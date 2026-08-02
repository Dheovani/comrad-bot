"""Conversation and usage persistence without storing unbounded content."""

import json
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Integer, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from comradbot.ai.models import AIMessage, AIUsageOperation, AIUsageSummary
from comradbot.ai.policy import ConversationScope
from comradbot.database.models import AIConversation, AIUsage


class AIRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_messages(
        self,
        guild_id: int,
        scope: ConversationScope,
        scope_id: int,
    ) -> list[AIMessage]:
        async with self._sessions() as session:
            result = await session.execute(
                select(AIConversation).where(
                    AIConversation.guild_id == guild_id,
                    AIConversation.scope_type == scope.value,
                    AIConversation.scope_id == scope_id,
                )
            )
            conversation = result.scalar_one_or_none()
            if conversation is None:
                return []
            raw = json.loads(conversation.messages_json)
            return [AIMessage.model_validate(item) for item in raw]

    async def save_messages(
        self,
        guild_id: int,
        scope: ConversationScope,
        scope_id: int,
        messages: Sequence[AIMessage],
    ) -> None:
        encoded = json.dumps([message.model_dump() for message in messages], ensure_ascii=False)
        async with self._sessions.begin() as session:
            result = await session.execute(
                select(AIConversation).where(
                    AIConversation.guild_id == guild_id,
                    AIConversation.scope_type == scope.value,
                    AIConversation.scope_id == scope_id,
                )
            )
            conversation = result.scalar_one_or_none()
            if conversation is None:
                conversation = AIConversation(
                    guild_id=guild_id,
                    scope_type=scope.value,
                    scope_id=scope_id,
                    messages_json=encoded,
                )
                session.add(conversation)
            else:
                conversation.messages_json = encoded

    async def reset(
        self,
        guild_id: int,
        scope: ConversationScope,
        scope_id: int,
    ) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                delete(AIConversation).where(
                    AIConversation.guild_id == guild_id,
                    AIConversation.scope_type == scope.value,
                    AIConversation.scope_id == scope_id,
                )
            )

    async def reset_guild(self, guild_id: int) -> None:
        async with self._sessions.begin() as session:
            await session.execute(delete(AIConversation).where(AIConversation.guild_id == guild_id))

    async def purge_expired(self, guild_id: int, cutoff: datetime) -> int:
        async with self._sessions.begin() as session:
            result = await session.execute(
                delete(AIConversation).where(
                    AIConversation.guild_id == guild_id,
                    AIConversation.updated_at < cutoff,
                )
            )
            return int(result.rowcount)  # type: ignore[attr-defined]

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

    async def reserve_usage(
        self,
        *,
        guild_id: int,
        user_id: int,
        operation: str,
        daily_limit: int,
        cutoff: datetime,
    ) -> int | None:
        async with self._sessions.begin() as session:
            if daily_limit > 0:
                used = await session.scalar(
                    select(func.count(AIUsage.id)).where(
                        AIUsage.guild_id == guild_id,
                        AIUsage.created_at >= cutoff,
                    )
                )
                if int(used or 0) >= daily_limit:
                    return None
            usage = AIUsage(
                guild_id=guild_id,
                user_id=user_id,
                operation=operation,
                input_characters=0,
                output_characters=0,
                success=False,
            )
            session.add(usage)
            await session.flush()
            return usage.id

    async def finish_usage(
        self,
        usage_id: int,
        *,
        input_characters: int,
        output_characters: int,
        success: bool,
    ) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                update(AIUsage)
                .where(AIUsage.id == usage_id)
                .values(
                    input_characters=input_characters,
                    output_characters=output_characters,
                    success=success,
                )
            )

    async def usage_summary(self, guild_id: int, cutoff: datetime) -> AIUsageSummary:
        async with self._sessions() as session:
            totals = (
                await session.execute(
                    select(
                        func.count(AIUsage.id),
                        func.coalesce(func.sum(AIUsage.input_characters), 0),
                        func.coalesce(func.sum(AIUsage.output_characters), 0),
                        func.coalesce(func.sum(AIUsage.success.cast(Integer)), 0),
                    ).where(
                        AIUsage.guild_id == guild_id,
                        AIUsage.created_at >= cutoff,
                    )
                )
            ).one()
            operation_rows = await session.execute(
                select(AIUsage.operation, func.count(AIUsage.id))
                .where(
                    AIUsage.guild_id == guild_id,
                    AIUsage.created_at >= cutoff,
                )
                .group_by(AIUsage.operation)
                .order_by(AIUsage.operation)
            )
            return AIUsageSummary(
                total_requests=int(totals[0]),
                input_characters=int(totals[1]),
                output_characters=int(totals[2]),
                successful_requests=int(totals[3]),
                operations=tuple(
                    AIUsageOperation(operation=str(operation), requests=int(requests))
                    for operation, requests in operation_rows
                ),
            )
