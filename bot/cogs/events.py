"""Cog gérant les messages directs contenant une URL (sans passer par /download)."""
from __future__ import annotations

import discord
from discord.ext import commands

from bot.utils.logging import get_logger
from bot.utils.urls import extract_first_url, is_well_formed_url

logger = get_logger(__name__)


class EventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        # On ne réagit qu'aux DMs : dans un serveur, /download reste la méthode explicite.
        if not isinstance(message.channel, discord.DMChannel):
            return

        url = extract_first_url(message.content)
        if url is None:
            # Le système évite de réagir inutilement aux messages sans lien vidéo.
            return
        if not is_well_formed_url(url):
            await message.channel.send("❌ Cette URL n'est pas valide.")
            return

        download_cog = self.bot.get_cog("DownloadCog")
        if download_cog is None:
            logger.error("DownloadCog introuvable, impossible de traiter l'URL reçue en DM")
            return

        await download_cog.handle_message_url(message, url)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventsCog(bot))
