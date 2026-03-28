from __future__ import annotations

from typing import Any

ACTION_PRIORITY = {"SELL": 4, "SWITCH": 3, "CONSOLIDATE": 2, "KEEP": 1}


def evaluate_fund(metrics: dict[str, Any]) -> dict[str, Any]:
    flags = metrics.get("flags", {})
    alpha = metrics.get("alpha")
    r_squared = metrics.get("r_squared")
    max_overlap_score = metrics.get("max_overlap_score", 0)

    insufficient_data = alpha is None and r_squared is None and metrics.get("xirr") is None
    if insufficient_data:
        return {
            "action": "KEEP",
            "issues": ["Insufficient Data"],
            "confidence": "LOW",
        }

    issues: list[str] = []
    action = "KEEP"
    confidence = "HIGH"

    if r_squared is not None and r_squared > 0.90 and alpha is not None and alpha <= 0:
        action = "SELL"
        issues.append("Closet Indexer")
        if flags.get("is_expensive"):
            issues.append("High Fees")
    elif max_overlap_score > 60:
        action = "SELL"
        issues.append("Critical Overlap")
        if flags.get("is_expensive"):
            issues.append("High Fees")
    elif flags.get("is_underperforming") and alpha is not None and alpha < 0:
        action = "SELL"
        issues.append("Underperforming Fund")
        issues.append("Below Market")
    elif flags.get("is_expensive"):
        action = "SWITCH"
        issues.append("High Fees")
        if flags.get("is_high_overlap"):
            issues.append("Duplicate Investments")
    elif 40 <= max_overlap_score <= 60:
        action = "CONSOLIDATE"
        issues.append("Moderate Overlap")
        confidence = "MEDIUM"
    else:
        action = "KEEP"
        issues.append("Healthy Fund")

    return {
        "action": action,
        "issues": issues[:2],
        "confidence": confidence,
    }


def evaluate_portfolio(metrics: dict[str, Any]) -> dict[str, Any]:
    fund_decisions = []
    for fund_metric in metrics.get("fund_metrics", []):
        decision = evaluate_fund(fund_metric)
        fund_decisions.append(
            {
                "fund_name": fund_metric["fund_name"],
                "decision": decision,
                "metrics": fund_metric,
            }
        )

    primary = _select_primary_fund(fund_decisions)
    top_issues = metrics.get("portfolio_metrics", {}).get("top_issues", [])
    missing_data = "MISSING_DATA" in top_issues

    if primary is None:
        action = "KEEP"
        issues = ["Healthy Portfolio"]
        confidence = "LOW" if missing_data else "HIGH"
    else:
        action = primary["decision"]["action"]
        issues = primary["decision"]["issues"][:]
        confidence = primary["decision"]["confidence"]

    if not issues and top_issues:
        issues = [issue.replace("_", " ").title() for issue in top_issues[:2]]

    if action == "KEEP":
        if metrics["portfolio_metrics"]["max_portfolio_overlap"] > 40:
            action = "CONSOLIDATE"
            issues = ["Duplicate Investments"]
            confidence = "MEDIUM"
        elif metrics["portfolio_metrics"]["average_expense_ratio"] > 1.25:
            action = "SWITCH"
            issues = ["High Fees"]
            confidence = "HIGH"

    return {
        "action": action,
        "issues": issues[:2],
        "confidence": "LOW" if missing_data and action == "KEEP" else confidence,
        "portfolio_issues": top_issues[:2],
        "primary_fund": primary["fund_name"] if primary else None,
        "fund_decisions": fund_decisions,
    }


def _select_primary_fund(fund_decisions: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not fund_decisions:
        return None

    def sort_key(item: dict[str, Any]) -> tuple[int, float]:
        action = item["decision"]["action"]
        bleed = item["metrics"].get("wealth_bleed_10yr") or 0.0
        return ACTION_PRIORITY.get(action, 0), bleed

    return max(fund_decisions, key=sort_key)
