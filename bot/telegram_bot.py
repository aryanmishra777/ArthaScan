from __future__ import annotations

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .handlers import (
    callback_handler,
    chat_handler,
    document_handler,
    error_handler,
    start_handler,
)


def build_application(token: str) -> Application:
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(
        MessageHandler(
            ~filters.COMMAND & ~filters.Document.ALL,
            chat_handler,
        )
    )
    application.add_error_handler(error_handler)
    return application
