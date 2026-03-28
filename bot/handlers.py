from __future__ import annotations

import asyncio
import contextlib
import uuid
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from ai.chat_guard import handle_guarded_chat
from ai.formatter import format_callback_response, format_response
from ai.gemini_explainer import generate_gemini_explanation
from decision.rules import evaluate_portfolio
from extraction.extractor import ExtractionError, extract_pdf_to_json, transform_extracted_data
from finance.metrics import compute_portfolio_metrics
from utils.fallback import build_demo_finance_output
from utils.helpers import create_result_keyboard, ensure_tmp_dir, generate_report, safe_delete

STAGE_MESSAGES = (
    "Analyzing your portfolio...",
    "Detecting duplicate investments...",
    "Calculating hidden costs...",
)

CALLBACK_MAP = {
    "why_decision": "why",
    "where_move": "move",
    "do_nothing": "inaction",
    "explain_simple": "simple",
}
LANGUAGE_CALLBACKS = {"lang_english": "english", "lang_hinglish": "hinglish"}


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.setdefault("language", context.bot_data.get("default_language", "english"))
    await update.effective_message.reply_text(
        "🔬 <b>ArthaScan — AI Portfolio Doctor</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Upload your CAMS/KFintech mutual fund statement and get:\n\n"
        "📊 <b>Portfolio Health Score</b> — instant 0-100 rating\n"
        "🔁 <b>Overlap Detection</b> — find duplicate investments\n"
        "💸 <b>Wealth Bleed Calculator</b> — ₹ lost to fees over 10 years\n"
        "📉 <b>Closet Index Detection</b> — are you paying active fees for passive returns?\n"
        "⚡ <b>Ruthless Action Plan</b> — SELL / SWITCH / KEEP decisions\n\n"
        "🌐 Available in <b>English</b> and <b>Hinglish</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📎 Send your PDF statement to begin.",
        parse_mode=ParseMode.HTML,
    )


async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("pending_pdf"):
        await _handle_pdf_password(update, context)
        return

    language = context.user_data.get("language", context.bot_data.get("default_language", "english"))
    metrics = context.user_data.get("analysis_metrics")
    decision_output = context.user_data.get("decision_output")
    message, updated_language = await asyncio.to_thread(
        handle_guarded_chat,
        update.effective_message.text or "",
        decision_output,
        metrics,
        language,
    )
    if updated_language:
        language = updated_language
        context.user_data["language"] = updated_language
    await update.effective_message.reply_text(
        message,
        reply_markup=create_result_keyboard(language)
        if context.user_data.get("analysis_metrics")
        else None,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def _handle_pdf_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    password = (update.effective_message.text or "").strip()
    pdf_path = context.user_data.get("pending_pdf")
    if not pdf_path or not Path(pdf_path).exists():
        context.user_data.pop("pending_pdf", None)
        await update.effective_message.reply_text("Session expired. Please upload your PDF again.")
        return

    import fitz
    try:
        doc = fitz.open(pdf_path)
        if not doc.authenticate(password):
            doc.close()
            await update.effective_message.reply_text("Incorrect password. Please try again or upload a new PDF.")
            return

        decrypted_path = str(pdf_path).replace(".pdf", "_decrypted.pdf")
        doc.save(decrypted_path, encryption=fitz.PDF_ENCRYPT_NONE)
        doc.close()
        
        safe_delete(pdf_path)
        context.user_data.pop("pending_pdf", None)
        
        await _execute_portfolio_analysis(update, context, Path(decrypted_path))
    except Exception:
        context.user_data.pop("pending_pdf", None)
        safe_delete(pdf_path)
        await update.effective_message.reply_text("Failed to unlock PDF. Please upload an unencrypted file.")


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.effective_message.document
    if document is None:
        return

    current_language = context.user_data.get("language", context.bot_data.get("default_language", "english"))
    context.user_data.clear()
    context.user_data["language"] = current_language

    if document.mime_type != "application/pdf":
        await update.effective_message.reply_text(
            "Please upload a valid PDF statement. Other file types are not supported."
        )
        return

    tmp_dir = ensure_tmp_dir()
    temp_pdf = tmp_dir / f"{uuid.uuid4()}.pdf"
    
    telegram_file = await document.get_file()
    await telegram_file.download_to_drive(custom_path=str(temp_pdf))

    import fitz
    try:
        doc = fitz.open(str(temp_pdf))
        if doc.is_encrypted:
            context.user_data["pending_pdf"] = str(temp_pdf)
            doc.close()
            await update.effective_message.reply_text(
                "🔒 Aapka statement password-protected hai.\n"
                "Apna PAN number bhejo (e.g. ABCDE1234F) to unlock it."
            )
            return
        doc.close()
    except Exception:
        pass

    await _execute_portfolio_analysis(update, context, temp_pdf)


async def _execute_portfolio_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, temp_pdf: Path) -> None:
    stop_event = asyncio.Event()
    progress_message = await update.effective_message.reply_text(STAGE_MESSAGES[0])

    typing_task = asyncio.create_task(_typing_indicator(update, context, stop_event))
    progress_task = asyncio.create_task(_progress_indicator(progress_message, stop_event))

    try:
        metrics, used_demo = await _run_pipeline(temp_pdf)
    except Exception:
        used_demo = True
        metrics = build_demo_finance_output()
    finally:
        stop_event.set()
        await _await_task(typing_task)
        await _await_task(progress_task)
        safe_delete(temp_pdf)

    try:
        decision_output = await asyncio.to_thread(evaluate_portfolio, metrics)
        language = context.user_data.get("language", context.bot_data.get("default_language", "english"))
        final_message = format_response(decision_output, metrics, language=language)

        context.user_data["analysis_metrics"] = metrics
        context.user_data["decision_output"] = decision_output

        if used_demo:
            await update.effective_message.reply_text(
                "⚠️ Could not extract your portfolio reliably. "
                "Showing demo analysis — upload a clearer PDF for accurate results.",
                reply_markup=create_result_keyboard(language),
            )

        with contextlib.suppress(BadRequest):
            await progress_message.edit_text("Analysis complete.")
        await update.effective_message.reply_text(
            final_message,
            parse_mode=ParseMode.HTML,
            reply_markup=create_result_keyboard(language),
            disable_web_page_preview=True,
        )
    except Exception:
        fallback_metrics = build_demo_finance_output()
        fallback_decision = await asyncio.to_thread(evaluate_portfolio, fallback_metrics)
        language = context.user_data.get("language", context.bot_data.get("default_language", "english"))
        fallback_message = format_response(fallback_decision, fallback_metrics, language=language)
        context.user_data["analysis_metrics"] = fallback_metrics
        context.user_data["decision_output"] = fallback_decision
        with contextlib.suppress(BadRequest):
            await progress_message.edit_text("Analysis complete.")
        await update.effective_message.reply_text(
            "⚠️ Could not extract your portfolio reliably. "
            "Showing demo analysis — upload a clearer PDF for accurate results.",
            reply_markup=create_result_keyboard(language),
        )
        await update.effective_message.reply_text(
            fallback_message,
            parse_mode=ParseMode.HTML,
            reply_markup=create_result_keyboard(language),
            disable_web_page_preview=True,
        )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    metrics = context.user_data.get("analysis_metrics")
    decision_output = context.user_data.get("decision_output")

    if not metrics or not decision_output:
        await query.message.reply_text("Upload a PDF first so I can generate the analysis.")
        return

    language = context.user_data.get("language", context.bot_data.get("default_language", "english"))

    if query.data in LANGUAGE_CALLBACKS:
        new_language = LANGUAGE_CALLBACKS[query.data]
        context.user_data["language"] = new_language
        translated_message = format_response(decision_output, metrics, language=new_language)
        await query.message.reply_text(
            translated_message,
            parse_mode=ParseMode.HTML,
            reply_markup=create_result_keyboard(new_language),
            disable_web_page_preview=True,
        )
        return

    try:
        if query.data == "download_report":
            await _handle_report_download(query, metrics, decision_output, language)
            return

        response_key = CALLBACK_MAP.get(query.data)
        if response_key is None:
            await query.message.reply_text(
                "That action is not available right now.",
                reply_markup=create_result_keyboard(language),
            )
            return

        fallback_message = format_callback_response(response_key, decision_output, metrics, language=language)
        message = await asyncio.to_thread(
            generate_gemini_explanation,
            response_key,
            decision_output,
            metrics,
            language,
            fallback_message,
        )
        await query.message.reply_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=create_result_keyboard(language),
            disable_web_page_preview=True,
        )
    except Exception:
        await query.message.reply_text(
            "That action hit a problem, but your analysis is still available. Please try the button again.",
            reply_markup=create_result_keyboard(language),
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(update, Update) and update.effective_message:
        with contextlib.suppress(Exception):
            await update.effective_message.reply_text(
                "The analysis hit a problem, but the bot is still running. Please upload the PDF again."
            )


async def _run_pipeline(pdf_path: Path) -> tuple[dict[str, Any], bool]:
    try:
        extracted = await asyncio.wait_for(
            asyncio.to_thread(extract_pdf_to_json, pdf_path),
            timeout=60,
        )
        transformed = await asyncio.to_thread(transform_extracted_data, extracted)
        metrics = await asyncio.to_thread(compute_portfolio_metrics, transformed)
        if _should_use_demo_metrics(metrics):
            return build_demo_finance_output(), True
        return metrics, False
    except (asyncio.TimeoutError, ExtractionError):
        return build_demo_finance_output(), True
    except Exception:
        return build_demo_finance_output(), True


async def _typing_indicator(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    stop_event: asyncio.Event,
) -> None:
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return

    while not stop_event.is_set():
        with contextlib.suppress(Exception):
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.5)
        except asyncio.TimeoutError:
            continue


async def _progress_indicator(progress_message, stop_event: asyncio.Event) -> None:
    index = 0
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1.8)
            break
        except asyncio.TimeoutError:
            index = (index + 1) % len(STAGE_MESSAGES)
            with contextlib.suppress(BadRequest):
                await progress_message.edit_text(STAGE_MESSAGES[index])


async def _await_task(task: asyncio.Task[None]) -> None:
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task


async def _handle_report_download(
    query,
    metrics: dict[str, Any],
    decision_output: dict[str, Any],
    language: str,
) -> None:
    tmp_dir = ensure_tmp_dir()
    report_path = tmp_dir / f"portfolio-report-{uuid.uuid4()}.pdf"
    english_text = format_response(decision_output, metrics, language="english")
    hinglish_text = format_response(decision_output, metrics, language="hinglish")

    try:
        await asyncio.to_thread(
            generate_report,
            decision_output,
            metrics,
            report_path,
            english_text,
            hinglish_text,
        )
        with report_path.open("rb") as handle:
            await query.message.reply_document(
                document=handle,
                filename="portfolio_report.pdf",
                caption="Detailed report ready.",
                reply_markup=create_result_keyboard(language),
            )
    finally:
        safe_delete(report_path)


def _should_use_demo_metrics(metrics: dict[str, Any]) -> bool:
    fund_metrics = metrics.get("fund_metrics", [])
    if not fund_metrics:
        return True

    no_overlap = metrics.get("portfolio_metrics", {}).get("max_portfolio_overlap", 0) == 0
    no_stat_history = all(
        fund.get("alpha") is None and fund.get("r_squared") is None
        for fund in fund_metrics
    )
    no_valid_xirr = all(fund.get("xirr") is None for fund in fund_metrics)
    missing_data = "MISSING_DATA" in metrics.get("portfolio_metrics", {}).get("top_issues", [])

    return bool(missing_data and no_overlap and no_stat_history and no_valid_xirr)
