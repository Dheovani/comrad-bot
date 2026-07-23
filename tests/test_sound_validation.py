from pathlib import Path
from uuid import uuid4

import pytest

from comradbot.errors import ValidationError
from comradbot.sounds.storage import SoundStorage
from comradbot.sounds.validation import normalize_sound_name, validate_upload_metadata


@pytest.mark.parametrize(
    ("original", "expected"),
    [("  Risada Épica  ", "risada-epica"), ("air_horn", "air-horn"), ("123", "123")],
)
def test_normalize_sound_name(original: str, expected: str) -> None:
    assert normalize_sound_name(original) == expected


@pytest.mark.parametrize("name", ["", "!!!", "a" * 51, "../segredo"])
def test_invalid_sound_names(name: str) -> None:
    with pytest.raises(ValidationError):
        normalize_sound_name(name)


def test_upload_metadata_checks_extension_mime_and_size() -> None:
    assert (
        validate_upload_metadata(
            filename="voice.ogg", content_type="audio/ogg", size_bytes=10, max_size_bytes=20
        )
        == ".ogg"
    )
    with pytest.raises(ValidationError, match="MIME"):
        validate_upload_metadata(
            filename="voice.ogg",
            content_type="application/x-msdownload",
            size_bytes=10,
            max_size_bytes=20,
        )
    with pytest.raises(ValidationError, match="tamanho"):
        validate_upload_metadata(
            filename="voice.ogg", content_type="audio/ogg", size_bytes=21, max_size_bytes=20
        )


def test_storage_uses_uuid_and_blocks_path_traversal(tmp_path: Path) -> None:
    storage = SoundStorage(tmp_path)
    sound_id = str(uuid4())
    relative = storage.relative_sound_path(123, sound_id)

    assert relative == Path("123") / f"{sound_id}.opus"
    assert storage.absolute_path(relative).is_relative_to(tmp_path.resolve())
    with pytest.raises(ValidationError, match="escaparia"):
        storage.absolute_path("../outside.opus")
