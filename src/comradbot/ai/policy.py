"""Guild-configurable AI conversation memory policy."""

from dataclasses import dataclass
from enum import StrEnum


class ConversationScope(StrEnum):
    CHANNEL = "channel"
    USER = "user"
    SERVER = "server"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ConversationPolicy:
    scope: ConversationScope = ConversationScope.CHANNEL
    retention_days: int = 30


@dataclass(frozen=True, slots=True)
class ConversationKey:
    scope: ConversationScope
    scope_id: int


def resolve_conversation_key(
    policy: ConversationPolicy,
    *,
    guild_id: int,
    channel_id: int,
    user_id: int,
) -> ConversationKey | None:
    if policy.scope is ConversationScope.NONE:
        return None
    if policy.scope is ConversationScope.USER:
        scope_id = user_id
    elif policy.scope is ConversationScope.SERVER:
        scope_id = guild_id
    else:
        scope_id = channel_id
    return ConversationKey(scope=policy.scope, scope_id=scope_id)
