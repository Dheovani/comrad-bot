from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from comradbot.commands.general import (
    GeneralCog,
    build_help_embed,
    extract_mention_prompt,
    should_respond_to_mention,
)


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
    assert "/settings volume" in content
    assert "/ping" in content
    assert "/health" in content


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


def test_mention_prompt_removes_bot_id_and_sanitizes_other_discord_ids() -> None:
    prompt = extract_mention_prompt(
        "<@20> o que <@!30> acha do canal <#40> e do cargo <@&50>?",
        bot_user_id=20,
    )

    assert prompt == "o que @member acha do canal #channel e do cargo @role?"
    assert extract_mention_prompt("<@!20>", bot_user_id=20).startswith("Você foi chamado")


class FakeTyping:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_direct_mention_uses_shared_ai_conversation_scope() -> None:
    ai_service = SimpleNamespace(ask=AsyncMock(return_value="Resposta do camarada"))
    bot = SimpleNamespace(
        user=SimpleNamespace(id=20),
        settings=SimpleNamespace(
            discord_respond_to_mentions=True,
            max_ai_response_characters=1800,
        ),
        ai_service=ai_service,
    )
    channel = SimpleNamespace(
        id=30,
        typing=lambda: FakeTyping(),
        send=AsyncMock(),
    )
    message = SimpleNamespace(
        guild=SimpleNamespace(id=40),
        channel=channel,
        author=SimpleNamespace(id=50, bot=False),
        mentions=[SimpleNamespace(id=20)],
        content="<@20> como estamos hoje?",
        reply=AsyncMock(),
    )

    await GeneralCog(cast(Any, bot)).on_message(cast(Any, message))

    ai_service.ask.assert_awaited_once_with(
        guild_id=40,
        channel_id=30,
        user_id=50,
        prompt="como estamos hoje?",
    )
    message.reply.assert_awaited_once()
    assert message.reply.await_args.args[0] == "Resposta do camarada"
