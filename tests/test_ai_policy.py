import pytest

from comradbot.ai.policy import (
    ConversationPolicy,
    ConversationScope,
    resolve_conversation_key,
)


@pytest.mark.parametrize(
    ("scope", "expected_id"),
    [
        (ConversationScope.CHANNEL, 20),
        (ConversationScope.USER, 30),
        (ConversationScope.SERVER, 10),
    ],
)
def test_conversation_scope_resolves_isolated_key(
    scope: ConversationScope, expected_id: int
) -> None:
    key = resolve_conversation_key(
        ConversationPolicy(scope=scope, retention_days=30),
        guild_id=10,
        channel_id=20,
        user_id=30,
    )

    assert key is not None
    assert key.scope is scope
    assert key.scope_id == expected_id


def test_none_scope_disables_persistent_memory() -> None:
    assert (
        resolve_conversation_key(
            ConversationPolicy(scope=ConversationScope.NONE, retention_days=30),
            guild_id=10,
            channel_id=20,
            user_id=30,
        )
        is None
    )
