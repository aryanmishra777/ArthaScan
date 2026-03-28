from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from bot.telegram_bot import build_application


def _ensure_event_loop() -> asyncio.AbstractEventLoop:
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def main() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=env_path)
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is required. Add it to a .env file in the project root "
            "or export it in your shell."
        )

    _ensure_event_loop()
    application = build_application(token)
    application.bot_data["default_language"] = os.getenv("BOT_LANGUAGE", "english").strip().lower()
    application.run_polling()


if __name__ == "__main__":
    main()
