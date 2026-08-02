# ComradBot

[![CI](https://github.com/Dheovani/comrad-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Dheovani/comrad-bot/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Dheovani/comrad-bot/actions/workflows/codeql.yml/badge.svg)](https://github.com/Dheovani/comrad-bot/actions/workflows/codeql.yml)
[![Docker Hub](https://img.shields.io/docker/v/theovani/comradbot?label=Docker%20Hub&sort=semver)](https://hub.docker.com/r/theovani/comradbot)

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
  downloads, with sanitized provider failures, defensive metadata mapping, and playback-time
  refresh for tracks that waited in the queue;
- guild-scoped persistent playlists that save public source references and resolve fresh temporary
  streams when queued;
- custom sound validation with extension, MIME type, size, FFprobe content, and duration checks;
- conversion of accepted uploads to Opus files stored under guild-specific directories with UUIDs;
- custom sound details, random playback, permission-aware renaming, and name autocomplete;
- async SQLite persistence through SQLAlchemy 2 repositories and startup Alembic migrations;
- optional Groq and OpenAI text providers selected through configuration, plus OpenAI TTS;
- conversational responses when the bot is directly mentioned in a guild channel;
- opt-in recent-channel summaries and an AI configuration status command;
- bounded Groq speech recognition for validated audio and video attachments;
- persistent per-server default volume and AI availability settings;
- bounded AI memory, local user/guild rate limits, cooldowns, timeouts, and metadata-only usage logs;
- an ephemeral dependency health report with uptime, latency, audio-player, and command counters;
- centralized contextual logging and sanitized global command error handling;
- deterministic tests that do not contact Discord, Groq, OpenAI, or music platforms.

See [CHANGELOG.md](CHANGELOG.md) for the 1.0.0 release summary and [TODO.md](TODO.md) for future
evolution only.

## Requirements

- Python 3.12 or newer;
- Git;
- FFmpeg and FFprobe available on `PATH`;
- a Discord application and bot token;
- Windows with Git Bash for the commands below. Linux and macOS work with the usual virtualenv
  activation command.

Docker Desktop is an alternative to installing Python and FFmpeg directly. It is required only for
the container workflow described below.

Runtime and development dependencies are declared in `pyproject.toml`. The project remains
compatible with `pip install -e .` and does not require Poetry. Discord voice dependencies,
including PyNaCl and the DAVE protocol backend, are installed through the official
`discord.py[voice]` extra.

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

Do not grant Administrator. The bot enables Guilds, Guild Messages, and Voice States intents.
Message Content Intent remains disabled by default. Discord still provides content when the bot
itself is directly mentioned, so mention responses do not require general message access.

`/ai summarize` is the only current feature that needs Message Content Intent. To use it, enable
**Message Content Intent** under **Bot > Privileged Gateway Intents**, set
`DISCORD_MESSAGE_CONTENT_INTENT=true`, and restart the bot. The user and bot also need Read Message
History in that channel. ComradBot reads a bounded window only when the command is invoked, ignores
bot messages and attachments, and does not store the fetched transcript.

## Environment variables

Copy `.env.example` to `.env`. Never commit `.env`.

| Variable | Required | Default or purpose |
| --- | --- | --- |
| `DISCORD_TOKEN` | Yes | Secret bot token; startup fails clearly when missing |
| `DISCORD_GUILD_ID` | Recommended for development | Guild receiving immediate command sync |
| `DISCORD_SYNC_GLOBAL_COMMANDS` | No | `false`; global command propagation can take longer |
| `DISCORD_RESPOND_TO_MENTIONS` | No | `true`; send direct mentions to the configured AI |
| `DISCORD_MESSAGE_CONTENT_INTENT` | No | `false`; opt in to message access for `/ai summarize` |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./data/comradbot.db` |
| `ALEMBIC_CONFIG_FILE` | No | `./alembic.ini`; overridden to `/app/alembic.ini` in Docker |
| `ALEMBIC_DIRECTORY` | No | `./alembic`; overridden to `/app/alembic` in Docker |
| `AI_PROVIDER` | No | `auto`; accepts `auto`, `groq`, or `openai` |
| `GROQ_API_KEY` | No | Enables Groq text conversations and attachment transcription |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` |
| `GROQ_TRANSCRIPTION_MODEL` | No | `whisper-large-v3-turbo` |
| `OPENAI_API_KEY` | No | Enables OpenAI text responses and TTS |
| `OPENAI_MODEL` | No | `gpt-4.1-mini` |
| `OPENAI_TTS_MODEL` | No | `gpt-4o-mini-tts` |
| `OPENAI_TTS_VOICE` | No | `coral`, an official provider voice |
| `CUSTOM_COMRADBOT_PERSONA` | No | Replaces the built-in persona when non-empty |
| `DATA_DIRECTORY` | No | `./data` |
| `SOUNDS_DIRECTORY` | No | `./data/sounds` |
| `HEALTHCHECK_HEARTBEAT_FILE` | No | `./data/.heartbeat` |
| `DEFAULT_VOLUME` | No | `0.5`, fallback for servers without a persisted preference |
| `MAX_QUEUE_SIZE` | No | `100` |
| `MAX_PLAYLISTS_PER_GUILD` | No | `25` |
| `MAX_PLAYLIST_TRACKS` | No | `100` |
| `MAX_SOUND_FILE_SIZE_MB` | No | `10` |
| `MAX_SOUND_DURATION_SECONDS` | No | `30` |
| `MAX_SOUNDS_PER_GUILD` | No | `100`; default saved-sound count quota per server |
| `MAX_SOUND_STORAGE_MB_PER_GUILD` | No | `500`; default converted Opus storage quota per server |
| `MAX_AI_CONTEXT_MESSAGES` | No | `30` |
| `MAX_AI_RESPONSE_CHARACTERS` | No | `1800` |
| `MAX_TRANSCRIPTION_FILE_SIZE_MB` | No | `20`; cannot exceed Groq's 25 MB free-tier limit |
| `MAX_TRANSCRIPTION_DURATION_SECONDS` | No | `300` |
| `MAX_TRANSCRIPTION_CHARACTERS` | No | `12000` |
| `AUDIO_IDLE_TIMEOUT_SECONDS` | No | `300` |
| `LOG_LEVEL` | No | `INFO` |

Additional AI safeguards can be configured with `AI_USER_REQUESTS_PER_MINUTE`,
`AI_GUILD_REQUESTS_PER_MINUTE`, `AI_COOLDOWN_SECONDS`, `AI_MAX_PROMPT_CHARACTERS`, and
`AI_TIMEOUT_SECONDS`.

Container liveness timing can be adjusted with `HEARTBEAT_INTERVAL_SECONDS` and
`HEALTHCHECK_MAX_AGE_SECONDS`. The maximum age should remain comfortably greater than the update
interval.

With `AI_PROVIDER=auto`, OpenAI is selected for text and TTS when both provider keys exist,
preserving the previous configuration behavior. When `GROQ_API_KEY` is also present, attachment
transcription continues to use Groq independently of the selected text provider.

## Groq setup

Groq provides a rate-limited free plan suitable for a small private Discord server. Free quotas and
available models may change, so ComradBot treats quota failures as recoverable errors.

1. Create or sign in to a Groq Console account at
   [console.groq.com](https://console.groq.com/).
2. Open [API Keys](https://console.groq.com/keys) and create a key for ComradBot.
3. Copy `.env.example` to `.env` if the local file does not exist yet.
4. Set these values in `.env`:

   ```env
   AI_PROVIDER=groq
   GROQ_API_KEY=gsk_your_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   GROQ_TRANSCRIPTION_MODEL=whisper-large-v3-turbo
   ```

5. Keep `OPENAI_API_KEY` empty when OpenAI should not be used.
6. Install the updated dependencies:

   ```bash
   python -m pip install -e ".[dev]"
   ```

7. Restart the bot with `python -m comradbot`.
8. Test `/ai ask prompt:Olá` or send `@ComradBot olá` in a server channel.

Never commit `.env` or paste the Groq key into source code, Discord, screenshots, or logs. Direct
mentions send the text after the bot mention and the bounded conversation context for that channel
to the selected provider. Attachments are not sent. The bounded text conversation is stored in the
local SQLite database until `/ai reset` clears that channel; usage logs store counts and identifiers,
not an additional copy of the conversation text.

## Running the bot

With the virtualenv active and `.env` configured:

```bash
python -m comradbot
```

The equivalent installed entry point is:

```bash
comradbot
```

ComradBot applies Alembic migrations to `head` during startup before loading commands. The same
migration can be applied manually while the bot is stopped:

```bash
alembic upgrade head
```

The first migration-aware startup safely adopts known local databases created by the former
metadata bootstrap. It recognizes either the original `0001` schema or the complete current schema,
including the known hybrid state where current tables coexist with a stale `0001` marker. It adds
the appropriate Alembic revision and preserves existing data. An unversioned partial or modified
schema is rejected with an actionable error instead of being changed automatically. Back up
`data/comradbot.db` before manually repairing an inconsistent database.

## Running with Docker

The container includes Python, application dependencies, FFmpeg, FFprobe, Alembic migrations, and a
non-root runtime user. Docker Compose passes the local `.env` at runtime; credentials are not copied
into the image.

### Run the published image

The versioned image is published at
[`theovani/comradbot`](https://hub.docker.com/r/theovani/comradbot) for AMD64 and ARM64 Linux hosts.
Download `.env.example` and `compose.production.yaml` from the matching
[GitHub release](https://github.com/Dheovani/comrad-bot/releases), place them in the same directory,
and rename `.env.example` to `.env`. After configuring at least `DISCORD_TOKEN`, start version
1.0.0 without cloning the source repository:

```bash
docker compose -f compose.production.yaml pull
docker compose -f compose.production.yaml up -d
docker compose -f compose.production.yaml ps
```

Follow logs with:

```bash
docker compose -f compose.production.yaml logs -f comradbot
```

The production Compose file pins `theovani/comradbot:1.0.0` so deployments do not change
unexpectedly. Set `COMRADBOT_IMAGE` to select another published version:

```bash
COMRADBOT_IMAGE=theovani/comradbot:1.0.0 docker compose -f compose.production.yaml up -d
```

Use `docker compose -f compose.production.yaml down` to stop the bot. Do not add
`--volumes` unless the persistent database and custom sounds should be permanently deleted.

### Build from source

Contributors can build the current checkout with the development-oriented `compose.yaml`:

1. Install and start Docker Desktop.
2. Configure `.env` normally, including `DISCORD_TOKEN`.
3. Build and start ComradBot from the repository root:

   ```bash
   docker compose up --build -d
   ```

4. Follow startup and migration logs:

   ```bash
   docker compose logs -f comradbot
   ```

5. Inspect container and health status:

   ```bash
   docker compose ps
   ```

6. Stop the bot without deleting its data:

   ```bash
   docker compose down
   ```

The named volume `comradbot-data` stores SQLite, custom sounds, and runtime data under `/app/data`.
`docker compose down` preserves it; `docker compose down --volumes` deletes it and must not be used
unless permanent data removal is intended.

The named volume starts empty. To import an existing local `data/` directory before the first
container start, build the image and copy the data as the container's runtime UID:

```bash
docker compose build
docker run --rm --user root \
  -v comradbot-data:/target \
  -v "${PWD}/data:/source:ro" \
  comradbot:local \
  sh -c "cp -a /source/. /target/ && chown -R 10001:10001 /target"
```

Back up the local directory and ensure no host bot process is using its SQLite database during the
copy.

To rebuild after pulling a project update:

```bash
docker compose build --pull
docker compose up -d
```

Published container images are built only from GitHub Releases. The release workflow derives
immutable semantic-version tags such as `1.0.0` and `1.0`, updates `latest` for stable releases, and
attaches OCI metadata, provenance, and an SBOM. It rejects tags that disagree with `pyproject.toml`
or lack a matching `CHANGELOG.md` section. Each release also receives a checksummed
`comradbot-<version>-docker.zip` containing `.env.example` and `compose.production.yaml`. Docker Hub
credentials are stored only as the `DOCKER_USERNAME` Actions variable and `DOCKER_TOKEN` Actions
secret.

Back up the volume while the bot is stopped:

```bash
docker compose down
docker run --rm -v comradbot-data:/data -v "${PWD}:/backup" alpine \
  tar czf /backup/comradbot-data.tar.gz -C /data .
```

Treat the archive as sensitive because it contains server configuration and AI conversation
context. Test restoration procedures before relying on a backup. SQLite supports only one running
ComradBot instance with this volume; do not scale the Compose service beyond one replica.

## Available commands

- `/help`
- `/ping`
- `/health`
- `/music play query:<text-or-url>`
- `/music pause`
- `/music resume`
- `/music skip`
- `/music stop`
- `/music repeat mode:<off|track|queue>`
- `/music queue`
- `/music now`
- `/music volume value:<0-100>`
- `/music remove position:<number>`
- `/music clear`
- `/music disconnect`
- `/music playlist create name:<name>`
- `/music playlist add playlist:<name> query:<text-or-url>`
- `/music playlist list`
- `/music playlist show name:<name>`
- `/music playlist play name:<name>`
- `/music playlist remove name:<name> position:<number>`
- `/music playlist move name:<name> from-position:<number> to-position:<number>`
- `/music playlist rename name:<name> new-name:<new-name>`
- `/music playlist delete name:<name>`
- `/sound upload name:<name> file:<attachment> category:<optional> tags:<comma-separated>`
- `/sound play name:<name> interrupt:<boolean>`
- `/sound list filter:<text | category:name | tag:name>`
- `/sound info name:<name>`
- `/sound random`
- `/sound metadata name:<name> category:<optional> tags:<comma-separated>`
- `/sound rename name:<name> new-name:<new-name>`
- `/sound delete name:<name>`
- `/ai ask prompt:<text>`
- `/ai reset`
- `/ai summarize count:<number>`
- `/ai transcribe file:<attachment>`
- `/ai speak prompt:<text>`
- `/ai status`
- `/settings show`
- `/settings volume value:<0-100>`
- `/settings ai enabled:<boolean>`
- `/settings sounds max-count:<number> storage-mb:<number>`

The music panel provides pause/resume, skip, stop, and queue buttons, but every action remains
available as a slash command.

Directly mentioning `@ComradBot` in a server channel starts or continues that channel's bounded AI
conversation. Messages from bots are ignored, Discord IDs in mentions are sanitized before provider
submission, the reply does not ping the author again, and this behavior can be disabled with
`DISCORD_RESPOND_TO_MENTIONS=false`.

`/ai summarize` considers at most `MAX_AI_CONTEXT_MESSAGES` recent non-bot text messages, even when
a larger count is requested. It ignores attachments, does not add the transcript or result to the
channel's AI conversation memory, and applies the same local rate limits as `/ai ask`. `/ai status`
is ephemeral and reports provider availability, TTS availability, summary access, and local limits
without making an API request or displaying secrets.

`/ai transcribe` accepts FLAC, MP3, MP4, M4A, OGG, WAV, and WebM attachments. ComradBot checks the
declared size and MIME type, verifies the real media stream and duration with FFprobe, normalizes
speech to temporary mono 16 kHz FLAC, and sends only that temporary audio to Groq. The source and
normalized files are deleted after success or failure. Transcription shares the configured local AI
rate limits and permits only one active transcription per guild.

Members with Manage Server permission can use `/settings`. The default volume is applied whenever a
guild player is created; changing it also updates an active player immediately. Disabling AI blocks
slash commands and direct-mention conversations for that guild without affecting music or custom
sounds. These preferences are stored in SQLite and remain isolated by guild ID.

## AI persona

The default persona is a friendly, theatrical caricature inspired by communist characters from old
television series. It casually calls people “comrade” or “companheiro” and uses exaggerated
collective-workplace imagery for humor. It does not introduce political discussion, advocacy, or
persuasion unless a user explicitly brings up politics. The prompt lives separately in
`src/comradbot/ai/prompts.py` and can be replaced without changing command code.

Set `CUSTOM_COMRADBOT_PERSONA` in `.env` to replace the complete built-in persona for either Groq or
OpenAI. Keep a multiline prompt on one dotenv assignment, using `\n` for newlines and `\"` for
embedded double quotes:

```env
CUSTOM_COMRADBOT_PERSONA="You are a concise game-night assistant.\nCall users \"comrade\"."
```

An empty or whitespace-only value falls back to the built-in `COMRADBOT_PERSONA`; the two prompts
are not concatenated. Do not paste a raw, unquoted multiline prompt into `.env`, because dotenv will
interpret its subsequent lines as separate invalid assignments.

Generated speech uses only official provider voices. Groq currently provides TTS in English and
Saudi Arabic, so `/ai speak` is intentionally unavailable when Groq is selected; OpenAI remains the
Portuguese-capable TTS provider. The project does not support voice cloning or impersonation of real
people.

## Quality checks

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest
```

Tests use disposable databases and files plus fakes for external services. The default suite never
makes real Discord, Groq, OpenAI, or media-platform requests. Local FFmpeg integration tests generate
short WAV fixtures in memory to verify real probing, validation, cleanup, Opus conversion, and
speech-recognition FLAC normalization. Pytest measures branch coverage across `src/comradbot` and
fails below the current 70% project baseline.

GitHub Actions installs FFmpeg and runs the same installation, lint, formatting, type-checking, and
test commands on Python 3.12 and 3.13 for every pull request and push to `main`. The CI fails when
any test fails or aggregate branch coverage drops below the baseline. Python 3.12 runs also publish
the XML and browsable HTML coverage reports as a workflow artifact retained for 14 days. A separate
CodeQL workflow analyzes Python changes on pull requests, pushes to `main`, manual runs, and a weekly
schedule. Code scanning must be enabled in the repository settings for CodeQL results to appear
under the Security tab. To prevent merging a failing pull request, configure a GitHub branch
ruleset for `main` that requires the `Python 3.12` and `Python 3.13` status checks.
The CI also builds the non-root container image and smoke-tests Python, package imports, FFmpeg, and
FFprobe without publishing the image or using real credentials.

## Technical decisions

- **One player per guild:** `GuildAudioManager` is the only player registry. Music, custom sounds,
  and TTS all produce `AudioItem` objects for the same queue.
- **Priority without mixing:** music is appended normally; custom sounds and TTS can be inserted as
  the next item. Explicit interruption stops the current item. Simultaneous mixing was evaluated
  and intentionally rejected for the final single-source player: a PCM mixer would add continuous
  CPU work, buffering and synchronization failure modes for a private-server feature that already
  has deterministic priority insertion and interruption.
- **No automatic interrupted-stream resume:** reliable resume would require a playback clock that
  excludes pauses, source-specific seek capability, and renewed public stream URLs before passing a
  calculated offset to FFmpeg. Discord's playback callback does not report a trustworthy consumed
  position, and remote sources do not guarantee accurate seeking. Explicit interruption therefore
  discards the interrupted item; users can queue it again manually.
- **Internal Opus format:** accepted uploads are converted to 96 kbps Opus, which is compact and
  appropriate for Discord voice. Physical filenames use UUIDs; logical names remain in the database.
  Sounds may have one optional category and up to ten normalized tags. Autocomplete and `/sound list`
  accept normal text plus `category:<name>` and `tag:<name>` filters without exposing physical paths.
- **Per-guild sound quotas:** global defaults bound saved-sound count and converted Opus storage.
  Administrators can override both through `/settings sounds`. Uploads for the same guild are
  serialized, and quota checks run before processing and after conversion to prevent concurrent or
  size-estimation overruns.
- **Temporary streams:** the resolver gives ephemeral public stream URLs to FFmpeg and never stores
  third-party music permanently. Tracks that waited behind another item are re-resolved from their
  public page immediately before playback; a failed refresh is skipped without stopping the guild
  player. HTTP reconnect flags are applied only to these remote music streams; local custom sounds
  and TTS files use local-safe FFmpeg options. DRM bypass and private authentication are out of
  scope.
- **Persistent playlists:** playlists belong to one guild and store track titles, durations, and
  public source references only. Temporary stream URLs and media files are not persisted. Playlist
  playback resolves each reference again and reports tracks that are unavailable or do not fit in
  the current queue. Public platform-native playlist import was evaluated and intentionally omitted:
  extractor-specific collections have unstable metadata, potentially large request fan-out, and
  ambiguous partial-failure semantics. Users can save individually resolved public references, while
  the command and service layers remain independent of any one platform.
- **Optional AI providers:** Cogs and mention listeners depend on `AIService`, not a concrete SDK.
  Groq uses its official asynchronous SDK for text and attachment transcription; OpenAI supports
  text and Portuguese TTS. Usage
  records contain IDs, operation names, character counts, and outcomes—not full conversation
  content. Channel summaries fetch a bounded history only on demand and are not added to persistent
  conversation memory.
- **Persistent guild preferences:** `GuildSettingsService` is the only business-facing access point
  for server configuration. Discord commands do not execute SQL, and audio/AI consume the settings
  through injected async lookups.
- **Container liveness without a web server:** the connected bot updates a heartbeat under the data
  volume. Docker checks heartbeat freshness, SQLite, FFmpeg, and FFprobe without contacting Discord
  or an AI provider. Shutdown waits for pending writes before deleting the heartbeat.
- **Single-instance persistence:** Compose uses a named volume and SQLite for a simple private-server
  deployment. Multiple bot replicas are unsupported until persistence and distributed locks move to
  infrastructure designed for concurrent instances.
- **Local observability:** `/health` checks the Discord connection, SQLite, FFmpeg, and FFprobe, then
  reports non-sensitive uptime, latency, active-player, slash-command, and music-resolver counters.
  Initial resolutions and playback-time source refreshes expose separate success, failure, timeout,
  and average-latency metrics. Resolver logs classify inputs only as search text or URL and never
  include the query, resolved stream URL, database URL, tokens, or provider keys. Counters are
  bounded integers held in process memory and reset on restart.
- **Speech recognition boundary:** the initial implementation transcribes explicit attachments
  through Groq Whisper after local FFmpeg validation. It does not listen to voice channels. Live
  capture remains deferred because discord.py does not expose a stable receive API compatible with
  Discord's current DAVE voice protocol; it should be reassessed rather than built on an unmaintained
  receiver extension.
- **Agent documentation formatting:** Ruff excludes `AGENTS.md` from formatting because it is an
  instruction document containing illustrative snippets, not executable project code.
- **Migration-only schema lifecycle:** startup runs Alembic outside the event loop. Empty and
  versioned databases upgrade normally; only exact known legacy bootstrap schemas are stamped.
  Partial or modified unversioned schemas require operator review.
- **Voice control permissions:** mutating slash commands and player buttons require the member to
  share the bot's voice channel. Members with Move Members permission may control it from another
  voice channel; read-only queue views remain available without joining voice.

## Current limitations

- There is no simultaneous mixing or automatic resume after interruption; both were evaluated and
  intentionally excluded from the final single-source player design.
- Playlist playback resolves tracks sequentially and does not import platform-native playlists.
- Groq mode supports text conversations but not `/ai speak`; its hosted TTS models do not support
  Portuguese.
- Speech recognition works only with explicit attachments; the bot does not record or monitor voice
  channels. Groq free-plan quotas and the configured local limits still apply.
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
- **The bot connects but has no audio:** verify Connect/Speak permissions and channel user limits.
  If the log reports that `davey` is missing, reinstall with `python -m pip install -e ".[dev]"`;
  the declared `discord.py[voice]` dependency installs both the DAVE backend and compatible PyNaCl.
- **Music is unavailable:** private, protected, removed, or authenticated content is unsupported. Try
  another public source.
- **AI is disabled:** set `AI_PROVIDER=groq` with `GROQ_API_KEY`, or configure `OPENAI_API_KEY`.
  Music and custom sounds continue to work without either provider.
- **`/ai summarize` is disabled:** enable Message Content Intent in the Discord Developer Portal,
  set `DISCORD_MESSAGE_CONTENT_INTENT=true`, verify Read Message History permissions, and restart
  the bot.
- **Groq returns a quota error:** the free plan is rate-limited. Wait for the reported quota window
  to reset and keep the local AI limits enabled.
- **Transcription is unavailable:** select Groq with `AI_PROVIDER=groq`, configure `GROQ_API_KEY`,
  restart the bot, and verify that the attachment is within the configured size and duration limits.
- **An upload is rejected:** extension and MIME type are only initial checks; FFprobe must also detect
  real audio within the configured size and duration limits. Generic
  `application/octet-stream` attachments are accepted only as unknown metadata and still undergo
  full FFprobe validation before conversion.
- **Database migration fails:** stop the bot, back up `data/comradbot.db`, and run
  `alembic current` followed by `alembic upgrade head`. Do not delete or stamp a partial database
  without inspecting its schema and data first.
- **Container is unhealthy:** run `docker compose ps` and `docker compose logs comradbot`. Confirm
  that `/app/data` is writable, startup migrations completed, and the bot reached Discord before the
  health-check start period expired.
- **`/health` is degraded:** inspect which dependency is unavailable. Verify the Discord connection,
  FFmpeg/FFprobe on `PATH`, and SQLite file permissions before restarting the bot.
- **Many tests fail with `PermissionError` under `%TEMP%\pytest-of-<user>`:** the configured suite
  uses the repository-local `.pytest-tmp` directory to avoid broken Windows temporary-directory
  ACLs. Update the editable installation, run tests from the repository root, and do not store
  personal files in `.pytest-tmp` because pytest recreates it for each run.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes. Report vulnerabilities according to
[SECURITY.md](SECURITY.md), without opening a public issue for sensitive reports.

ComradBot is distributed under the [MIT License](LICENSE).
