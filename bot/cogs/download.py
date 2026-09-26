"""Cog gérant la commande /download et le flux complet de téléchargement."""
from __future__ import annotations

from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import config
from bot.models.download_job import DownloadJob, JobStatus
from bot.services import cleanup, media_processor
from bot.services.downloader import DownloadFailedError, DownloadTimeoutError, download_video
from bot.services.extractor import (
    AuthenticationRequiredError,
    QualityOption,
    VideoInfo,
    VideoUnavailableError,
    fetch_video_info,
)
from bot.services.queue import (
    CooldownActiveError,
    DownloadQueue,
    QueueFullError,
    TooManyActiveDownloadsError,
)
from bot.services.storage import StorageProvider
from bot.utils.formatting import format_duration, format_size
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class QualitySelectView(discord.ui.View):
    """Boutons de sélection de qualité, restreints à l'auteur de la demande."""

    def __init__(self, owner_id: int, qualities: list[QualityOption], on_choice):
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.on_choice = on_choice
        self.message: discord.Message | None = None

        for quality in qualities:
            self.add_item(self._make_button(quality))

    def _make_button(self, quality: QualityOption) -> discord.ui.Button:
        button = discord.ui.Button(
            label=quality.label,
            style=discord.ButtonStyle.success if quality.height is None else discord.ButtonStyle.primary,
        )

        async def callback(interaction: discord.Interaction) -> None:
            # Un autre utilisateur ne doit pas pouvoir cliquer sur le bouton d'une demande
            # qui ne lui appartient pas.
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message(
                    "❌ Cette sélection ne t'appartient pas.", ephemeral=True
                )
                return
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)
            await self.on_choice(interaction, quality)
            self.stop()

        button.callback = callback
        return button

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(content="⏱️ Sélection expirée.", view=self)
            except discord.HTTPException:
                pass


def _build_info_embed(info: VideoInfo) -> discord.Embed:
    embed = discord.Embed(title="🎬 Vidéo détectée", color=discord.Color.blurple())
    embed.add_field(name="Titre", value=info.title[:256], inline=False)
    embed.add_field(name="Plateforme", value=info.platform, inline=True)
    embed.add_field(name="Durée", value=format_duration(info.duration), inline=True)
    if info.thumbnail:
        embed.set_thumbnail(url=info.thumbnail)
    embed.set_footer(text="Choisis une qualité ci-dessous.")
    return embed


def _extract_percent(data: dict) -> float:
    total = data.get("total_bytes") or data.get("total_bytes_estimate")
    downloaded = data.get("downloaded_bytes") or 0
    if not total:
        return 0.0
    return min(100.0, downloaded / total * 100)


def _progress_bar(percent: float, width: int = 20) -> str:
    filled = int(width * percent / 100)
    return "█" * filled + "░" * (width - filled)


class DownloadCog(commands.Cog):
    def __init__(self, bot: commands.Bot, storage: StorageProvider):
        self.bot = bot
        self.storage = storage
        self.download_queue = DownloadQueue(runner=self._run_job)
        self.download_queue.start_workers()
        self._progress_messages: dict[str, discord.Message] = {}

    async def cog_unload(self) -> None:
        await self.download_queue.stop()

    @app_commands.command(name="download", description="Télécharge une vidéo à partir d'une URL")
    @app_commands.describe(url="Lien vers la vidéo à télécharger")
    async def download(self, interaction: discord.Interaction, url: str) -> None:
        await interaction.response.defer(thinking=True)
        message = await interaction.followup.send("🔎 Analyse de la vidéo...")
        await self._process_url(url=url, user=interaction.user, channel=interaction.channel, message=message)

    async def handle_message_url(self, message: discord.Message, url: str) -> None:
        status_message = await message.channel.send("🔎 Analyse de la vidéo...")
        await self._process_url(url=url, user=message.author, channel=message.channel, message=status_message)

    async def _process_url(self, *, url: str, user, channel, message: discord.Message) -> None:
        try:
            video_info = await fetch_video_info(url)
        except AuthenticationRequiredError:
            await self._safe_edit(
                message, "❌ Cette vidéo nécessite une authentification qui n'est pas configurée sur le bot."
            )
            return
        except VideoUnavailableError as exc:
            logger.info("Vidéo indisponible pour %s : %s", url, exc)
            await self._safe_edit(
                message, "❌ Cette vidéo n'est pas disponible ou ne peut pas être téléchargée."
            )
            return
        except Exception:
            logger.exception("Erreur inattendue lors de l'extraction pour %s", url)
            await self._safe_edit(message, "❌ Cette plateforme ou ce contenu n'est pas compatible.")
            return

        if not video_info.qualities:
            await self._safe_edit(message, "❌ Aucune qualité téléchargeable n'a été trouvée pour cette vidéo.")
            return

        embed = _build_info_embed(video_info)

        async def on_choice(button_interaction: discord.Interaction, quality: QualityOption) -> None:
            await button_interaction.followup.send(
                f"⏳ Demande de téléchargement en **{quality.label}** ajoutée à la file..."
            )
            await self._start_job(
                user_id=user.id, channel=channel, url=url, quality=quality, title=video_info.title
            )

        view = QualitySelectView(owner_id=user.id, qualities=video_info.qualities, on_choice=on_choice)
        await self._safe_edit(message, content=None, embed=embed, view=view)
        view.message = message

    async def _start_job(self, *, user_id: int, channel, url: str, quality: QualityOption, title: str) -> None:
        job = DownloadJob.create(
            user_id=user_id,
            channel_id=channel.id,
            url=url,
            format_selector=quality.format_selector,
            quality_label=quality.label,
        )
        job.title = title

        try:
            self.download_queue.check_can_enqueue(user_id)
        except CooldownActiveError as exc:
            await channel.send(f"⏱️ Attends encore {exc.remaining_seconds:.0f}s avant un nouveau téléchargement.")
            return
        except (TooManyActiveDownloadsError, QueueFullError) as exc:
            await channel.send(f"❌ {exc}")
            return

        progress_message = await channel.send(f"⬇️ Téléchargement en {quality.label} en préparation...")
        self._progress_messages[job.job_id] = progress_message
        await self.download_queue.enqueue(job)

    async def _run_job(self, job: DownloadJob) -> None:
        channel = self.bot.get_channel(job.channel_id) or await self.bot.fetch_channel(job.channel_id)
        progress_message = self._progress_messages.get(job.job_id)

        async def on_progress(data: dict) -> None:
            if progress_message is None:
                return
            if data.get("status") == "downloading":
                percent = _extract_percent(data)
                speed = data.get("speed")
                text = f"⬇️ Téléchargement de la vidéo en {job.quality_label}...\n\n{_progress_bar(percent)} {percent:.0f}%"
                if speed:
                    text += f"\n{percent:.0f}% • {format_size(speed)}/s"
                await self._safe_edit_text(progress_message, text)
            elif data.get("status") == "finished":
                await self._safe_edit_text(progress_message, "🔄 Finalisation (fusion audio/vidéo si nécessaire)...")

        try:
            job.status = JobStatus.DOWNLOADING
            raw_path = await download_video(job.job_id, job.url, job.format_selector, on_progress)

            job.status = JobStatus.PROCESSING
            final_path = media_processor.finalize_output(raw_path, job.title or job.job_id, job.job_id)
            job.output_path = final_path
            size = media_processor.get_file_size(final_path)

            await self._deliver_result(channel, job, final_path, size)
            job.status = JobStatus.DONE

        except DownloadTimeoutError:
            job.status = JobStatus.FAILED
            await self._safe_edit_text(
                progress_message, "⏱️ Le téléchargement a pris trop de temps et a été annulé."
            )
        except (DownloadFailedError, media_processor.InvalidMediaFileError) as exc:
            job.status = JobStatus.FAILED
            logger.error("Échec du téléchargement pour job %s : %s", job.job_id, exc)
            await self._safe_edit_text(
                progress_message, "❌ Le téléchargement a échoué.\n\nRéessaie dans quelques instants."
            )
        except Exception:
            job.status = JobStatus.FAILED
            logger.exception("Erreur inattendue pour le job %s", job.job_id)
            await self._safe_edit_text(progress_message, "❌ Impossible de traiter la vidéo demandée.")
        finally:
            cleanup.cleanup_job_files(job.job_id)
            self._progress_messages.pop(job.job_id, None)

    async def _deliver_result(self, channel, job: DownloadJob, path: Path, size: int) -> None:
        if size <= config.discord_max_file_size:
            await channel.send(
                content=(
                    "✅ Téléchargement terminé\n\n"
                    f"🎬 Nom : {path.name}\n"
                    f"📺 Qualité : {job.quality_label}\n"
                    f"📦 Taille : {format_size(size)}"
                ),
                file=discord.File(path),
            )
            path.unlink(missing_ok=True)
        else:
            await channel.send(
                f"📦 La vidéo fait {format_size(size)}.\n\n"
                "Discord ne permet pas de l'envoyer directement.\n\n"
                "☁️ Création d'un lien temporaire..."
            )
            stored = await self.storage.store(path, path.name)
            url = await self.storage.get_url(stored)
            await channel.send(
                f"✅ Vidéo prête.\n\n🔗 {url}\n\n"
                f"⏳ Ce lien expirera dans {config.file_retention_minutes} minutes."
            )

    @staticmethod
    async def _safe_edit(message, content, embed=None, view=None):
        if message is None:
            return
        try:
            kwargs = {"content": content}
            if embed is not None:
                kwargs["embed"] = embed
            if view is not None:
                kwargs["view"] = view
            await message.edit(**kwargs)
        except discord.HTTPException:
            logger.warning("Impossible de mettre à jour le message")

    @staticmethod
    async def _safe_edit_text(message, content: str) -> None:
        if message is None:
            return
        try:
            await message.edit(content=content)
        except discord.HTTPException:
            logger.warning("Impossible de mettre à jour le message de progression")
