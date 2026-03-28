from __future__ import annotations

from html import escape
from typing import Any

from utils.helpers import format_currency


def format_response(
    decision_output: dict[str, Any],
    metrics: dict[str, Any],
    language: str = "english",
) -> str:
    language_key = "hinglish" if language.lower() == "hinglish" else "english"
    primary_metrics = _get_primary_metrics(decision_output, metrics)
    action = decision_output.get("action", "KEEP")
    confidence = decision_output.get("confidence", "LOW")

    if "MISSING_DATA" in metrics.get("portfolio_metrics", {}).get("top_issues", []) and action == "KEEP":
        return _format_incomplete(language_key)

    emoji = "✅" if action == "KEEP" else "🚨"
    health_score = metrics.get("portfolio_metrics", {}).get("health_score")
    key_insight = _build_key_insight(language_key, action, primary_metrics, metrics)
    findings = _build_findings(language_key, action, primary_metrics, metrics)[:2]
    action_line = _build_action_line(language_key, action)

    parts = []
    if health_score is not None:
        parts.append(_build_health_score_display(health_score, language_key))
    parts.extend(
        [
            f"{emoji} {key_insight}",
            "\n".join(findings),
            f"⚡ {action_line}",
            f"Confidence: {escape(confidence)}",
        ]
    )
    return "\n\n".join(parts)


def format_callback_response(
    response_type: str,
    decision_output: dict[str, Any],
    metrics: dict[str, Any],
    language: str = "english",
) -> str:
    language_key = "hinglish" if language.lower() == "hinglish" else "english"
    primary_metrics = _get_primary_metrics(decision_output, metrics)
    expense_ratio = primary_metrics.get("expense_ratio") or metrics["portfolio_metrics"].get("average_expense_ratio", 0)
    benchmark_gap = abs(primary_metrics.get("benchmark_difference") or 0)
    overlap = primary_metrics.get("max_overlap_score") or metrics["portfolio_metrics"].get("max_portfolio_overlap", 0)
    wealth_bleed = primary_metrics.get("wealth_bleed_10yr") or 0

    english_responses = {
        "why": _build_why_response("english", expense_ratio, benchmark_gap, overlap),
        "move": (
            f"Move this money to a low-cost index fund or direct plan. Fees can drop from "
            f"<b>{expense_ratio:.1f}%</b> to about <b>0.1%</b>."
        ),
        "inaction": _build_inaction_response("english", wealth_bleed, expense_ratio, overlap),
        "simple": _build_simple_response("english", overlap, expense_ratio),
    }
    hinglish_responses = {
        "why": _build_why_response("hinglish", expense_ratio, benchmark_gap, overlap),
        "move": (
            f"Is paisa ko low-cost index fund ya direct plan me le jao. Fees "
            f"<b>{expense_ratio:.1f}%</b> se <b>0.1%</b> ke paas aa sakti hai."
        ),
        "inaction": _build_inaction_response("hinglish", wealth_bleed, expense_ratio, overlap),
        "simple": _build_simple_response("hinglish", overlap, expense_ratio),
    }
    responses = hinglish_responses if language_key == "hinglish" else english_responses
    return responses[response_type]


def _format_incomplete(language: str) -> str:
    if language == "hinglish":
        return (
            "⚠️ Humein portfolio ko sahi tarah analyze karne ke liye aur data chahiye.\n\n"
            "• Kuch fund details missing hain\n"
            "• Hum fees ya duplication ko accurately map nahi kar pa rahe\n\n"
            "⚡ <b>UPDATE</b> latest statement upload karo\n\n"
            "Confidence: LOW"
        )
    return (
        "⚠️ We need more data to analyze your portfolio properly.\n\n"
        "• Some fund details are missing\n"
        "• We cannot measure fees or duplication accurately\n\n"
        "⚡ <b>UPDATE</b> your latest statement\n\n"
        "Confidence: LOW"
    )


def _build_key_insight(language: str, action: str, primary_metrics: dict[str, Any], metrics: dict[str, Any]) -> str:
    wealth_bleed = primary_metrics.get("wealth_bleed_10yr") or 0
    overlap = primary_metrics.get("max_overlap_score") or metrics["portfolio_metrics"].get("max_portfolio_overlap", 0)
    fees = primary_metrics.get("expense_ratio") or metrics["portfolio_metrics"].get("average_expense_ratio", 0)

    if action == "KEEP":
        if language == "hinglish":
            return "Aapka portfolio healthy lag raha hai aur long term ke liye track par hai."
        return "Your portfolio looks healthy and on track for the long term."

    if wealth_bleed > 0:
        if language == "hinglish":
            return (
                f"Aap 10 saal me <b>{format_currency(wealth_bleed)}</b> lose kar rahe ho "
                "high fees aur duplicate investments ki wajah se."
            )
        return (
            f"You are losing <b>{format_currency(wealth_bleed)}</b> over 10 years "
            "due to high fees and duplicate investments."
        )

    if overlap >= 40:
        if language == "hinglish":
            return f"Aapke portfolio me <b>{overlap:.0f}%</b> duplicate investments dikh rahi hain."
        return f"Your portfolio shows <b>{overlap:.0f}%</b> duplicate investments."
    if language == "hinglish":
        return f"Aap <b>{fees:.1f}%</b> fees de rahe ho jo long-term returns ko kam kar rahi hai."
    return f"You are paying <b>{fees:.1f}%</b> fees that reduce your long-term returns."


def _build_findings(language: str, action: str, primary_metrics: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    overlap = primary_metrics.get("max_overlap_score") or metrics["portfolio_metrics"].get("max_portfolio_overlap", 0)
    fees = primary_metrics.get("expense_ratio") or metrics["portfolio_metrics"].get("average_expense_ratio", 0)
    benchmark_gap = primary_metrics.get("benchmark_difference")

    if action == "KEEP":
        if language == "hinglish":
            return [
                f"• Fees low hain at around <b>{fees:.1f}%</b>",
                "• Portfolio simple hai aur unnecessary duplication nahi dikhti",
            ]
        return [
            f"• Your fees are low at around <b>{fees:.1f}%</b>",
            "• The portfolio stays simple without unnecessary duplication",
        ]

    findings: list[str] = []
    wealth_bleed = primary_metrics.get("wealth_bleed_10yr") or 0
    metric_used_in_insight = wealth_bleed > 0 or overlap >= 40 or fees > 0
    if wealth_bleed > 0 and overlap >= 40:
        if language == "hinglish":
            findings.append(
                f"• <b>{overlap:.0f}%</b> overlap hai, matlab same stocks multiple funds me hain"
            )
        else:
            findings.append(
                f"• <b>{overlap:.0f}%</b> of your portfolio sits in duplicate investments"
            )
    elif not metric_used_in_insight and fees > 0:
        if language == "hinglish":
            findings.append(f"• Aap <b>{fees:.1f}%</b> fees de rahe ho jo returns ko kha rahi hai")
        else:
            findings.append(f"• You are paying <b>{fees:.1f}%</b> in fees that eat into returns")
    if len(findings) < 2:
        if language == "hinglish":
            if fees > 0 and wealth_bleed > 0:
                findings.append(f"• Aap <b>{fees:.1f}%</b> fees de rahe ho, jo long-term returns ko reduce kar rahi hain")
            elif benchmark_gap is not None:
                findings.append("• Fund market se peeche hai aur extra value nahi de raha")
            else:
                findings.append("• Duplicate ya costly funds portfolio ko inefficient bana dete hain")
        else:
            if fees > 0 and wealth_bleed > 0:
                findings.append(f"• You are paying <b>{fees:.1f}%</b> fees, which is cutting your long-term returns")
            elif benchmark_gap is not None:
                findings.append("• The fund trails the market and adds no extra value")
            else:
                findings.append("• Duplicate or costly funds make the portfolio less efficient")
    return findings[:2]


def _build_action_line(language: str, action: str) -> str:
    messages = {
        "english": {
            "SELL": "<b>SELL</b> this fund and move to a low-cost option",
            "SWITCH": "<b>SWITCH</b> this fund to a low-cost index fund (~0.1% fees)",
            "CONSOLIDATE": "<b>CONSOLIDATE</b> these duplicate funds and keep one strong option",
            "KEEP": "<b>KEEP</b> your current investments",
        },
        "hinglish": {
            "SELL": "<b>SELL</b> karo aur low-cost option me shift ho jao",
            "SWITCH": "<b>SWITCH</b> karke low-cost index fund (~0.1% fees) lo",
            "CONSOLIDATE": "<b>CONSOLIDATE</b> karo aur ek strong fund rakho",
            "KEEP": "<b>KEEP</b> karo aur current investments continue rakho",
        },
    }
    return messages[language].get(action, messages[language]["KEEP"])


def _build_health_score_display(score: int, language: str) -> str:
    """Build a visual health score gauge."""
    filled = round(score / 10)
    bar = "█" * filled + "░" * (10 - filled)

    if score >= 80:
        grade = "Excellent"
        grade_hi = "Behtareen"
        grade_emoji = "💚"
    elif score >= 60:
        grade = "Good"
        grade_hi = "Achha"
        grade_emoji = "💛"
    elif score >= 40:
        grade = "Needs Attention"
        grade_hi = "Dhyan Do"
        grade_emoji = "🧡"
    else:
        grade = "Critical"
        grade_hi = "Khatarnak"
        grade_emoji = "❤️"

    if language == "hinglish":
        return (
            f"{grade_emoji} <b>Portfolio Health Score: {score}/100</b>\n"
            f"{bar}  ({grade_hi})"
        )
    return (
        f"{grade_emoji} <b>Portfolio Health Score: {score}/100</b>\n"
        f"{bar}  ({grade})"
    )


def _get_primary_metrics(decision_output: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    primary_name = decision_output.get("primary_fund")
    for fund in metrics.get("fund_metrics", []):
        if fund["fund_name"] == primary_name:
            return fund
    return metrics.get("fund_metrics", [{}])[0] if metrics.get("fund_metrics") else {}


def _build_why_response(language: str, expense_ratio: float, benchmark_gap: float, overlap: float) -> str:
    if language == "hinglish":
        if benchmark_gap > 0.1:
            return (
                f"Aap <b>{expense_ratio:.1f}%</b> fees de rahe ho aur fund market se "
                f"<b>{benchmark_gap:.1f}%</b> peeche hai. Aap zyada de rahe ho aur kam paa rahe ho."
            )
        if overlap >= 40:
            return (
                f"Aap <b>{expense_ratio:.1f}%</b> fees de rahe ho aur <b>{overlap:.0f}%</b> "
                "duplicate exposure le rahe ho. Isme extra value nahi mil rahi."
            )
        return f"Aap <b>{expense_ratio:.1f}%</b> fees de rahe ho bina clear extra benefit ke. Yeh returns ko kam karta hai."
    if benchmark_gap > 0.1:
        return (
            f"You are paying <b>{expense_ratio:.1f}%</b> fees and the fund trails the market by "
            f"<b>{benchmark_gap:.1f}%</b>. You are paying more and getting less."
        )
    if overlap >= 40:
        return (
            f"You are paying <b>{expense_ratio:.1f}%</b> fees and carrying <b>{overlap:.0f}%</b> "
            "duplicate exposure. That adds cost without enough benefit."
        )
    return f"You are paying <b>{expense_ratio:.1f}%</b> fees without a clear extra benefit. That reduces returns."


def _build_inaction_response(language: str, wealth_bleed: float, expense_ratio: float, overlap: float) -> str:
    if language == "hinglish":
        if wealth_bleed > 0:
            return f"Agar aap kuch nahi karte, to 10 saal me <b>{format_currency(wealth_bleed)}</b> lose ho sakta hai fees ya duplication se."
        if overlap >= 40:
            return f"Agar aap kuch nahi karte, to <b>{overlap:.0f}%</b> duplicate exposure portfolio ko inefficient rakhega."
        return f"Agar aap kuch nahi karte, to <b>{expense_ratio:.1f}%</b> fees long-term wealth ko kam karti rahegi."
    if wealth_bleed > 0:
        return f"If you do nothing, you may lose <b>{format_currency(wealth_bleed)}</b> over 10 years from fees or duplicate investments."
    if overlap >= 40:
        return f"If you do nothing, your <b>{overlap:.0f}%</b> duplicate exposure will keep the portfolio inefficient."
    return f"If you do nothing, <b>{expense_ratio:.1f}%</b> fees will keep reducing your long-term wealth."


def _build_simple_response(language: str, overlap: float, expense_ratio: float) -> str:
    if language == "hinglish":
        if overlap >= 40:
            return (
                f"Aap same stocks ko multiple funds me le rahe ho. <b>{overlap:.0f}%</b> overlap "
                "aur extra fees returns ko kam karte hain."
            )
        return f"Yeh fund simple terms me mehenga hai. Aap <b>{expense_ratio:.1f}%</b> fees de rahe ho, isliye returns kam hote hain."
    if overlap >= 40:
        return (
            f"You own similar stocks across funds with <b>{overlap:.0f}%</b> overlap. "
            "That duplication and extra fees lower your final wealth."
        )
    return f"This is mainly a cost problem. You are paying <b>{expense_ratio:.1f}%</b> in fees, which lowers returns."
