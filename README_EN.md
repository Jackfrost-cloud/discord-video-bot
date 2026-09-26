# Discord Video Bot

Discord bot that lets users send a video URL (YouTube, TikTok, Instagram, Twitter/X, and any other platform supported by `yt-dlp`), choose a quality using buttons, and receive the file — directly via DM if its size allows it, or through a temporary link otherwise.

## 1. Architecture

```text
discord-video-bot/
├── bot/
│   ├── main.py               # entry point, bot startup + fallback server + cleanup
│   ├── config.py             # centralized configuration (.env)
│   ├── cogs/
│   │   ├── download.py       # /download command, quality buttons, orchestration
│   │   └── events.py         # detects URLs sent via DM
│   ├── services/
│   │   ├── extractor.py      # metadata + available qualities (yt-dlp, no download)
│   │   ├── downloader.py     # actual download (yt-dlp + FFmpeg merging)
│   │   ├── media_processor.py# file validation and finalization
│   │   ├── storage.py        # StorageProvider abstraction (LocalStorage included)
│   │   ├── fileserver.py     # internal HTTP server for temporary links
│   │   ├── queue.py          # queue, per-user limits, cooldown
│   │   └── cleanup.py        # cleanup of temporary files and expired links
│   ├── models/download_job.py
│   └── utils/                # urls.py, formatting.py, logging.py
├── tests/
├── .env.example
├── Dockerfile / docker-compose.yml
└── requirements.txt
```

## 2. Technologies

- **Python 3.12+**, `discord.py` 2.x (slash commands + UI components)
- **yt-dlp** as the extraction and download engine
- **FFmpeg**, automatically invoked by yt-dlp to merge separate video/audio streams
- **aiohttp**, for the small internal HTTP server that serves temporary download links
  (fallback for oversized files)
- **pytest** + **pytest-asyncio** for testing

## 3. Main Technical Decisions

- **Fully asynchronous**: blocking `yt-dlp` calls run through
  `asyncio.to_thread`, never in the bot's event loop.
- **Dynamic format selectors** (`bestvideo[height<=X]+bestaudio/best[height<=X]`):
  the bot never offers a quality that does not actually exist for the requested video.
- **Queue + semaphore** to limit global and per-user concurrency, with a configurable cooldown
  — a stream of downloads never blocks other users.
- **Abstract storage (`StorageProvider`)**: `LocalStorage` is provided and functional,
  but the code is not coupled to a specific provider — an `S3Storage` can be added by
  implementing the same interface.
- **Fallback security**: each temporary file is accessible through a random token
  (`secrets.token_urlsafe`), never through its system path; links expire and are
  automatically cleaned up.
- **No false promises**: if a quality, platform, or authentication method is not available,
  the bot clearly says so rather than simulating a result.

## 4. Installation

```bash
git clone https://github.com/Jackfrost-cloud/discord-video-bot.git
cd discord-video-bot
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### FFmpeg Installation

- **Windows**: download a build from https://www.gyan.dev/ffmpeg/builds/, extract
  the archive, and add the `bin` directory to your `PATH` (or set `FFMPEG_LOCATION` in `.env`).
- **Linux (Debian/Ubuntu)**:
  ```bash
  sudo apt update && sudo apt install ffmpeg
  ```
- **Docker**: nothing to do, FFmpeg is already installed in the image (see `Dockerfile`).

## 5. Configuration

Copy `.env.example` to `.env` and set at least `DISCORD_TOKEN`:

```bash
cp .env.example .env
```

Each variable is documented in `.env.example` (concurrency, timeouts, maximum Discord file
size, temporary link retention, etc.).

## 6. Creating the Discord Bot

1. Go to https://discord.com/developers/applications and create a **New Application**.
2. In the **Bot** tab, click **Reset Token** and copy the token into `DISCORD_TOKEN`
   (never publish it or commit it).
3. Still in **Bot**, enable the **Message Content Intent** (required to
   detect URLs sent via DM).
4. Under **OAuth2 > URL Generator**, select the `bot` and `applications.commands` scopes,
   then grant the `Send Messages`, `Attach Files`, `Embed Links`, and `Use Slash Commands` permissions.
5. Open the generated URL to invite the bot to your server.

## 7. Running

```bash
python -m bot.main
```

On the first startup, the bot automatically synchronizes the `/download` slash command
(this can take up to an hour for it to appear globally; synchronization is instant on a
test server if you limit synchronization to a specific guild).

## 8. Tests

```bash
pip install -r requirements.txt
pytest
```

The tests cover URL validation, formatting, safe filename generation, the job model, and
queue behavior (per-user limits).
They do not download any real videos — `yt-dlp` is not called during the tests.

## 9. Docker Deployment

```bash
cp .env.example .env   # then set DISCORD_TOKEN and the rest
docker compose up -d
```

The container includes Python, all dependencies, and FFmpeg. The `./downloads` and `./tmp`
directories are mounted as volumes to persist files currently being processed across
restarts.

## 10. Known Issues / Limitations

- The fallback link is served by an HTTP server **without native HTTPS support**: in production,
  put it behind a reverse proxy (nginx, Caddy, Traefik) that terminates TLS before
  forwarding `PUBLIC_BASE_URL`.
- `DISCORD_MAX_FILE_SIZE` must be adjusted according to your server's actual boost level (25 MB by
  default, 50 MB or 100 MB depending on boosts, or the specific limit if the bot runs on an
  account with Nitro).
- DRM-protected content, authentication, or paywalled content is intentionally not supported:
  the bot fails cleanly rather than attempting to bypass a protection mechanism.
- `STORAGE_PROVIDER` only provides `local` by default; a remote provider (S3, etc.)
  requires implementing `StorageProvider` in `bot/services/storage.py`.
