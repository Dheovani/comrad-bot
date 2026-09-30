# ComradBot

[![CI](https://github.com/Dheovani/comrad-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Dheovani/comrad-bot/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Dheovani/comrad-bot/actions/workflows/codeql.yml/badge.svg)](https://github.com/Dheovani/comrad-bot/actions/workflows/codeql.yml)
[![Docker Hub](https://img.shields.io/docker/v/theovani/comradbot?label=Docker%20Hub&sort=semver)](https://hub.docker.com/r/theovani/comradbot)

ComradBot is a modular Discord bot for private groups of friends. It combines music playback,
managed custom sounds, generative AI, TTS, attachment transcription, and lightweight social tools.
Music, sounds, and TTS share one isolated audio player per Discord server.

## Features

- Music search or public-URL playback through a bounded queue, playlists, repeat modes, volume,
  playback controls, and a persistent button panel;
- validated custom sound upload, Opus conversion, metadata, autocomplete, quotas, audit history,
  and portable ZIP export and restore;
- Groq or OpenAI text conversations, optional OpenAI or ElevenLabs TTS, direct mention replies,
  bounded memory, budgets, usage summaries, and Groq attachment transcription;
- persistent per-server settings and feature flags backed by async SQLite and Alembic;
- English and Brazilian Portuguese Discord localization;
- Discord-native polls for game-night planning;
- Docker health checks, optional external heartbeat monitoring, and automated container releases.

See [CHANGELOG.md](CHANGELOG.md) for the 1.1.1 release, [TODO.md](TODO.md) for the remaining roadmap,
and [technical decisions](docs/technical-decisions.md) for architecture and tradeoffs.

## Requirements

- Python 3.12 or newer;
- FFmpeg, FFprobe, and Deno 2.3 or newer on `PATH` for full YouTube support;
- a Discord application and bot token;
- Git.

Docker is an alternative to installing Python and FFmpeg locally. Poetry is not required.

## Local installation on Windows with Git Bash

```bash
git clone https://github.com/Dheovani/comrad-bot.git
cd comrad-bot
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

Install FFmpeg with WinGet, restart the terminal, and verify both executables:

```bash
winget install --id Gyan.FFmpeg -e
ffmpeg -version
ffprobe -version
```

Install Deno for yt-dlp's YouTube challenge solver and verify it:

```bash
winget install --id DenoLand.Deno -e
deno --version
```

If virtual environment creation reports `Permission denied` while `(.venv)` is already visible,
deactivate it, close processes using `.venv`, remove the broken environment, and create it again.

## Discord setup

1. Create an application and bot in the
   [Discord Developer Portal](https://discord.com/developers/applications).
2. Store the token only as `DISCORD_TOKEN` in `.env`.
3. In **OAuth2 > URL Generator**, select `bot` and `applications.commands`.
4. Grant View Channels, Send Messages, Embed Links, Attach Files, Read Message History, Create
   Polls, Connect, Speak, and Use Application Commands.
5. Invite the bot and set `DISCORD_GUILD_ID` for immediate development command synchronization.

Do not grant Administrator. Message Content Intent is disabled by default. Enable it in the portal
and set `DISCORD_MESSAGE_CONTENT_INTENT=true` only if `/ai summarize` is needed.

## Configuration

Copy [.env.example](.env.example) to `.env`; it is the complete configuration reference. Never
commit `.env` or expose bot tokens, provider keys, or external-monitor ping URLs.

Minimum local configuration:

```env
DISCORD_TOKEN=replace-me
DISCORD_GUILD_ID=replace-me
DATABASE_URL=sqlite+aiosqlite:///./data/comradbot.db
```

AI is optional. Music and custom sounds continue working without an AI key.

### Groq

Create a key in the Groq console and configure:

```env
AI_PROVIDER=groq
GROQ_API_KEY=replace-me
GROQ_MODEL=openai/gpt-oss-120b
GROQ_TRANSCRIPTION_MODEL=whisper-large-v3-turbo
```

Groq provides text and attachment transcription. Its quotas depend on the provider plan.

### TTS

Use OpenAI:

```env
TTS_PROVIDER=openai
OPENAI_API_KEY=replace-me
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=coral
```

Or pair any text provider with an official ElevenLabs voice:

```env
TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=replace-me
ELEVENLABS_TTS_MODEL=eleven_flash_v2_5
ELEVENLABS_TTS_VOICE_ID=replace-with-an-official-voice-id
```

`CUSTOM_COMRADBOT_PERSONA` replaces the built-in persona when non-empty. Keep multiline dotenv
values on one quoted assignment using `\n` and escaped quotes.

## Run locally

```bash
python -m comradbot
```

Development-guild commands synchronize on startup when `DISCORD_GUILD_ID` is set. Global command
propagation can take longer.

## Run with Docker

The published AMD64 and ARM64 image is
[`theovani/comradbot`](https://hub.docker.com/r/theovani/comradbot). Download `.env.example` and
`compose.production.yaml` from the matching GitHub release, rename the environment file to `.env`,
then run:

```bash
docker compose -f compose.production.yaml pull
docker compose -f compose.production.yaml up -d
docker compose -f compose.production.yaml ps
docker compose -f compose.production.yaml logs -f comradbot
```

The production file pins `theovani/comradbot:1.1.1`. The named `comradbot-data` volume contains the
database and custom sounds. Routine shutdown must not use `--volumes`.

Contributors can build the current checkout with:

```bash
docker compose up --build -d
```

For unattended deployment, persistence, monitoring, updates, and alert testing, follow the
[Ubuntu VPS hosting guide](docs/hosting-ubuntu-vps.md).

## Commands

Use `/help` inside Discord for the current command guide and parameter hints.

| Group | Purpose |
| --- | --- |
| `/music` | Play, pause, resume, skip, stop, inspect queues, control volume and repeat, and manage playlists |
| `/sound` | Upload, play, search, inspect, edit, audit, export, restore, and delete custom sounds |
| `/ai` | Ask, reset, summarize, discover audio, transcribe attachments, speak, and inspect status or usage |
| `/settings` | Configure volume, AI memory and budgets, sound quotas, and per-group feature flags |
| `/social poll` | Create a public Discord-native poll |
| `/help`, `/ping`, `/health` | Discover commands and inspect bot or dependency health |

Users must join a voice channel before starting playback. Voice controls normally require the user
to share the bot's channel; members with Move Members can control it from another channel.

## Data and limitations

- SQLite and the audio player support one running bot replica only;
- music streams are temporary, public, and never stored permanently;
- DRM bypass, private-content access, and platform-native playlist import are unsupported;
- custom sounds are stored per guild as normalized Opus files;
- interrupted audio is not resumed automatically and simultaneous mixing is not implemented;
- speech recognition accepts explicit attachments only and never listens to voice channels;
- AI memory, limits, budgets, provider availability, and retention are configurable per server.

## Quality checks

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest
```

The default suite does not contact Discord, AI providers, or music platforms. GitHub Actions runs
the checks on Python 3.12 and 3.13, builds the container, and publishes coverage artifacts.

Dependabot checks Python, Docker, and Actions dependencies weekly. A separate scheduled workflow
performs live YouTube-to-FFmpeg and Groq model-availability checks and opens one maintenance issue on
failure. Add `GROQ_API_KEY` as an Actions secret to enable the Groq check; optionally set the
`GROQ_MODEL` Actions variable when using a model other than the documented default.

## Troubleshooting

- **Commands are missing:** set `DISCORD_GUILD_ID`, verify the `applications.commands` scope, and
  restart the bot.
- **Voice is unavailable:** reinstall with `python -m pip install -e ".[dev]"` and verify Connect and
  Speak permissions plus FFmpeg and FFprobe.
- **YouTube music returns HTTP 403:** update the project dependencies, verify `deno --version`, and
  rebuild or pull version `1.1.1` or newer; older images contain an obsolete yt-dlp release.
- **AI is disabled:** configure `AI_PROVIDER` and its matching key; non-AI features remain available.
- **Summarization is disabled:** enable Message Content Intent in the portal and `.env`.
- **Uploads fail:** confirm the configured size and duration limits; FFprobe validates real content,
  not only extension or MIME type.
- **Migration fails:** stop the bot, back up `data/comradbot.db`, then inspect `alembic current` and
  run `alembic upgrade head`.
- **Container is unhealthy:** inspect `docker compose ps` and logs, confirm `/app/data` is writable,
  and verify migrations, FFmpeg, FFprobe, and Discord startup.

## Documentation

- [Technical decisions](docs/technical-decisions.md)
- [Supported Ubuntu VPS deployment](docs/hosting-ubuntu-vps.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

ComradBot is distributed under the [MIT License](LICENSE).
