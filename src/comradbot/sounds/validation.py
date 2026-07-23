"""Validation and normalization rules for untrusted sound uploads."""

import re
import unicodedata
from pathlib import Path

from comradbot.errors import ValidationError

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".opus", ".flac", ".m4a", ".webm"}
SUPPORTED_MIME_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/opus",
    "audio/flac",
    "audio/mp4",
    "audio/webm",
    "video/webm",
}
_VALID_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,48}[a-z0-9])?$")


def normalize_sound_name(name: str) -> str:
    if "/" in name or "\\" in name or ".." in name:
        raise ValidationError("O nome do áudio contém uma sequência de caminho inválida.")
    folded = unicodedata.normalize("NFKD", name.strip()).encode("ascii", "ignore").decode()
    normalized = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    if not normalized or not _VALID_NAME.fullmatch(normalized):
        raise ValidationError(
            "Use um nome com 1 a 50 caracteres, contendo letras, números, hífen ou sublinhado."
        )
    return normalized


def validate_upload_metadata(
    *, filename: str, content_type: str | None, size_bytes: int, max_size_bytes: int
) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValidationError("Formato não suportado. Use MP3, WAV, OGG/Opus, FLAC, M4A ou WebM.")
    if content_type and content_type.lower().split(";", 1)[0] not in SUPPORTED_MIME_TYPES:
        raise ValidationError("O tipo MIME informado não corresponde a um áudio suportado.")
    if size_bytes <= 0:
        raise ValidationError("O arquivo está vazio.")
    if size_bytes > max_size_bytes:
        raise ValidationError("O arquivo excede o limite de tamanho configurado.")
    return extension
