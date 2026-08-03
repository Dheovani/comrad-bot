# ComradBot future roadmap

ComradBot 1.0.0 delivery history is recorded in [CHANGELOG.md](CHANGELOG.md). This file contains only
unimplemented evolution opportunities. Items remain intentionally unordered until a release scope is
selected.

## 1. Audio and music evolution

- [x] Add repeat modes for the current track and complete queue
- [x] Evaluate automatic resume for interrupted seekable tracks; retain explicit requeue semantics
- [x] Evaluate optional simultaneous mixing; retain the bounded single-source player
- [x] Add playlist reordering and playlist metadata editing
- [x] Evaluate platform-native playlist import; retain provider-neutral individual references
- [x] Add resolver observability for provider failures and source-refresh latency

## 2. Custom sound evolution

- [x] Add optional categories, tags, and richer autocomplete filters
- [x] Add configurable per-guild sound count and storage quotas
- [x] Add moderator audit records for rename and deletion operations
- [x] Add bulk export and restore tools for guild-owned custom sounds

## 3. AI and voice evolution

- [x] Add configurable conversation scope and retention policies per guild
- [x] Add per-guild AI budgets and usage summaries without storing prompt content
- [x] Evaluate additional concrete providers; retain Groq and OpenAI until another option offers a clear net cost, privacy, or capability benefit
- [ ] Reassess live voice recognition when discord.py provides stable DAVE-compatible audio receive
- [x] Add Portuguese-capable ElevenLabs TTS with official premade voices and a bounded free-tier path
- [x] Add bounded AI-assisted queue and sound discovery without autonomous playback

## 4. Discord experience

- [x] Add packaged localization infrastructure for English and Brazilian Portuguese responses
- [x] Expand player panels with bounded pagination and persistent state refresh
- [x] Add native Discord polls for game-night planning; defer scheduled-event automation until it offers enough value to justify Manage Events access
- [x] Add persistent per-guild command feature flags for music, sounds, AI, and social utilities

## 5. Operations and releases

- [x] Publish the prepared versioned multi-platform container image through the GitHub 1.0.0 release
- [x] Add container vulnerability scanning and dependency update automation
- [x] Add changelog validation and a checksummed Docker deployment bundle to the release workflow
- [x] Add optional secret-safe external heartbeat monitoring for long-running deployments
- [x] Document a single-replica Ubuntu 24.04 LTS Docker Compose target with persistent storage
