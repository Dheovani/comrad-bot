# Changelog

All notable changes to ComradBot are documented in this file.

The project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Operations and security

- Added monthly Dependabot updates for Python, Docker, and GitHub Actions dependencies.
- Added scheduled Trivy scanning for high and critical container vulnerabilities with SARIF uploads.
- Added release metadata validation and checksummed Docker deployment bundles to release automation.

### Audio and music

- Added guild-scoped repeat modes for the current item and complete shared audio queue.
- Added permission-aware playlist renaming and atomic saved-track reordering.
- Added privacy-safe resolver outcome and latency metrics for initial resolution and source refresh.
- Documented final decisions to retain single-source playback, explicit requeue after interruption,
  and provider-neutral individual playlist references.

### Custom sounds

- Added optional sound categories, bounded normalized tags, metadata editing, and filter-aware
  listing and autocomplete.
- Added migration `0003` with safe adoption of existing versioned and legacy development databases.
- Added configurable per-guild sound count and converted-storage quotas with concurrency-safe upload
  enforcement and migration `0004`.
- Added persistent, guild-scoped audit records for custom sound renames and deletions, the
  moderator-only `/sound audit` command, and migration `0005`.
- Added moderator-only custom sound ZIP export and restore with a versioned manifest, SHA-256
  integrity checks, guild isolation, archive safety validation, and normal upload quota enforcement.

### Generative AI

- Added per-guild channel, user, server-wide, and stateless conversation scopes with configurable
  1-to-365-day retention, expiry cleanup, safe scope transitions, and migration `0006`.
- Evaluated Gemini and Anthropic as additional text providers and retained the existing Groq/OpenAI
  adapters: Gemini's free tier permits product-improvement use of submitted content, while Anthropic
  API access requires paid usage credits. No speculative SDK dependency was added.
- Added configurable per-guild daily AI request budgets, moderator-only aggregate `/ai usage`
  reporting without prompt content, concurrency-safe reservations, and migration `0007`.
- Added independently selectable ElevenLabs TTS using its official asynchronous SDK, Portuguese
  language enforcement, official voice IDs, bounded Opus output, finite retries, and cleanup on
  provider, quota, timeout, size-limit, and cancellation failures.
- Added read-only `/ai discover` recommendations grounded in a bounded, guild-local snapshot of the
  current queue and custom sound catalog, without granting the model playback or mutation actions.

## [1.0.0] — 2026-07-24

ComradBot 1.0.0 is the first complete release for private Discord servers. It delivers a shared
guild-scoped audio system, music playback, managed custom sounds, generative AI, speech features,
persistence, automated quality checks, observability, and container deployment.

### Discord and application foundation

- Added an installable Python 3.12 package with typed `pydantic-settings` configuration.
- Added automatic Cog loading and development-guild or global slash-command synchronization.
- Added centralized contextual logging, sanitized command errors, graceful resource shutdown, and
  `/help`, `/ping`, and `/health`.
- Limited Discord intents and documented minimum permissions without requiring Administrator.

### Audio and music

- Added one isolated `GuildAudioPlayer` per Discord guild with a concurrency-safe heterogeneous
  queue shared by music, custom sounds, and TTS.
- Added pause, resume, skip, stop, queue inspection, current-track display, volume, removal, clear,
  disconnect, idle timeout, and an expiring button control panel.
- Added safe FFmpeg and FFprobe execution without shell interpolation.
- Added a platform-neutral `AudioResolver` backed by `yt-dlp` for temporary public streams.
- Added playback-time source refresh, sanitized resolver failures, and automatic progression past
  unavailable tracks.
- Added persistent guild playlists that store public references rather than temporary stream URLs or
  third-party media.

### Custom sounds

- Added upload, playback, listing, details, random selection, rename, deletion, and autocomplete.
- Added defensive extension, MIME, size, duration, real-content, logical-name, ownership, and path
  validation.
- Added FFprobe inspection and normalized 96 kbps Opus storage under guild-specific UUID paths.
- Added persistent metadata and playback counters with creator-or-moderator modification rules.

### Generative AI and speech

- Added provider-neutral AI and speech abstractions with asynchronous OpenAI and Groq adapters.
- Added `/ai ask`, `/ai reset`, `/ai summarize`, `/ai status`, `/ai speak`, and `/ai transcribe`.
- Added bounded per-channel conversation memory and direct conversational replies when the bot is
  mentioned.
- Added configurable persona overrides through `CUSTOM_COMRADBOT_PERSONA`.
- Added user and guild rate limits, cooldowns, context and response limits, timeouts, bounded
  concurrency, sanitized provider errors, and metadata-only usage records.
- Added OpenAI TTS through the shared guild player with temporary-file cleanup.
- Added Groq Whisper transcription for validated attachments normalized to mono 16 kHz FLAC.
- Allowed Groq transcription to operate independently when OpenAI is selected for text and TTS.

### Persistence and server settings

- Added async SQLite persistence with SQLAlchemy 2 repositories.
- Added models for guild settings, custom sounds, AI conversations, AI usage, playlists, and saved
  track references.
- Added controlled Alembic startup migrations, including safe adoption of known legacy development
  schemas and rejection of unknown partial schemas.
- Added persistent per-guild default volume and AI availability settings.

### Quality, security, and observability

- Added deterministic unit and integration tests with fakes for Discord, voice, resolvers, AI
  providers, repositories, and media processing.
- Added real local FFmpeg integration coverage without external Discord, AI, or media-platform calls.
- Added Ruff formatting and linting, strict mypy checks, pytest-asyncio, and branch coverage with a
  70% minimum baseline.
- Added GitHub Actions checks for Python 3.12 and 3.13, coverage artifacts, CodeQL, and container
  builds.
- Added in-process uptime, latency, command, and active-player metrics plus dependency health
  reporting.
- Added bounded file handling, guild isolation, permission validation, secret-safe logs, and
  defensive temporary-file cleanup.

### Deployment

- Added a non-root Docker image containing Python, FFmpeg, FFprobe, voice dependencies, and migration
  assets.
- Added Docker Compose with a persistent named volume for SQLite, custom sounds, and runtime data.
- Added heartbeat-based container health checks that avoid external Discord or AI requests.
- Added documentation for local installation, Docker operation, data import, updates, backups,
  troubleshooting, and current single-instance SQLite constraints.

### Known limitations

- Interrupted music is not resumed automatically, and simultaneous audio mixing is not supported.
- Platform-native playlist import and permanent third-party music caching are not supported.
- Live voice-channel recognition is deferred until discord.py exposes a stable receive API compatible
  with Discord DAVE.
- Groq-hosted TTS is not used for Portuguese speech; `/ai speak` currently requires OpenAI.
- SQLite deployment supports one running ComradBot instance.
