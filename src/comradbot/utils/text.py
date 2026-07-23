"""Discord-safe text splitting."""


def split_message(text: str, limit: int = 1800) -> list[str]:
    if limit < 1:
        raise ValueError("limit must be positive")
    remaining = text.strip()
    if not remaining:
        return []
    chunks: list[str] = []
    while len(remaining) > limit:
        boundary = max(remaining.rfind("\n", 0, limit + 1), remaining.rfind(" ", 0, limit + 1))
        if boundary <= 0:
            boundary = limit
        chunks.append(remaining[:boundary].rstrip())
        remaining = remaining[boundary:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks
