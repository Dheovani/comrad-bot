# ComradBot

[![CI](https://github.com/Dheovani/comrad-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Dheovani/comrad-bot/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Dheovani/comrad-bot/actions/workflows/codeql.yml/badge.svg)](https://github.com/Dheovani/comrad-bot/actions/workflows/codeql.yml)

ComradBot is a modular Discord bot for a private group of friends who play games together. The
current MVP connects three vertical features: music from temporary public streams, validated custom
sounds, and generative AI responses that can also be spoken in a voice channel.

Music, custom sounds, and TTS share one guild-scoped audio player. Queue and voice state never leak
between Discord guilds.

## Current MVP

The current implementation includes:

- automatic Cog loading and fast slash-command synchronization to a development guild;
- a bounded guild audio queue with priority insertion for custom sounds and TTS;
- pause, resume, skip, stop, idle disconnect, and a small button-based player panel;
- a platform-neutral `AudioResolver` implemented with `yt-dlp`, timeouts, and no permanent music
  downloads;
- custom sound validation with extension, MIME type, size, FFprobe content, and duration checks;
- conversion of accepted uploads to Opus files stored under guild-specific directories with UUIDs;
- async SQLite persistence through SQLAlchemy 2 repositories and an initial Alembic migration;
- an optional OpenAI provider using the Responses and Speech APIs;
- bounded AI memory, local user/guild rate limits, cooldowns, timeouts, and metadata-only usage logs;
- centralized contextual logging and sanitized global command error handling;
- deterministic tests that do not contact Discord, OpenAI, or music platforms.

See [TODO.md](TODO.md) for the detailed roadmap and honest completion status.

## Requirements

- Python 3.12 or newer;
- Git;
- FFmpeg and FFprobe available on `PATH`;
- a Discord application and bot token;
- Windows with Git Bash for the commands below. Linux and macOS work with the usual virtualenv
  activation command.

Runtime and development dependencies are declared in `pyproject.toml`. The project remains
compatible with `pip install -e .` and does not require Poetry.

## Installation on Windows with Git Bash

```bash
git clone https://github.com/Dheovani/comrad-bot.git
cd comrad-bot
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

### Installing FFmpeg

One convenient option on Windows is:

```bash
winget install --id Gyan.FFmpeg -e
```

Restart the terminal and verify both programs:

```bash
ffmpeg -version
ffprobe -version
```

Alternatively, download a build from the [official FFmpeg website](https://ffmpeg.org/download.html)
and add its `bin` directory to `PATH`. ComradBot fails at startup with an actionable message when
either executable is unavailable.

## Discord Developer Portal setup

1. Create an application and bot in the
   [Discord Developer Portal](https://discord.com/developers/applications).
2. Generate a token under **Bot** and store it only in the local `.env` as `DISCORD_TOKEN`.
3. Under **OAuth2 > URL Generator**, select the `bot` and `applications.commands` scopes.
4. Grant only these permissions: View Channels, Send Messages, Embed Links, Attach Files, Read
   Message History, Connect, Speak, and Use Application Commands.
5. Invite the bot and set the server ID as `DISCORD_GUILD_ID` for immediate development sync.

Do not grant Administrator. Message Content Intent is disabled and is not needed by the current
commands. The bot enables only Guilds and Voice States intents.

## Environment variables

Copy `.env.example` to `.env`. Never commit `.env`.

| Variable | Required | Default or purpose |
| --- | --- | --- |
| `DISCORD_TOKEN` | Yes | Secret bot token; startup fails clearly when missing |
| `DISCORD_GUILD_ID` | Recommended for development | Guild receiving immediate command sync |
| `DISCORD_SYNC_GLOBAL_COMMANDS` | No | `false`; global command propagation can take longer |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./data/comradbot.db` |
| `OPENAI_API_KEY` | No | AI commands are disabled without it; audio features still work |
| `OPENAI_MODEL` | No | `gpt-4.1-mini` |
| `OPENAI_TTS_MODEL` | No | `gpt-4o-mini-tts` |
| `OPENAI_TTS_VOICE` | No | `coral`, an official provider voice |
| `DATA_DIRECTORY` | No | `./data` |
| `SOUNDS_DIRECTORY` | No | `./data/sounds` |
| `DEFAULT_VOLUME` | No | `0.5`, constrained to 0–1 |
| `MAX_QUEUE_SIZE` | No | `100` |
| `MAX_SOUND_FILE_SIZE_MB` | No | `10` |
| `MAX_SOUND_DURATION_SECONDS` | No | `30` |
| `MAX_AI_CONTEXT_MESSAGES` | No | `30` |
| `MAX_AI_RESPONSE_CHARACTERS` | No | `1800` |
| `AUDIO_IDLE_TIMEOUT_SECONDS` | No | `300` |
| `LOG_LEVEL` | No | `INFO` |

Additional AI safeguards can be configured with `AI_USER_REQUESTS_PER_MINUTE`,
`AI_GUILD_REQUESTS_PER_MINUTE`, `AI_COOLDOWN_SECONDS`, `AI_MAX_PROMPT_CHARACTERS`, and
`AI_TIMEOUT_SECONDS`.

## Running the bot

With the virtualenv active and `.env` configured:

```bash
python -m comradbot
```

The equivalent installed entry point is:

```bash
comradbot
```

The local development schema is created idempotently at startup. To apply migrations explicitly:

```bash
alembic upgrade head
```

## Available commands

- `/ping`
- `/music play query:<text-or-url>`
- `/music pause`
- `/music resume`
- `/music skip`
- `/music stop`
- `/music queue`
- `/music now`
- `/music volume value:<0-100>`
- `/music remove position:<number>`
- `/music clear`
- `/music disconnect`
- `/sound upload name:<name> file:<attachment>`
- `/sound play name:<name> interrupt:<boolean>`
- `/sound list`
- `/sound delete name:<name>`
- `/ai ask prompt:<text>`
- `/ai reset`
- `/ai speak prompt:<text>`

The music panel provides pause/resume, skip, stop, and queue buttons, but every action remains
available as a slash command.

## AI persona

The default persona is a friendly, theatrical caricature inspired by communist characters from old
television series. It casually calls people “comrade” or “companheiro” and uses exaggerated
collective-workplace imagery for humor. It does not introduce political discussion, advocacy, or
persuasion unless a user explicitly brings up politics. The prompt lives separately in
`src/comradbot/ai/prompts.py` and can be replaced without changing command code.

Generated speech uses only official provider voices. The project does not support voice cloning or
impersonation of real people.

## Quality checks

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest
```

Tests use disposable databases and files plus fakes for external services. The default suite never
makes real Discord, OpenAI, or media-platform requests.

GitHub Actions runs the same installation, lint, formatting, type-checking, and test commands on
Python 3.12 and 3.13 for every pull request and push to `main`. A separate CodeQL workflow analyzes
Python changes on pull requests, pushes to `main`, manual runs, and a weekly schedule. Code scanning
must be enabled in the repository settings for CodeQL results to appear under the Security tab.

## Technical decisions

- **One player per guild:** `GuildAudioManager` is the only player registry. Music, custom sounds,
  and TTS all produce `AudioItem` objects for the same queue.
- **Priority without mixing:** music is appended normally; custom sounds and TTS can be inserted as
  the next item. Explicit interruption stops the current item. Interrupted streams are not resumed
  automatically in the MVP.
- **Internal Opus format:** accepted uploads are converted to 96 kbps Opus, which is compact and
  appropriate for Discord voice. Physical filenames use UUIDs; logical names remain in the database.
- **Temporary streams:** the resolver gives ephemeral public stream URLs to FFmpeg and never stores
  third-party music permanently. DRM bypass and private authentication are out of scope.
- **Optional AI:** Cogs depend on `AIService`, which depends on `AIProvider`. Usage records contain
  IDs, operation names, character counts, and outcomes—not full conversation content.
- **Initial schema:** metadata bootstrap supports local development; migration `0001` is the baseline,
  and later schema changes must use Alembic.
- **Voice control permissions:** mutating slash commands and player buttons require the member to
  share the bot's voice channel. Members with Move Members permission may control it from another
  voice channel; read-only queue views remain available without joining voice.

## Current limitations

- Stream URLs can expire before playback in very long queues; playback-time re-resolution is future
  work.
- There is no simultaneous mixing or automatic resume after interruption.
- `/sound info`, `random`, `rename`, and autocomplete are not implemented yet.
- `/ai summarize`, `/ai status`, and persistent per-guild settings are not implemented yet.
- SQLite is intended for a single local instance. Distributed deployment requires a different
  persistence and locking strategy.
- An abrupt process termination can leave a generated file under `data/tmp`; it can be removed while
  the bot is stopped.

## Troubleshooting

- **Missing `DISCORD_TOKEN`:** ensure `.env` exists at the repository root and contains a valid token
  without extra quotes. Never paste the token into source code or logs.
- **Missing `ffmpeg` or `ffprobe`:** restart the terminal after installation and verify both version
  commands.
- **Commands do not appear:** set `DISCORD_GUILD_ID`, verify the `applications.commands` scope, and
  restart the bot. Global synchronization is not immediate.
- **The bot connects but has no audio:** verify Connect/Speak permissions, channel user limits, and
  that PyNaCl was installed.
- **Music is unavailable:** private, protected, removed, or authenticated content is unsupported. Try
  another public source.
- **AI is disabled:** this is expected without `OPENAI_API_KEY`; music and custom sounds continue to
  work normally.
- **An upload is rejected:** extension and MIME type are only initial checks; FFprobe must also detect
  real audio within the configured size and duration limits.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes. Report vulnerabilities according to
[SECURITY.md](SECURITY.md), without opening a public issue for sensitive reports.

ComradBot is distributed under the [MIT License](LICENSE).
