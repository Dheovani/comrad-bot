from comradbot.commands.general import build_help_embed


def test_help_embed_lists_current_command_groups() -> None:
    embed = build_help_embed()
    content = "\n".join(
        [embed.title or "", embed.description or ""]
        + [f"{field.name}\n{field.value}" for field in embed.fields]
    )

    assert "/music play" in content
    assert "/music disconnect" in content
    assert "/sound upload" in content
    assert "/sound rename" in content
    assert "/ai ask" in content
    assert "/ping" in content
