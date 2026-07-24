"""Validation rules for bounded, untrusted speech-recognition uploads."""

from pathlib import Path

from comradbot.errors import ValidationError

SUPPORTED_TRANSCRIPTION_EXTENSIONS = {
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".ogg",
    ".wav",
    ".webm",
}
SUPPORTED_TRANSCRIPTION_MIME_TYPES = {
    "audio/flac",
    "audio/m4a",
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
    "audio/x-m4a",
    "audio/x-wav",
    "video/mp4",
    "video/webm",
}
GENERIC_MIME_TYPES = {"application/octet-stream", "binary/octet-stream"}


def validate_transcription_upload(
    *,
    filename: str,
    content_type: str | None,
    size_bytes: int,
    max_size_bytes: int,
) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_TRANSCRIPTION_EXTENSIONS:
        raise ValidationError(
            "Unsupported transcription format. Use FLAC, MP3, MP4, M4A, OGG, WAV, or WebM."
        )
    normalized_mime = content_type.lower().split(";", 1)[0].strip() if content_type else None
    if (
        normalized_mime
        and normalized_mime not in SUPPORTED_TRANSCRIPTION_MIME_TYPES
        and normalized_mime not in GENERIC_MIME_TYPES
    ):
        raise ValidationError("The attachment MIME type is not supported for transcription.")
    if size_bytes <= 0:
        raise ValidationError("The attachment is empty.")
    if size_bytes > max_size_bytes:
        raise ValidationError("The attachment exceeds the transcription size limit.")
    return extension
