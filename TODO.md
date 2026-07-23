# ComradBot roadmap

This file tracks implemented and verified work only. Mark an item complete after it passes the
checks appropriate to its risk.

## Phase 1 — Project foundation

- [x] Create an installable `src/comradbot` package
- [x] Add typed environment configuration and validation
- [x] Add centralized contextual logging and global command error handling
- [x] Initialize the bot, load Cogs, and sync development commands
- [x] Verify `ffmpeg` and `ffprobe` during startup
- [x] Configure async SQLite, SQLAlchemy 2, and controlled development schema bootstrap
- [x] Add Alembic configuration and an initial migration

## Phase 2 — Audio system

- [x] Model heterogeneous audio items and next-item priority
- [x] Enforce one isolated player per Discord guild
- [ ] Fully test connection, volume, pause, resume, skip, stop, and cleanup transitions
- [ ] Fully test automatic inactivity disconnect
- [x] Invoke FFmpeg without unsafe user-input command concatenation
- [x] Add a basic expiring player control panel

## Phase 3 — Music

- [x] Define a platform-neutral source resolver abstraction
- [x] Resolve temporary public streams with timeouts outside the event loop
- [x] Implement `/music play`, `pause`, `resume`, `skip`, `stop`, and `queue`
- [ ] Implement `now`, `volume`, `remove`, `clear`, and `disconnect`
- [ ] Harden channel-control permissions for commands and buttons
- [ ] Add persistent playlists and saved tracks

## Phase 4 — Custom sounds

- [ ] Add end-to-end tests for name, extension, MIME, size, content, and duration validation
- [ ] Add end-to-end tests for FFmpeg conversion to the internal format
- [x] Store files per guild with UUIDs and safe relative paths
- [x] Persist metadata and playback counts
- [x] Implement `/sound upload`, `play`, `list`, and `delete`
- [ ] Implement `info`, `random`, `rename`, and autocomplete

## Phase 5 — Generative AI

- [x] Define `AIProvider` without coupling commands to a concrete SDK
- [x] Implement an async OpenAI provider and replaceable persona
- [x] Implement bounded memory plus `/ai ask` and `/ai reset`
- [x] Add user/guild limits, cooldown, timeout, and content-free usage metrics
- [ ] Implement `/ai summarize` and `/ai status`
- [ ] Prepare support for additional concrete providers when needed

## Phase 6 — TTS and AI/voice integration

- [x] Generate short responses and speech with an official provider voice
- [x] Queue TTS through the shared player and clean its temporary file
- [x] Implement `/ai speak` with per-guild concurrency limits
- [x] Document that interrupted media is not resumed in the MVP
- [ ] Evaluate future speech recognition without voice cloning

## Phase 7 — Persistence and guild settings

- [x] Model `GuildSettings`, `CustomSound`, `AIConversation`, and `AIUsage`
- [x] Add repositories so Cogs never execute SQL
- [ ] Add persistent per-guild configuration
- [ ] Require Alembic migrations for schema evolution after the MVP

## Phase 8 — Tests and observability

- [x] Test queue ordering, priority, limits, removal, and cleanup
- [x] Test sound names, metadata validation, and safe paths
- [x] Test cooldowns, context limits, and long-response splitting
- [x] Test repositories against disposable SQLite databases
- [ ] Expand fake-based tests for temporary file creation and failure cleanup
- [x] Run Ruff, mypy, and pytest across the project
- [ ] Add coverage reporting, metrics, health checks, and CI

## Phase 9 — Deployment

- [x] Document local execution and minimum Discord permissions
- [ ] Create a container image with no embedded secrets
- [ ] Define persistent volumes for the database and custom sounds
- [ ] Automate migrations and readiness checks

## Phase 10 — Future social features

- [ ] Research social tools appropriate for the server
- [ ] Keep future modules decoupled from audio players and AI providers
- [ ] Evaluate polls, events, and lightweight utilities
- [ ] Keep economy, XP, and advanced moderation outside the current scope
