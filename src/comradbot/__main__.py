"""Command-line entry point."""

import sys

from pydantic import ValidationError

from comradbot.bot import ComradBot
from comradbot.config import get_settings
from comradbot.logging import configure_logging


def main() -> None:
    try:
        settings = get_settings()
    except ValidationError as exc:
        missing = ", ".join(".".join(map(str, error["loc"])) for error in exc.errors())
        print(
            f"Configuração inválida ou ausente ({missing}). Copie .env.example para .env e "
            "preencha DISCORD_TOKEN.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    configure_logging(settings.log_level)
    bot = ComradBot(settings)
    bot.run(settings.discord_token.get_secret_value(), log_handler=None)


if __name__ == "__main__":
    main()
