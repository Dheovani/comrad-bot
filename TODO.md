# ComradBot future roadmap

ComradBot 1.0.0 delivery history is recorded in [CHANGELOG.md](CHANGELOG.md). This file contains only
unimplemented evolution opportunities. Items remain intentionally unordered until a release scope is
selected.

## Audio and music evolution

- [ ] Add repeat modes for the current track and complete queue
- [ ] Evaluate automatic resume for interrupted seekable tracks
- [ ] Evaluate optional simultaneous mixing with explicit resource limits
- [ ] Add playlist reordering and playlist metadata editing
- [ ] Evaluate platform-native playlist import without storing third-party media
- [ ] Add resolver observability for provider failures and source-refresh latency

## Custom sound evolution

- [ ] Add optional categories, tags, and richer autocomplete filters
- [ ] Add configurable per-guild sound count and storage quotas
- [ ] Add moderator audit records for rename and deletion operations
- [ ] Add bulk export and restore tools for guild-owned custom sounds

## AI and voice evolution

- [ ] Add configurable conversation scope and retention policies per guild
- [ ] Add per-guild AI budgets and usage summaries without storing prompt content
- [ ] Evaluate additional concrete providers only when they offer a clear cost or capability benefit
- [ ] Reassess live voice recognition when discord.py provides stable DAVE-compatible audio receive
- [ ] Evaluate Portuguese-capable non-OpenAI TTS providers with official voices
- [ ] Add optional AI-assisted queue and sound discovery without autonomous playback

## Discord experience

- [ ] Add localization infrastructure for English and Brazilian Portuguese responses
- [ ] Expand player panels with pagination and persistent state refresh
- [ ] Evaluate polls, event planning, game-night scheduling, and lightweight social utilities
- [ ] Add per-guild command feature flags where operationally useful

## Persistence and scale

- [ ] Add tested PostgreSQL support before allowing multiple bot replicas
- [ ] Add distributed coordination for guild players, rate limits, and scheduled work
- [ ] Add automated encrypted backups and documented restoration verification
- [ ] Define explicit data-retention and deletion controls for each persisted domain

## Operations and releases

- [ ] Publish the prepared versioned multi-platform container image through the GitHub 1.0.0 release
- [ ] Add container vulnerability scanning and dependency update automation
- [ ] Add changelog validation and non-container build artifacts to the release workflow
- [ ] Add external monitoring integration for long-running hosted deployments
- [ ] Document one supported 24/7 hosting target with persistent-volume requirements

## Deliberately uncommitted ideas

- [ ] Reassess economy or XP systems only if the server explicitly wants them
- [ ] Keep advanced moderation outside scope unless a concrete server need emerges
