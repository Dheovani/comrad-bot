# Technical decisions

This document records ComradBot's architectural boundaries and important tradeoffs. Operational
setup belongs in the README and the dedicated hosting guide.

## Audio

### One player per guild

`GuildAudioManager` is the only active-player registry. Music, custom sounds, and TTS become
`AudioItem` objects and pass through the same guild-scoped queue. State and synchronization never
cross guild boundaries.

### Priority without simultaneous mixing

Music is appended normally; custom sounds and TTS may be inserted next. Explicit interruption stops
the current item. A PCM mixer was rejected because continuous CPU use, buffering, synchronization,
and failure handling were disproportionate for a private-server bot with deterministic priority
insertion.

### No automatic resume after interruption

Reliable resume needs a playback clock excluding pauses, seekable sources, refreshed stream URLs,
and trustworthy consumed-position reporting. Discord playback callbacks and remote sources do not
provide those guarantees, so interrupted items must be queued again explicitly.

### Safe FFmpeg boundary

FFmpeg and FFprobe invocation is centralized and uses argument lists without shell interpolation.
Remote reconnect flags apply only to temporary music streams. Local sounds and TTS use local-safe
options. Blocking resolver work runs outside the event loop with timeouts.

### Temporary music streams and playlists

The resolver supplies ephemeral public stream URLs and never persists third-party media. Queued
tracks are refreshed before playback. Persistent playlists store titles, durations, and public
source references—not temporary URLs or media files. Platform-native playlist import remains
omitted because provider collections have unstable metadata, unbounded fan-out, and ambiguous
partial failures.

## Custom sounds

### Internal format and physical storage

Accepted uploads are inspected with FFprobe and converted to 96 kbps Opus. Physical filenames use
UUIDs under a guild directory; user-provided logical names remain only in the database. This avoids
path traversal, executable uploads, accidental overwrite, and unsafe filename reuse.

### Metadata, quotas, and concurrency

Sounds may have one category and up to ten normalized tags. Global defaults bound count and storage,
while administrators can configure guild overrides. Uploads for one guild are serialized and quotas
are checked before processing and after conversion.

### Audit records

Rename and deletion audit records are committed with their database changes. They contain guild,
sound, actor, owner, action, names, and timestamps but no paths or message content. Records remain
after a sound is deleted.

### Portable archives

Exports contain a versioned JSON manifest, normalized Opus files, and SHA-256 checksums. Restore
validates all paths and entries without extracting untrusted filenames, restricts archives to the
origin guild, and routes every sound through normal validation and quota enforcement. Restore is
incremental and reports imported, skipped, and failed entries.

## AI and speech

### Provider-neutral services

Discord adapters depend on `AIService` and provider protocols, not concrete SDKs. Groq supplies text
and attachment transcription; OpenAI supplies optional text and TTS; ElevenLabs supplies optional
TTS through official premade voices. Provider errors are mapped to safe application errors.

### Provider selection

Groq remains the free text and transcription path. OpenAI remains an optional paid text and
Portuguese TTS route. ElevenLabs was added as a specialized Portuguese-capable TTS adapter. Gemini
was not added because free-tier content may be used for product improvement; Anthropic was not added
because API usage requires paid credits. Another provider should be added only for a material
capability, cost, or privacy improvement.

Relevant evaluation sources:

- [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Google Gen AI SDK](https://googleapis.github.io/python-genai/)
- [Anthropic API billing](https://support.anthropic.com/en/articles/8977456-how-do-i-pay-for-my-api-usage)
- [Groq rate limits](https://console.groq.com/docs/rate-limits)
- [ElevenLabs API pricing](https://help.elevenlabs.io/hc/en-us/articles/28184926326033-How-much-does-it-cost-to-use-the-API)

### Conversation privacy

Each guild selects channel, user, server, or stateless conversation scope plus bounded retention.
Stored keys include scope type to avoid Discord ID collisions. Requests sharing a context are
serialized. Expired records are removed, and changing scope invalidates in-flight persistence before
deleting old memory.

### Limits, budgets, and usage

AI requests have bounded prompts, context, responses, concurrency, timeouts, cooldowns, per-minute
limits, and optional daily guild budgets. Usage records store identifiers, operation types,
character counts, outcomes, and timestamps—not prompts, responses, attachments, or keys. Reports use
requests and characters rather than provider-independent token or currency estimates.

### Read-only discovery

AI discovery receives a bounded guild-local projection of queue and sound metadata. The provider
gets no executable tool or callback, so recommendations cannot play or mutate audio. Stream URLs,
paths, media files, and requester IDs are excluded.

### Speech-recognition boundary

Transcription accepts explicit validated attachments, normalizes them to temporary mono 16 kHz FLAC,
and sends only that file to Groq Whisper. ComradBot does not listen to voice channels. Live capture
is deferred until discord.py exposes stable receive support compatible with Discord DAVE.

## Persistence and Discord

### Repositories and migrations

Discord commands never execute SQL. Services use repositories backed by SQLAlchemy async sessions.
Startup runs Alembic outside the event loop. Empty and versioned databases migrate normally; only
exact known legacy schemas are adopted automatically. Partial or modified unversioned schemas
require operator review.

### Single-instance SQLite

SQLite and in-memory guild coordination intentionally support one process. Multiple replicas remain
unsupported without shared persistence and distributed locks for players, rate limits, and scheduled
work.

### Persistent guild settings and feature flags

`GuildSettingsService` is the business-facing configuration boundary. Settings are isolated by guild
ID and injected into audio and AI services. Disabled slash groups remain visible because the command
tree is shared, but their operations are rejected safely.

### Localization

English and Brazilian Portuguese catalogs use `discord.app_commands.Translator` during command
synchronization and the same validated catalogs at runtime. Unsupported locales use the configured
default. Command names stay stable in English. Missing command-description translations retain the
English source text; mismatched runtime keys fail during startup.

### Voice controls and persistent panels

Mutating commands and buttons require the user to share the bot's voice channel unless they have
Move Members permission. Persistent component IDs restore callbacks after restart without storing a
duplicate queue snapshot. Every interaction reads live player state and applies the same permission
rules as slash commands.

### Native social polls

Game-night planning uses Discord-native polls rather than a custom vote database. Scheduled-event
automation was deferred because it requires Manage Events and an additional lifecycle policy while
Discord already provides moderator-managed events.

## Operations and observability

### Local health without a web server

The connected bot refreshes a heartbeat in the data volume. Docker validates its freshness, SQLite,
FFmpeg, and FFprobe without contacting Discord or AI providers. `/health` reports non-sensitive
Discord, database, audio-tool, uptime, latency, player, command, and resolver state.

### Resolver observability

Initial resolution and playback-time refresh have separate success, failure, timeout, and latency
counters. Logs classify inputs only as search text or URL and never include queries, stream URLs,
database URLs, tokens, or provider keys. Counters are bounded and reset on restart.

### YouTube challenge solving and stream headers

The yt-dlp Python installation includes its matching EJS components and the container includes Deno,
the runtime recommended by yt-dlp for YouTube JavaScript challenges. Resolved media remains a
temporary stream. The resolver retains only a small allowlist of non-secret HTTP headers required by
the media endpoint; cookies and authorization headers are never forwarded or logged. FFmpeg receives
arguments without a shell, and queued tracks refresh both their URL and headers before playback.

### External heartbeat

An optional operator-provided HTTPS URL enables a dead-man's-switch heartbeat compatible with
Healthchecks.io. Redirects are disabled, timeouts are bounded, delivery failures are non-fatal, and
the secret URL is never logged. This complements rather than replaces Docker's dependency health
check.

### Container and release model

The container runs as a non-root user and stores mutable data only in `/app/data`. Production Compose
uses one named volume and one replica. Stable GitHub Releases build AMD64 and ARM64 images, publish
semantic tags to Docker Hub, attach provenance and an SBOM, and upload a checksummed deployment
bundle.

### Agent-document formatting

Ruff excludes `AGENTS.md` because it is an instruction document containing illustrative snippets,
not executable source documentation.
