"""Central logging configuration with contextual fields."""

import contextvars
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

_guild_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("guild_id", default=None)
_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("user_id", default=None)
_operation_id: contextvars.ContextVar[str] = contextvars.ContextVar("operation_id", default="-")


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.guild_id = _guild_id.get() or "-"
        record.user_id = _user_id.get() or "-"
        record.operation_id = _operation_id.get()
        return True


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(ContextFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s guild=%(guild_id)s user=%(user_id)s "
            "operation=%(operation_id)s %(message)s"
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


@contextmanager
def log_context(*, guild_id: int | None = None, user_id: int | None = None) -> Iterator[str]:
    guild_token = _guild_id.set(guild_id)
    user_token = _user_id.set(user_id)
    operation_token = _operation_id.set(uuid4().hex[:12])
    try:
        yield _operation_id.get()
    finally:
        _guild_id.reset(guild_token)
        _user_id.reset(user_token)
        _operation_id.reset(operation_token)
