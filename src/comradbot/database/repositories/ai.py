"""Conversation and usage persistence without storing unbounded content."""

import json
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from comradbot.ai.models import AIMessage
from comradbot.database.models import AIConversation, AIUsage


class AIRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_messages(self, guild_id: int, scope_id: int) -> list[AIMessage]:
        async with self._sessions() as session:
            result = await session.execute(
                select(AIConversation).where(
                    AIConversation.guild_id == guild_id,
                    AIConversation.scope_id == scope_id,
                )
            )
            conversation = result.scalar_one_or_none()
            if conversation is None:
                return []
            raw = json.loads(conversation.messages_json)
            return [AIMessage.model_validate(item) for item in raw]

    async def save_messages(
        self, guild_id: int, scope_id: int, messages: Sequence[AIMessage]
    ) -> None:
        encoded = json.dumps([message.model_dump() for message in messages], ensure_ascii=False)
        async with self._sessions.begin() as session:
            result = await session.execute(
                select(AIConversation).where(
                    AIConversation.guild_id == guild_id,
                    AIConversation.scope_id == scope_id,
                )
            )
            conversation = result.scalar_one_or_none()
            if conversation is None:
                conversation = AIConversation(
                    guild_id=guild_id, scope_id=scope_id, messages_json=encoded
                )
                session.add(conversation)
            else:
                conversation.messages_json = encoded

    async def reset(self, guild_id: int, scope_id: int) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                delete(AIConversation).where(
                    AIConversation.guild_id == guild_id,
                    AIConversation.scope_id == scope_id,
                )
            )

    async def record_usage(
        self,
        *,
        guild_id: int,
        user_id: int,
        operation: str,
        input_characters: int,
        output_characters: int,
        success: bool,
    ) -> None:
        async with self._sessions.begin() as session:
            session.add(
                AIUsage(
                    guild_id=guild_id,
                    user_id=user_id,
                    operation=operation,
                    input_characters=input_characters,
                    output_characters=output_characters,
                    success=success,
                )
            )
