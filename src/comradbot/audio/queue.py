"""Bounded, asyncio-safe heterogeneous audio queue."""

import asyncio
from collections import deque

from comradbot.audio.models import AudioItem
from comradbot.errors import ValidationError


class AudioQueue:
    def __init__(self, max_size: int) -> None:
        self._items: deque[AudioItem] = deque()
        self._max_size = max_size
        self._condition = asyncio.Condition()

    def __len__(self) -> int:
        return len(self._items)

    async def put(self, item: AudioItem, *, next_item: bool = False) -> int:
        async with self._condition:
            if len(self._items) >= self._max_size:
                raise ValidationError(f"The queue has reached its limit of {self._max_size} items.")
            if next_item:
                self._items.appendleft(item)
                position = 1
            else:
                self._items.append(item)
                position = len(self._items)
            self._condition.notify(1)
            return position

    async def get(self) -> AudioItem:
        async with self._condition:
            await self._condition.wait_for(self._items.__len__)
            return self._items.popleft()

    async def remove(self, position: int) -> AudioItem:
        async with self._condition:
            if position < 1 or position > len(self._items):
                raise ValidationError("That queue position does not exist.")
            self._items.rotate(-(position - 1))
            item = self._items.popleft()
            self._items.rotate(position - 1)
            return item

    async def clear(self) -> list[AudioItem]:
        async with self._condition:
            removed = list(self._items)
            self._items.clear()
            return removed

    async def snapshot(self) -> list[AudioItem]:
        async with self._condition:
            return list(self._items)
