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

- [ ] Add optional categories, tags, and richer autocomplete filters
- [ ] Add configurable per-guild sound count and storage quotas
- [ ] Add moderator audit records for rename and deletion operations
- [ ] Add bulk export and restore tools for guild-owned custom sounds

## 3. AI and voice evolution

- [ ] Add configurable conversation scope and retention policies per guild
- [ ] Add per-guild AI budgets and usage summaries without storing prompt content
- [ ] Evaluate additional concrete providers only when they offer a clear cost or capability benefit
- [ ] Reassess live voice recognition when discord.py provides stable DAVE-compatible audio receive
- [ ] Evaluate Portuguese-capable non-OpenAI TTS providers with official voices
- [ ] Add optional AI-assisted queue and sound discovery without autonomous playback

## 4. Discord experience

- [ ] Add localization infrastructure for English and Brazilian Portuguese responses
- [ ] Expand player panels with pagination and persistent state refresh
- [ ] Evaluate polls, event planning, game-night scheduling, and lightweight social utilities
- [ ] Add per-guild command feature flags where operationally useful

## 5. Persistence and scale

- [ ] Add tested PostgreSQL support before allowing multiple bot replicas
- [ ] Add distributed coordination for guild players, rate limits, and scheduled work
- [ ] Add automated encrypted backups and documented restoration verification
- [ ] Define explicit data-retention and deletion controls for each persisted domain

## 6. Operations and releases

- [x] Publish the prepared versioned multi-platform container image through the GitHub 1.0.0 release
- [x] Add container vulnerability scanning and dependency update automation
- [x] Add changelog validation and a checksummed Docker deployment bundle to the release workflow
- [ ] Add external monitoring integration for long-running hosted deployments
- [ ] Document one supported 24/7 hosting target with persistent-volume requirements
