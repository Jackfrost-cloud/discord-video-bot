"""Configuration pytest : fournit les variables d'environnement requises avant l'import du bot."""
import os

os.environ.setdefault("DISCORD_TOKEN", "test-token-not-real")
os.environ.setdefault("MAX_CONCURRENT_DOWNLOADS", "2")
os.environ.setdefault("MAX_QUEUE_SIZE", "5")
os.environ.setdefault("MAX_ACTIVE_DOWNLOADS_PER_USER", "1")
os.environ.setdefault("DOWNLOAD_COOLDOWN", "0")
os.environ.setdefault("TEMP_DIRECTORY", "./tmp_test")
os.environ.setdefault("DOWNLOADS_DIRECTORY", "./downloads_test")
