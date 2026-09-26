"""Configuration centralisée des logs (jamais de secrets journalisés)."""
import logging
import sys

from bot.config import config


def setup_logging() -> None:
    level = getattr(logging, config.log_level, logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # discord.py est bavard en DEBUG, on le garde raisonnable.
    logging.getLogger("discord").setLevel(max(level, logging.INFO))
    logging.getLogger("discord.http").setLevel(max(level, logging.WARNING))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
