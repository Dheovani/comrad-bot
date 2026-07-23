from comradbot.commands.general import build_help_embed, should_respond_to_mention


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


def test_mention_response_only_accepts_human_messages_that_include_the_bot() -> None:
    assert should_respond_to_mention(
        author_is_bot=False,
        mentioned_user_ids={10, 20},
        bot_user_id=20,
    )
    assert not should_respond_to_mention(
        author_is_bot=True,
        mentioned_user_ids={20},
        bot_user_id=20,
    )
    assert not should_respond_to_mention(
        author_is_bot=False,
        mentioned_user_ids={10},
        bot_user_id=20,
    )
