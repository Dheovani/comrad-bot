"""Domain errors safe to map to Discord responses."""


class ComradBotError(Exception):
    """Base class for expected application failures."""


class ValidationError(ComradBotError):
    """Input failed a business rule."""


class PermissionDeniedError(ComradBotError):
    """The actor is not allowed to perform an operation."""


class VoiceConnectionError(ComradBotError):
    """A Discord voice connection could not be used."""


class AudioPlaybackError(ComradBotError):
    """FFmpeg or the Discord voice client failed during playback."""


class ResolverError(ComradBotError):
    """A public media source could not be resolved."""


class AIError(ComradBotError):
    """An AI provider operation failed."""


class AIDisabledError(AIError):
    """AI is intentionally unavailable because no provider is configured."""


class RateLimitError(AIError):
    """A local or provider rate limit was reached."""


class OperationTimeoutError(ComradBotError):
    """An external or long-running operation timed out."""


class DatabaseMigrationError(ComradBotError):
    """The database schema cannot be migrated safely without operator action."""
