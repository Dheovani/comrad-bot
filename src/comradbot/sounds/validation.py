"""Validation and normalization rules for untrusted sound uploads."""

import re
import unicodedata
from pathlib import Path

from comradbot.errors import ValidationError

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".opus", ".flac", ".m4a", ".webm"}
SUPPORTED_MIME_TYPES = {
    "audio/mp3",
    "audio/mpeg",
    "audio/mpeg3",
    "audio/x-mp3",
    "audio/x-mpeg",
    "audio/x-mpeg-3",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/opus",
    "audio/flac",
    "audio/mp4",
    "audio/webm",
    "video/webm",
}
GENERIC_MIME_TYPES = {"application/octet-stream", "binary/octet-stream"}
_VALID_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,48}[a-z0-9])?$")


def normalize_sound_name(name: str) -> str:
    if "/" in name or "\\" in name or ".." in name:
        raise ValidationError("The sound name contains an invalid path sequence.")
    folded = unicodedata.normalize("NFKD", name.strip()).encode("ascii", "ignore").decode()
    normalized = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    if not normalized or not _VALID_NAME.fullmatch(normalized):
        raise ValidationError("Use a name with 1 to 50 letters, numbers, hyphens, or underscores.")
    return normalized


def validate_upload_metadata(
    *, filename: str, content_type: str | None, size_bytes: int, max_size_bytes: int
) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValidationError("Unsupported format. Use MP3, WAV, OGG/Opus, FLAC, M4A, or WebM.")
    normalized_mime = content_type.lower().split(";", 1)[0].strip() if content_type else None
    if (
        normalized_mime
        and normalized_mime not in SUPPORTED_MIME_TYPES
        and normalized_mime not in GENERIC_MIME_TYPES
    ):
        raise ValidationError(
            f"The provided MIME type ({normalized_mime}) is not a supported audio type."
        )
    if size_bytes <= 0:
        raise ValidationError("The file is empty.")
    if size_bytes > max_size_bytes:
        raise ValidationError("The file exceeds the configured size limit.")
    return extension
