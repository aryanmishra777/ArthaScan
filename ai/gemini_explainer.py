from __future__ import annotations

import json
import os
from typing import Any

RESPONSE_CACHE: dict[str, str] = {}



ALLOWED_RESPONSE_TYPES = {"why", "simple", "move", "inaction", "define"}
ALLOWED_CHAT_INTENTS = {
    "why",
    "simple",
    "move",
    "inaction",
    "fees",
    "overlap",
    "returns",
    "fund",
    "confidence",
    "summary",
    "lang_hinglish",
    "lang_english",
    "define",
}
FORBIDDEN_TERMS = {
    "bitcoin",
    "crypto",
    "stock tip",
    "guaranteed",
    "tomorrow",
    "next year",
    "prediction",
    "buy this",
    "sell everything",
    "multibagger",
}


def generate_gemini_explanation(
    response_type: str,
    decision_output: dict[str, Any],
    metrics: dict[str, Any],
    language: str,
    fallback_message: str,
) -> str:
    if not _gemini_enabled() or response_type not in ALLOWED_RESPONSE_TYPES:
        return fallback_message

    client = _get_client()
    if client is None:
        return fallback_message

    model_name = _model_name()
    payload = _build_payload(response_type, decision_output, metrics, language)
    prompt = _build_prompt(response_type, payload, language)

    if prompt in RESPONSE_CACHE:
        return RESPONSE_CACHE[prompt]

    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        text = _normalize_response_text(getattr(response, "text", "") or "")
        if text:
            RESPONSE_CACHE[prompt] = text
            return text
        return fallback_message
    except Exception:
        return fallback_message


def generate_guarded_gemini_chat(
    user_text: str,
    decision_output: dict[str, Any],
    metrics: dict[str, Any],
    language: str,
    fallback_message: str,
) -> str:
    if not _gemini_enabled():
        return fallback_message

    client = _get_client()
    if client is None:
        return fallback_message

    payload = _build_payload("chat", decision_output, metrics, language)
    prompt = (
        "You are a conversational AI assistant for ArthaScan, a deterministic portfolio analyzer.\n"
        "You can greet the user and explain your capabilities.\n"
        "You may explain standard financial terms (like XIRR, Expense Ratio, Overlap, NAV) in simple terms if asked.\n"
        "You are encouraged to explain HOW metrics (like Health Score, XIRR, Overlap) and 'confidence scores' are calculated to build trust and transparency.\n"
        "For portfolio questions, you may only answer using the uploaded portfolio analysis.\n"
        "Do not introduce new numbers, predictions, or stock-specific advice.\n"
        "Do not change the recommended action.\n"
        "If the question is completely unrelated to mutual funds, your capabilities, or the portfolio, reply exactly with: I can't answer that.\n"
        "Maximum 60 words.\n"
        f"Language: {language}\n"
        f"User question: {user_text}\n"
        f"Payload: {payload}\n"
        "Return only the final message."
    )

    if prompt in RESPONSE_CACHE:
        return RESPONSE_CACHE[prompt]

    try:
        response = client.models.generate_content(model=_model_name(), contents=prompt)
        text = _normalize_response_text(getattr(response, "text", "") or "")
        if not _validate_guarded_response(text, payload):
            return "Main uska answer nahi de sakta." if language == "hinglish" else "I can't answer that."
        if text:
            RESPONSE_CACHE[prompt] = text
            return text
        return fallback_message
    except Exception:
        return fallback_message


def classify_intent_with_gemini(
    user_text: str,
    decision_output: dict[str, Any],
    metrics: dict[str, Any],
    language: str,
) -> tuple[str | None, float]:
    if not _gemini_enabled():
        return None, 0.0

    client = _get_client()
    if client is None:
        return None, 0.0

    payload = _build_payload("intent", decision_output, metrics, language)
    prompt = (
        "You are an intent classifier for ArthaScan.\n"
        "Choose exactly one intent from this whitelist:\n"
        f"{sorted(ALLOWED_CHAT_INTENTS)}\n"
        "If the message is unrelated to the uploaded portfolio analysis, set allowed=false.\n"
        "Return strict JSON only with keys: allowed, intent, confidence.\n"
        f"User message: {user_text}\n"
        f"Payload: {payload}\n"
    )

    try:
        response = client.models.generate_content(model=_model_name(), contents=prompt)
        raw_text = getattr(response, "text", "") or ""
        data = _parse_json_response(raw_text)
        intent = str(data.get("intent", "")).strip().lower()
        allowed = bool(data.get("allowed"))
        confidence = float(data.get("confidence", 0) or 0)
        if not allowed or intent not in ALLOWED_CHAT_INTENTS:
            return None, confidence
        return intent, confidence
    except Exception:
        return None, 0.0


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
    except Exception:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def _model_name() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"


def _gemini_enabled() -> bool:
    return os.getenv("USE_GEMINI_EXPLANATIONS", "true").strip().lower() in {"1", "true", "yes", "on"}


def _build_payload(
    response_type: str,
    decision_output: dict[str, Any],
    metrics: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    primary_fund = decision_output.get("primary_fund")
    primary_metrics = {}
    for fund_metric in metrics.get("fund_metrics", []):
        if fund_metric.get("fund_name") == primary_fund:
            primary_metrics = fund_metric
            break
    if not primary_metrics:
        primary_metrics = metrics.get("fund_metrics", [{}])[0] if metrics.get("fund_metrics") else {}

    return {
        "response_type": response_type,
        "language": language,
        "action": decision_output.get("action", "KEEP"),
        "issues": decision_output.get("issues", []),
        "confidence": decision_output.get("confidence", "LOW"),
        "fund_name": primary_fund or primary_metrics.get("fund_name", "Portfolio"),
        "expense_ratio": primary_metrics.get("expense_ratio"),
        "benchmark_difference": primary_metrics.get("benchmark_difference"),
        "max_overlap_score": primary_metrics.get("max_overlap_score"),
        "wealth_bleed_10yr": primary_metrics.get("wealth_bleed_10yr"),
        "portfolio_overlap": metrics.get("portfolio_metrics", {}).get("max_portfolio_overlap"),
        "average_expense_ratio": metrics.get("portfolio_metrics", {}).get("average_expense_ratio"),
    }


def _build_prompt(response_type: str, payload: dict[str, Any], language: str) -> str:
    language_name = "Hinglish" if language == "hinglish" else "English"
    return (
        "You are a constrained explanation layer for ArthaScan, a deterministic mutual fund analyzer.\n"
        "Rules:\n"
        "- Do not calculate anything.\n"
        "- Do not change the action.\n"
        "- Do not add facts not present in the payload.\n"
        "- Do not give open-ended investment advice.\n"
        "- Output one short message only.\n"
        "- Maximum 40 words.\n"
        "- Keep it suitable for Telegram.\n"
        f"- Write in {language_name}.\n"
        "- Use simple language.\n"
        "- Preserve HTML <b> tags only if you include numbers.\n"
        f"- Focus only on the '{response_type}' explanation intent.\n\n"
        f"Payload: {payload}\n\n"
        "Return only the final message."
    )


def _normalize_response_text(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return ""
    words = cleaned.split()
    if len(words) > 40:
        cleaned = " ".join(words[:40]).rstrip(".,;:") + "."
    return cleaned


def _validate_guarded_response(text: str, payload: dict[str, Any]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if any(term in lowered for term in FORBIDDEN_TERMS):
        return False
    if len(text.split()) > 60:
        return False
    return True


def _parse_json_response(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found")
    return json.loads(text[start : end + 1])
