"""Petit serveur HTTP interne servant les liens de téléchargement temporaires (fallback)."""
from __future__ import annotations

from aiohttp import web

from bot.config import config
from bot.services.storage import StorageProvider
from bot.utils.logging import get_logger

logger = get_logger(__name__)


def build_app(storage: StorageProvider) -> web.Application:
    app = web.Application()

    async def handle_download(request: web.Request) -> web.StreamResponse:
        token = request.match_info["token"]
        stored = await storage.resolve(token)
        if stored is None:
            raise web.HTTPNotFound(text="Ce lien est invalide ou a expiré.")
        return web.FileResponse(
            path=stored.path,
            headers={"Content-Disposition": f'attachment; filename="{stored.filename}"'},
        )

    app.router.add_get("/files/{token}", handle_download)
    return app


async def start_fileserver(storage: StorageProvider) -> web.AppRunner:
    app = build_app(storage)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.fallback_server_host, config.fallback_server_port)
    await site.start()
    logger.info(
        "Serveur de fallback démarré sur %s:%s", config.fallback_server_host, config.fallback_server_port
    )
    return runner
