"""Point d'entrée du bot."""
from __future__ import annotations

import asyncio

import discord
from discord.ext import commands

from bot.config import config
from bot.services import cleanup
from bot.services.fileserver import start_fileserver
from bot.services.storage import build_storage_provider
from bot.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

INTENTS = discord.Intents.default()
INTENTS.message_content = True  # nécessaire pour détecter les URLs envoyées en DM


class VideoDownloadBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=INTENTS)
        self.storage = build_storage_provider()
        self._fileserver_runner = None
        self._cleanup_task: asyncio.Task | None = None

    async def setup_hook(self) -> None:
        from bot.cogs.download import DownloadCog

        await self.add_cog(DownloadCog(self, self.storage))
        await self.load_extension("bot.cogs.events")

        try:
            synced = await self.tree.sync()
            logger.info("%d commande(s) slash synchronisée(s)", len(synced))
        except discord.HTTPException:
            logger.exception("Échec de la synchronisation des commandes slash")

        self._fileserver_runner = await start_fileserver(self.storage)
        self._cleanup_task = asyncio.create_task(cleanup.run_periodic_cleanup(self.storage))

    async def close(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._fileserver_runner:
            await self._fileserver_runner.cleanup()
        await super().close()

    async def on_ready(self) -> None:
        logger.info("Bot connecté en tant que %s (id: %s)", self.user, self.user.id)


def main() -> None:
    bot = VideoDownloadBot()
    bot.run(config.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
