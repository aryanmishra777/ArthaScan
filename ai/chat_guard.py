from __future__ import annotations

import logging
import os
import re
from typing import Any

from ai.formatter import format_callback_response, format_response
from ai.gemini_explainer import classify_intent_with_gemini, generate_guarded_gemini_chat

logger = logging.getLogger(__name__)

REFUSAL_MESSAGE = "ArthaScan can't answer that. Please ask about your uploaded portfolio or use the buttons."
REFUSAL_MESSAGE_HINGLISH = "ArthaScan uska answer nahi de sakta. Apne uploaded portfolio ke baare me poochho ya buttons use karo."

MAX_INPUT_LENGTH = 500
MIN_INPUT_LENGTH = 1
GEMINI_INTENT_THRESHOLD = 0.85

INJECTION_PATTERNS = re.compile(
    r"ignore (previous|prior|all) instructions?"
    r"|forget (everything|what i said|previous)"
    r"|you are now|act as|pretend (you are|to be)"
    r"|system prompt|reveal your|jailbreak"
    r"|<\s*(script|iframe|img)|javascript:",
    re.IGNORECASE,
)

GENERAL_PATTERNS = re.compile(
    r"^(hi|hello|hey|hola|namaste|start)\b"
    r"|\b(help( me)?|assist|what do you do|who are you)\b"
    r"|\b(kaise.*?madad|kaise.*?sahayta|kaise.*?sahayata|kya kar sakte|kaun ho|saha?y?a?ta|madad)\b",
    re.IGNORECASE,
)

HINGLISH_SIGNALS = re.compile(
    r"\b(yaar|bhai|karo|karu|hai|hain|nahi|nhi|matlab|"
    r"batao|samjha|smjha|samjhao|aasan|kya karu|kuch nahi|zyada|"
    r"achha|theek|thoda|bahut|seedha|seedhi|toh|aur|lekin)\b",
    re.IGNORECASE,
)


def handle_guarded_chat(
    user_text: str,
    decision_output: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    language: str,
) -> tuple[str, str | None]:
    if os.getenv("SAFE_CHAT_MODE", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return _refusal(language), None

    sanitized, error = _sanitize_input(user_text)
    if error:
        logger.warning("Input rejected: %s | reason=%s", repr(str(user_text)[:100]), error)
        return _refusal(language), None

    if GENERAL_PATTERNS.search(sanitized):
        if metrics is None or decision_output is None:
            if _detect_hinglish(sanitized) or language == "hinglish":
                return "Namaste! Main ArthaScan hoon. Main aapke mutual fund statement mein chhupe huye charges aur duplicate funds dhoondh sakta hoon. Apna CAMS/KFintech statement PDF upload karein taaki main analysis shuru kar saku.", "hinglish"
            return "Hi! I am ArthaScan. I can find hidden fees and duplicate investments in your mutual funds. Please upload your CAMS/KFintech statement PDF to start.", "english"
        else:
            if _detect_hinglish(sanitized) or language == "hinglish":
                return "Namaste! Aapka analysis taiyar hai. Main aapke portfolio ke baare me koi bhi sawal ka jawab de sakta hoon, ya aap neeche diye gaye buttons use kar sakte hain.", "hinglish"
            return "Hi! Your analysis is ready. I can answer any questions about your portfolio, or you can use the buttons below.", "english"

    if INJECTION_PATTERNS.search(sanitized):
        logger.warning("Prompt injection pattern blocked: %s", repr(sanitized[:100]))
        return _refusal(language), None

    if metrics is None or decision_output is None:
        if _looks_like_portfolio_request(sanitized):
            if _detect_hinglish(sanitized):
                return "Pehle apna portfolio PDF upload karo, tab ArthaScan analysis samjha sakta hai.", None
            return "Upload a portfolio PDF first so ArthaScan can answer questions about your analysis.", None
        return _refusal(language), None

    response_language = language
    if response_language == "english" and _detect_hinglish(sanitized):
        response_language = "hinglish"

    intent = _classify_intent(sanitized)
    if intent == "unknown":
        if not _is_meaningful_query(sanitized):
            logger.info("Rejected non-meaningful query: %s", repr(sanitized[:100]))
            return _refusal(response_language), None
        intent = "chat"

    return _route_intent(intent, sanitized, decision_output, metrics, response_language)


def _route_intent(
    intent: str,
    text: str,
    decision_output: dict[str, Any],
    metrics: dict[str, Any],
    language: str,
) -> tuple[str, str | None]:
    simple_routes = {
        "lang_hinglish": lambda: (format_response(decision_output, metrics, language="hinglish"), "hinglish"),
        "lang_english": lambda: (format_response(decision_output, metrics, language="english"), "english"),
        "summary": lambda: (format_response(decision_output, metrics, language=language), None),
        "fees": lambda: (_fees_response(metrics, decision_output, language), None),
        "overlap": lambda: (_overlap_response(metrics, decision_output, language), None),
        "returns": lambda: (_returns_response(metrics, language), None),
        "fund": lambda: (_fund_response(decision_output, language), None),
        "confidence": lambda: (_confidence_response(decision_output, language), None),
    }
    if intent in simple_routes:
        return simple_routes[intent]()

    gemini_intents = {"why", "simple", "move", "inaction", "define", "chat"}
    if intent in gemini_intents:
        if intent == "define":
            fallback = "Yeh ek financial term hai." if language == "hinglish" else "This is a financial term."
        elif intent == "chat":
            fallback = _refusal(language)
        else:
            fallback = format_callback_response(intent, decision_output, metrics, language=language)
        try:
            response = generate_guarded_gemini_chat(text, decision_output, metrics, language, fallback)
            if response.lower() in {"i can't answer that.", "main uska answer nahi de sakta."}:
                return _refusal(language), None
            return response, None
        except Exception as exc:
            logger.error("Gemini guarded chat failed for intent '%s': %s", intent, exc)
            return fallback, None

    return _refusal(language), None


def _sanitize_input(text: str) -> tuple[str, str | None]:
    if not isinstance(text, str):
        return "", "non-string input"

    cleaned = " ".join(text.strip().split())
    if len(cleaned) < MIN_INPUT_LENGTH:
        return "", "empty input"
    if len(cleaned) > MAX_INPUT_LENGTH:
        return "", f"input too long ({len(cleaned)} chars)"
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", cleaned):
        return "", "non-printable characters"
    return cleaned, None


def _is_meaningful_query(text: str) -> bool:
    words = text.split()
    if len(words) < 2:
        return False
    real_words = [word for word in words if len(word) >= 2]
    return len(real_words) / len(words) >= 0.6


def _detect_hinglish(text: str) -> bool:
    return bool(HINGLISH_SIGNALS.search(text))


def _looks_like_portfolio_request(text: str) -> bool:
    keywords = (
        "portfolio",
        "fund",
        "fees",
        "overlap",
        "return",
        "xirr",
        "analysis",
        "sell",
        "switch",
        "keep",
        "consolidate",
        "expense",
        "sip",
        "mutual fund",
        "invest",
    )
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _classify_intent(text: str) -> str:
    patterns: list[tuple[str, str]] = [
        ("define", r"\bwhat is\b|\bdefine\b|\bmeaning\b|\bwhat does\b|kya hota hai|kise kehte|kya hai|meaning kya hai"),
        ("lang_hinglish", r"\bhinglish\b|\bhindi me\b|\bhinglish me\b|\breply in hinglish\b|\breply in hindi\b"),
        ("lang_english", r"\benglish\b|\breply in english\b"),
        ("why", r"\bwhy\b|\breason\b|\bjustify\b|kyu|kyun|kisliye|kyon"),
        ("simple", r"\bexplain\b|\bsimple\b|\bplain english\b|samjha|smjha|samjhao|aasan bhasha|aasan language|easy language|simple words|seedha samjhao"),
        ("move", r"\bwhere\b|\bmove\b|\bswitch to\b|\breallocate\b|kaha|kahan|kahaan|kidhar|shift karu|move karu"),
        ("inaction", r"\bdo nothing\b|\bignore\b|\bwait\b|\bif i keep\b|agar kuch na karu|agar main kuch na karu|aise hi chhoda|ignore karu"),
        ("fees", r"\bfee\b|\bfees\b|\bexpense\b|\bter\b|\bcost\b|kharcha|mehenga|charges"),
        ("overlap", r"\boverlap\b|\bduplicate\b|\bsame stocks\b|same companies|same fund|dohraya|repeat investment"),
        ("returns", r"\bxirr\b|\breturn\b|\breturns\b|\bperformance\b|\bundperform|return kitna|kaisa perform|profit"),
        ("fund", r"\bwhich fund\b|\bproblem fund\b|\bmain fund\b|\bwhat fund\b|kaunsa fund|kis fund|problem wala fund"),
        ("confidence", r"\bconfidence\b|\bhow sure\b|kitne sure|kitna sure"),
        ("summary", r"\bsummary\b|\baction\b|\bportfolio\b|\bresult\b|\banalysis\b|batao|kya karu|kya result hai"),
    ]
    for intent, pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return intent
    return "unknown"


def _fees_response(metrics: dict[str, Any], decision_output: dict[str, Any], language: str) -> str:
    primary = _get_primary_metrics(decision_output, metrics)
    fees = primary.get("expense_ratio") or metrics.get("portfolio_metrics", {}).get("average_expense_ratio", 0)
    bleed = primary.get("wealth_bleed_10yr") or 0
    if language == "hinglish":
        if bleed > 0:
            return f"Aap <b>{fees:.1f}%</b> fees de rahe ho. Isi wajah se 10 saal me <b>{_currency(bleed)}</b> wealth kam ho sakti hai."
        return f"Aap <b>{fees:.1f}%</b> fees de rahe ho, jo low-cost options se kaafi zyada hai."
    if bleed > 0:
        return f"You are paying <b>{fees:.1f}%</b> fees, which can reduce wealth by <b>{_currency(bleed)}</b> over 10 years."
    return f"You are paying <b>{fees:.1f}%</b> fees, which is much higher than low-cost options."


def _overlap_response(metrics: dict[str, Any], decision_output: dict[str, Any], language: str) -> str:
    primary = _get_primary_metrics(decision_output, metrics)
    overlap = primary.get("max_overlap_score") or metrics.get("portfolio_metrics", {}).get("max_portfolio_overlap", 0)
    if language == "hinglish":
        return f"Aapke portfolio me <b>{overlap:.0f}%</b> overlap hai. Matlab multiple funds same stocks kharid rahe hain."
    return f"Your portfolio has <b>{overlap:.0f}%</b> overlap. That means multiple funds are buying the same stocks."


def _returns_response(metrics: dict[str, Any], language: str) -> str:
    overall_xirr = metrics.get("portfolio_metrics", {}).get("overall_xirr")
    if overall_xirr is None:
        if language == "hinglish":
            return "Abhi valid return figure analysis me available nahi hai."
        return "I can't answer that. The current analysis does not have a valid return figure."
    if language == "hinglish":
        return f"Aapka overall XIRR <b>{overall_xirr:.2f}%</b> hai. Yeh current portfolio ka annualized return signal hai."
    return f"Your overall XIRR is <b>{overall_xirr:.2f}%</b>. That is the annualized return signal for the current portfolio."


def _fund_response(decision_output: dict[str, Any], language: str) -> str:
    fund_name = decision_output.get("primary_fund") or "the current portfolio"
    action = decision_output.get("action", "KEEP")
    if language == "hinglish":
        return f"Primary focus <b>{fund_name}</b> hai, aur current recommended action <b>{action}</b> hai."
    return f"The main focus is <b>{fund_name}</b>, and the current recommended action is <b>{action}</b>."


def _confidence_response(decision_output: dict[str, Any], language: str) -> str:
    confidence = decision_output.get("confidence", "LOW")
    if language == "hinglish":
        return f"Current confidence <b>{confidence}</b> hai, based on the extracted data and deterministic rules."
    return f"The current confidence is <b>{confidence}</b>, based on the extracted data and deterministic rules."


def _get_primary_metrics(decision_output: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    primary_name = decision_output.get("primary_fund")
    for fund in metrics.get("fund_metrics", []):
        if fund.get("fund_name") == primary_name:
            return fund
    return metrics.get("fund_metrics", [{}])[0] if metrics.get("fund_metrics") else {}


def _currency(value: float) -> str:
    if value >= 100000:
        return f"₹{value / 100000:.1f}L"
    if value >= 1000:
        return f"₹{value / 1000:.0f}K"
    return f"₹{value:.0f}"


def _refusal(language: str) -> str:
    return REFUSAL_MESSAGE_HINGLISH if language == "hinglish" else REFUSAL_MESSAGE
