from comradbot.utils.text import split_message


def test_split_message_prefers_boundaries_and_preserves_content() -> None:
    text = "um dois três quatro cinco"
    chunks = split_message(text, limit=10)

    assert all(len(chunk) <= 10 for chunk in chunks)
    assert " ".join(chunks) == text


def test_split_message_handles_long_unbroken_text_and_empty_input() -> None:
    assert split_message("abcdefgh", limit=3) == ["abc", "def", "gh"]
    assert split_message("   ") == []
