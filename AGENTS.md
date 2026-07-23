# AGENTS.md

## 1. Purpose

This file defines the working rules for AI coding agents and human contributors working on **ComradBot**.

ComradBot is a Discord bot for a private group of friends who play games together. Its primary capabilities are:

1. Music playback in Discord voice channels;
2. Custom sound upload, management, and playback;
3. Generative AI interactions;
4. Text-to-speech responses integrated with the shared audio system;
5. Social and utility features added incrementally.

Agents must treat this document as a project-level instruction set. When repository code and this document disagree, inspect the current implementation carefully and preserve intentional architectural decisions unless the task explicitly requires changing them.

---

## 2. Language Policy

All project documentation must be written in **English**.

This includes, but is not limited to:

- `README.md`;
- `AGENTS.md`;
- `TODO.md`;
- architecture decision records;
- code comments that explain non-obvious behavior;
- public docstrings;
- setup instructions;
- migration notes;
- release notes;
- troubleshooting guides.

User-facing Discord messages may be localized later. Unless a feature explicitly introduces localization, use consistent English copy in the codebase.

Commit messages should preferably be written in English.

---

## 3. Core Engineering Principles

Agents must follow these principles:

- Inspect before changing.
- Preserve working code.
- Prefer small, reviewable changes.
- Keep Discord command handlers thin.
- Keep business logic independent from Discord where practical.
- Avoid speculative abstractions.
- Avoid global mutable state.
- Do not block the event loop.
- Do not hide failures.
- Do not expose secrets.
- Test behavior, not implementation details.
- Update documentation when behavior changes.
- Update `TODO.md` only when work is actually completed.

Do not replace existing architecture merely because another approach is personally preferred. Refactor only when there is a concrete benefit for correctness, maintainability, security, or testability.

---

## 4. Expected Technology Stack

The intended stack is:

- Python 3.12 or newer;
- `discord.py`;
- `discord.app_commands` for slash commands;
- `asyncio`;
- FFmpeg and FFprobe;
- PyNaCl for Discord voice support;
- SQLAlchemy 2 with async support;
- SQLite for local development;
- Alembic for migrations;
- `pydantic-settings`;
- the current official OpenAI Python SDK;
- `pytest`;
- `pytest-asyncio`;
- Ruff;
- mypy.

Do not introduce another dependency manager unless explicitly requested. The project must remain compatible with:

```bash
python -m pip install -e ".[dev]"
```

Dependencies must be declared in `pyproject.toml`.

Every new dependency requires a clear justification.

---

## 5. Repository Inspection Rules

Before making changes:

1. Inspect the repository tree.
2. Read `README.md`, `AGENTS.md`, `TODO.md`, and `pyproject.toml`.
3. Inspect related source files and tests.
4. Identify existing abstractions before creating new ones.
5. Check whether the requested behavior is already partially implemented.
6. Review configuration and environment variables.
7. Verify current coding and naming conventions.
8. Review recent TODO items and unfinished work.

Do not assume the repository is empty.

Do not recreate files blindly.

Do not delete or rewrite unrelated code.

---

## 6. Target Project Structure

The expected structure is approximately:

```text
comrad-bot/
├── src/
│   └── comradbot/
│       ├── __init__.py
│       ├── __main__.py
│       ├── bot.py
│       ├── config.py
│       ├── logging.py
│       ├── commands/
│       │   ├── general.py
│       │   ├── music.py
│       │   ├── sounds.py
│       │   └── ai.py
│       ├── audio/
│       │   ├── models.py
│       │   ├── player.py
│       │   ├── queue.py
│       │   ├── resolver.py
│       │   ├── ffmpeg.py
│       │   └── manager.py
│       ├── ai/
│       │   ├── models.py
│       │   ├── provider.py
│       │   ├── openai_provider.py
│       │   ├── conversation.py
│       │   └── prompts.py
│       ├── sounds/
│       │   ├── service.py
│       │   ├── storage.py
│       │   └── validation.py
│       ├── database/
│       │   ├── models.py
│       │   ├── session.py
│       │   └── repositories/
│       ├── services/
│       ├── ui/
│       └── utils/
├── tests/
├── data/
│   └── .gitkeep
├── .env.example
├── .gitignore
├── AGENTS.md
├── TODO.md
├── README.md
└── pyproject.toml
```

This layout may evolve when justified, but the following concerns must remain separated:

- Discord command handling;
- business rules;
- audio playback;
- music source resolution;
- AI providers;
- conversation state;
- file storage;
- persistence;
- configuration;
- infrastructure;
- Discord UI components.

---

## 7. Architecture Boundaries

### 7.1 Discord command layer

Command modules and Cogs should:

- validate Discord-specific input;
- check permissions;
- defer interactions when operations may take time;
- invoke application services;
- translate domain errors into user-facing messages;
- build embeds, views, and responses.

Command modules must not:

- execute SQL directly;
- invoke FFmpeg command construction directly;
- call OpenAI directly;
- contain queue implementation details;
- manipulate storage paths directly;
- contain large business workflows.

Prefer code such as:

```python
result = await music_service.enqueue(...)
await interaction.followup.send(embed=build_track_embed(result))
```

Avoid code where the command performs resolution, persistence, queue mutation, and playback itself.

### 7.2 Service layer

Services coordinate use cases.

Examples:

- enqueueing a track;
- uploading and validating a custom sound;
- deleting a sound and its file;
- generating an AI response;
- generating TTS and adding it to the audio queue;
- resetting a conversation;
- summarizing recent messages.

Services may depend on repositories, providers, storage abstractions, and domain components.

### 7.3 Domain and infrastructure

Domain code should remain independent from Discord where practical.

Infrastructure code includes:

- Discord voice clients;
- FFmpeg;
- FFprobe;
- OpenAI;
- yt-dlp or another source resolver;
- SQLAlchemy;
- filesystem storage.

Wrap infrastructure behind explicit interfaces or focused classes when substitution is useful for testing or future providers.

Do not create interfaces for trivial code with no realistic alternative or testability benefit.

---

## 8. Async Programming Rules

ComradBot is asynchronous. Protect the event loop.

Never perform these operations directly on the event loop when they may block:

- synchronous HTTP requests;
- CPU-heavy media processing;
- FFmpeg or FFprobe calls that wait synchronously;
- yt-dlp resolution;
- large filesystem operations;
- synchronous database drivers;
- long-running parsing.

Use suitable approaches such as:

- async SDK methods;
- async subprocess APIs;
- `asyncio.to_thread`;
- bounded background tasks;
- timeouts;
- semaphores.

Every external operation must have a reasonable timeout.

Do not create unlimited concurrent tasks.

Do not use untracked `asyncio.create_task()` calls without lifecycle management and error handling.

When creating background tasks:

- retain a reference when necessary;
- handle cancellation;
- log unexpected exceptions;
- clean them up during shutdown.

---

## 9. Audio Architecture

Audio is a shared subsystem.

There must be at most one active audio player per Discord guild.

Use a guild-scoped manager, such as `GuildAudioManager`, indexed by guild ID.

Each guild player should own:

- the Discord voice connection;
- the current audio item;
- the queue;
- playback state;
- pause and resume behavior;
- volume;
- loop or repeat state when implemented;
- inactivity handling;
- cleanup logic;
- synchronization primitives;
- playback error handling.

Guild state must never leak into another guild.

### 9.1 Shared queue

Music, custom sounds, and TTS must use the same playback infrastructure.

Use an explicit item type, for example:

```python
class AudioItemType(StrEnum):
    MUSIC = "music"
    CUSTOM_SOUND = "custom_sound"
    TTS = "tts"
```

Do not implement unrelated voice players for each feature.

The shared queue should support priority rules without becoming an unbounded general-purpose scheduler.

Initial policy:

- music is appended normally;
- custom sounds may be inserted as the next item;
- TTS may be inserted as the next item;
- explicit interruption may stop the current item;
- interrupted streams do not need automatic resume in the initial version.

Document limitations clearly.

### 9.2 Concurrency

Queue mutation and playback transitions must be concurrency-safe.

Protect operations that may race:

- enqueue;
- skip;
- stop;
- disconnect;
- playback completion callbacks;
- automatic inactivity disconnect;
- queue clear;
- current-item replacement.

Use `asyncio.Lock`, events, or another clear synchronization mechanism where necessary.

Avoid deadlocks by keeping lock scopes small and not awaiting unrelated network operations while holding a lock.

### 9.3 FFmpeg

FFmpeg invocation must be centralized.

Do not build shell commands by concatenating untrusted strings.

Prefer argument lists and safe subprocess handling.

The application must verify that both `ffmpeg` and `ffprobe` are available during startup or before the first relevant operation.

Failures must produce actionable messages.

Temporary files must be deleted reliably, including failure and cancellation paths.

---

## 10. Music Source Resolution

Music commands must depend on a source resolver abstraction.

Example responsibilities:

- accept a search query or URL;
- resolve metadata;
- provide a temporary streamable source;
- normalize duration and title;
- return enough information for playback;
- raise typed errors.

Command handlers and the audio player must not depend directly on yt-dlp or any specific platform.

Blocking resolver work must run outside the event loop.

Do not implement:

- DRM circumvention;
- authentication bypass;
- private-content access;
- permanent downloading of third-party music;
- evasion of platform restrictions.

Temporary metadata and files must be cleaned up.

A failed track must not crash the guild player. Log the failure, notify the relevant channel when possible, and continue to the next queued item.

---

## 11. Custom Sound Rules

Custom sound uploads must be validated defensively.

Validate:

- filename;
- logical sound name;
- extension;
- MIME type when available;
- file size;
- actual media format;
- duration;
- guild ownership;
- user permissions;
- duplicate normalized names.

Never trust only the attachment extension.

Use FFprobe to inspect actual media properties.

Convert accepted uploads to a consistent internal format using FFmpeg.

Physical filenames must use safe generated identifiers, such as UUIDs.

Do not use a user-provided sound name as the physical filename.

Recommended layout:

```text
data/sounds/<guild_id>/<sound_id>.<internal_extension>
```

Prevent:

- path traversal;
- absolute path injection;
- directory escape;
- accidental overwrite;
- executable uploads;
- oversized files;
- unsupported formats.

Store paths relative to the configured data directory.

Deletion must account for partial inconsistency between the database and filesystem.

Log inconsistency without exposing internal paths to users.

---

## 12. AI Provider Architecture

AI features must depend on an abstraction, not directly on a concrete SDK.

A minimal conceptual interface may include:

```python
class AIProvider(Protocol):
    async def generate_response(self, request: AIRequest) -> AIResponse:
        ...

    async def generate_speech(self, request: SpeechRequest) -> SpeechResult:
        ...
```

The initial provider may use OpenAI.

Provider-specific request construction, error mapping, model naming, and response extraction belong inside the provider implementation.

Commands must not import or instantiate the OpenAI client directly.

The application must still start and provide non-AI features when no AI API key is configured.

In that situation, AI commands should return a clear feature-disabled message.

---

## 13. AI Conversation and Context Rules

Conversation scope must be explicit.

Choose and document whether context is stored per:

- user;
- channel;
- guild;
- thread;
- a combination of these.

Do not store unlimited conversation history.

Enforce:

- maximum prompt length;
- maximum context messages;
- maximum response length;
- request timeout;
- user cooldown;
- guild-level rate limits;
- bounded concurrency;
- finite retry policies.

Do not store complete message content in usage logs unless explicitly required and documented.

Usage records should favor metadata such as:

- guild ID;
- user ID;
- provider;
- model;
- operation type;
- estimated or reported token usage;
- status;
- timestamp;
- latency.

Do not expose:

- system prompts;
- provider keys;
- raw provider responses containing internal metadata;
- stack traces;
- hidden configuration.

---

## 14. TTS Rules

TTS is part of the shared audio system.

The expected flow is:

1. validate the request;
2. generate or obtain the textual response;
3. generate speech through the configured AI provider;
4. store the result in a temporary file;
5. enqueue it as `AudioItemType.TTS`;
6. play it through the guild audio player;
7. delete the temporary file after use.

TTS generation must be rate-limited and concurrency-limited.

Use only provider-supported voices.

Do not implement voice cloning or imitation of real people.

Do not retain generated speech files permanently unless a future feature explicitly requires it.

---

## 15. ComradBot Persona

The ComradBot persona should be stored separately from command code.

The default personality should be:

- humorous;
- slightly dramatic;
- friendly;
- appropriate for a private group of friends;
- occasionally themed around “comrades”;
- not reduced to a repetitive caricature;
- not hostile toward specific members;
- not impersonating a real person;
- not claiming consciousness, feelings, or a human identity.

The persona must be replaceable through configuration or a prompt file.

Do not hardcode long system prompts inside command handlers.

---

## 16. Database Rules

Use SQLAlchemy 2 async APIs.

Command handlers must not execute SQL.

Use repositories or focused persistence services.

Store Discord snowflakes as integer-compatible values.

Do not persist Discord library objects.

Initial entities may include:

- `GuildSettings`;
- `CustomSound`;
- `AIConversation`;
- `AIUsage`;
- future `Playlist`;
- future `SavedTrack`.

Schema changes must use Alembic once migrations are established.

Do not silently modify production schemas at runtime.

SQLite is the initial development database, but code should avoid unnecessary SQLite-only assumptions when practical.

Transactions must be explicit for multi-step writes.

Repositories should not leak SQLAlchemy implementation details into the command layer.

---

## 17. Configuration Rules

Configuration must use `pydantic-settings`.

Environment variables must be documented in `.env.example`.

Never commit real credentials.

Expected settings include:

```env
DISCORD_TOKEN=
DISCORD_GUILD_ID=
DISCORD_SYNC_GLOBAL_COMMANDS=false

DATABASE_URL=sqlite+aiosqlite:///./data/comradbot.db

OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_TTS_MODEL=
OPENAI_TTS_VOICE=

DATA_DIRECTORY=./data
SOUNDS_DIRECTORY=./data/sounds

DEFAULT_VOLUME=0.5
MAX_QUEUE_SIZE=100
MAX_SOUND_FILE_SIZE_MB=10
MAX_SOUND_DURATION_SECONDS=30
MAX_AI_CONTEXT_MESSAGES=30
MAX_AI_RESPONSE_CHARACTERS=1800

LOG_LEVEL=INFO
```

Rules:

- required settings must fail fast with clear messages;
- optional integrations must degrade gracefully;
- numeric limits must be validated;
- paths must be normalized;
- secrets must not appear in validation messages;
- settings should be injected where practical rather than repeatedly loaded.

---

## 18. Discord Interaction Rules

Use slash commands and command groups.

Recommended groups:

```text
/music
/sound
/ai
```

Use:

- embeds for structured public responses;
- ephemeral responses for validation errors and administrative operations;
- deferred responses for operations that may exceed Discord interaction timing;
- autocomplete for custom sound names;
- buttons when they improve playback control.

All button actions must also be available as slash commands.

Views must handle:

- timeout;
- expired state;
- missing player state;
- permission checks;
- exceptions;
- repeated interaction attempts.

Do not request the Discord Administrator permission.

Use only required intents.

Do not enable Message Content Intent unless a feature explicitly needs it and the requirement is documented.

---

## 19. Error Handling

Use typed domain or application errors for expected failures.

Examples:

- `AudioQueueFullError`;
- `NotInVoiceChannelError`;
- `DifferentVoiceChannelError`;
- `TrackResolutionError`;
- `FFmpegUnavailableError`;
- `InvalidSoundFileError`;
- `SoundNotFoundError`;
- `AIProviderUnavailableError`;
- `AIRateLimitError`;
- `AIRequestTimeoutError`.

Map these errors to clear user-facing messages.

Unexpected exceptions must:

- be logged with stack traces internally;
- return a generic safe message to the user;
- not crash the bot;
- not expose tokens, paths, provider responses, or internal implementation details.

Never write:

```python
except Exception:
    pass
```

Broad exceptions are allowed only at appropriate boundaries where they are logged and converted into safe failure behavior.

Playback callbacks must capture and route exceptions safely.

---

## 20. Logging

Logging must be configured centrally.

Logs should include, when relevant:

- timestamp;
- level;
- logger name;
- operation;
- guild ID;
- user ID;
- channel ID;
- operation ID;
- latency;
- error category.

Never log:

- Discord tokens;
- OpenAI keys;
- authorization headers;
- complete signed URLs;
- secret configuration;
- full sensitive user prompts by default.

Use structured context where practical.

Do not use `print()` for application diagnostics.

---

## 21. Security Rules

Treat all Discord input as untrusted.

Validate:

- text length;
- attachment size;
- filenames;
- paths;
- URLs;
- numeric ranges;
- queue positions;
- guild ownership;
- permissions;
- channel membership.

Do not execute user input through a shell.

Do not concatenate user input into FFmpeg commands.

Do not expose local filesystem paths.

Do not allow one guild to access another guild's sounds, queue, settings, or conversation state.

Use least-privilege Discord permissions.

Secrets belong only in environment variables or approved secret stores.

Any suspected token exposure requires immediate revocation and replacement.

---

## 22. Code Style

Follow Ruff formatting and lint rules configured in `pyproject.toml`.

Use type annotations for public functions and non-trivial internal APIs.

Prefer:

- descriptive names;
- small focused functions;
- explicit return types;
- immutable data models where suitable;
- `pathlib.Path`;
- `StrEnum` for stable string enums;
- dataclasses or Pydantic models for structured data;
- dependency injection through constructors or explicit parameters.

Avoid:

- large utility modules;
- ambiguous names such as `helper.py`;
- deeply nested conditionals;
- functions with many unrelated responsibilities;
- hidden side effects;
- magic numeric values;
- premature generic frameworks.

Docstrings should explain behavior, constraints, or non-obvious decisions. Do not add docstrings that merely repeat the function name.

Comments should explain why, not restate what the code visibly does.

---

## 23. Naming Conventions

Use:

- `snake_case` for functions, variables, and modules;
- `PascalCase` for classes;
- `UPPER_SNAKE_CASE` for constants;
- singular names for entity classes;
- plural names only where the object represents a collection.

Use clear domain terms:

- `track`;
- `audio_item`;
- `custom_sound`;
- `guild_player`;
- `resolver`;
- `provider`;
- `conversation`;
- `usage_record`.

Do not mix multiple terms for the same concept without a documented distinction.

---

## 24. Testing Policy

Tests should focus on logic that does not require a live Discord connection.

Prioritize tests for:

- queue operations;
- item priority;
- playback state transitions;
- safe queue removal;
- normalized sound names;
- path safety;
- attachment validation;
- duration and size limits;
- cooldowns;
- rate limits;
- AI context trimming;
- long-message splitting;
- temporary file cleanup;
- repository behavior;
- provider error mapping;
- configuration validation.

Use mocks or fakes for:

- Discord voice clients;
- interactions;
- source resolvers;
- AI providers;
- FFmpeg runners;
- filesystem storage where useful;
- repositories where an integration database is not required.

The default test suite must not call:

- Discord;
- OpenAI;
- YouTube or other music platforms;
- external HTTP services.

Async tests must use `pytest-asyncio`.

Tests should be deterministic.

Do not rely on real time passing when a fake clock or explicit timestamp can be used.

---

## 25. Documentation Responsibilities

Update `README.md` when changing:

- installation;
- requirements;
- environment variables;
- startup commands;
- Discord permissions;
- available commands;
- known limitations;
- FFmpeg setup;
- database setup;
- AI provider setup.

Update `TODO.md` when:

- starting a meaningful project phase;
- completing a documented task;
- discovering a necessary follow-up;
- deferring functionality.

Do not mark an item complete merely because code was drafted. It should be implemented, integrated, and reasonably tested.

Add an architecture note when introducing a decision that future contributors could otherwise misunderstand.

All documentation updates must remain in English.

---

## 26. TODO.md Rules

Use Markdown checkboxes.

Recommended structure:

```markdown
## Phase 1 — Foundation

- [x] Create package structure
- [x] Add typed configuration
- [ ] Add graceful shutdown
```

Rules:

- keep tasks concrete;
- split large tasks;
- do not duplicate completed work;
- preserve useful historical context;
- avoid turning TODO into a changelog;
- mark blocked items clearly;
- include acceptance criteria for ambiguous tasks.

When an agent completes work, it must update the related checkbox in the same change.

---

## 27. Development Workflow

For each task:

1. Inspect related code and documentation.
2. Restate the implementation plan briefly.
3. Update `TODO.md` when appropriate.
4. Implement the smallest coherent change.
5. Add or update tests.
6. Run formatting.
7. Run linting.
8. Run type checking.
9. Run tests.
10. Update documentation.
11. Summarize changed files.
12. Report unresolved limitations honestly.

Recommended validation commands:

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest
```

When a command cannot be executed, state why.

Do not claim a check passed unless it was actually run successfully.

---

## 28. Change Scope

Do not perform unrelated cleanup during a focused task.

A task to add `/music skip` should not also:

- rename all modules;
- replace the database layer;
- rewrite the README;
- change the dependency manager;
- redesign the entire command hierarchy.

Small adjacent fixes are acceptable when necessary for correctness.

Large refactors require a clear explanation and should normally be separated.

---

## 29. Backward Compatibility

Preserve public command behavior unless the task explicitly changes it.

When changing a slash command:

- consider Discord command synchronization;
- update documentation;
- update tests;
- account for renamed parameters;
- avoid silently changing semantics.

Configuration changes must preserve existing environment variables where practical.

Database changes must use migrations once Alembic is active.

---

## 30. Performance and Resource Limits

Every potentially unbounded resource needs a limit.

Examples:

- audio queue length;
- custom sound size;
- custom sound duration;
- AI prompt length;
- AI context size;
- AI response length;
- concurrent AI requests;
- resolver concurrency;
- operation timeout;
- retained temporary files;
- inactivity duration;
- cached metadata size.

Prefer configuration-driven limits with validated defaults.

Clean up guild players after disconnection.

Clean up abandoned temporary files when practical.

---

## 31. Graceful Shutdown

The bot must support graceful shutdown.

Shutdown should attempt to:

- stop accepting new work;
- disconnect voice clients;
- cancel managed background tasks;
- close AI and HTTP clients;
- dispose database engines;
- remove temporary resources;
- flush logs.

Cancellation should be treated as part of normal lifecycle behavior, not always as an error.

---

## 32. Feature Priorities

Current priority order:

1. Stable project foundation;
2. Reliable guild-scoped audio player;
3. Music queue and playback controls;
4. Custom sound upload and playback;
5. AI text responses;
6. TTS through the shared audio queue;
7. Persistence and guild settings;
8. Better Discord UI controls;
9. Observability and deployment;
10. Social utilities.

Do not prioritize unrelated systems such as XP, economy, advanced moderation, or a web dashboard unless explicitly requested.

---

## 33. Features Explicitly Out of Scope for the Initial Version

Unless specifically requested, do not implement:

- a web dashboard;
- Spotify playback integration;
- DRM bypass;
- permanent caching of third-party music;
- simultaneous audio mixing;
- automatic resume after interruption;
- voice recognition;
- voice cloning;
- impersonation of real people;
- multiple concrete AI providers;
- economy systems;
- XP systems;
- advanced moderation;
- broad message surveillance.

Interfaces may allow future extension, but avoid speculative implementation.

---

## 34. Agent Response Expectations

After completing a coding task, report:

- what changed;
- why it changed;
- important architectural decisions;
- tests added or updated;
- commands executed;
- command results;
- remaining limitations;
- required manual setup.

Use exact file paths.

Do not provide vague claims such as “everything is production-ready.”

Be explicit when something remains untested.

---

## 35. Definition of Done

A task is complete only when all applicable items are true:

- the requested behavior is implemented;
- architecture boundaries are respected;
- errors are handled;
- security concerns are addressed;
- tests cover the important logic;
- Ruff passes;
- formatting passes;
- mypy passes or known exceptions are documented;
- pytest passes;
- documentation is updated;
- `TODO.md` reflects reality;
- no secrets were added;
- no unrelated behavior was broken.

---

## 36. Final Reminder

ComradBot should remain enjoyable to use, but its codebase must not become disposable.

Favor reliability over gimmicks, clear boundaries over large Cogs, and incremental delivery over implementing every idea at once.
