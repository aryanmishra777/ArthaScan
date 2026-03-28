from __future__ import annotations

import math
from datetime import date, datetime
from statistics import mean
from typing import Any


def calculate_xirr(transactions: list[dict[str, Any]], current_value: float | None) -> float | None:
    if not transactions or current_value is None or current_value <= 0:
        return None

    cashflows: list[tuple[date, float]] = []
    for transaction in transactions:
        tx_date = _parse_date(transaction.get("date"))
        amount = transaction.get("amount")
        if tx_date is None or amount is None:
            continue
        cashflows.append((tx_date, -abs(float(amount))))

    if not cashflows:
        return None

    final_date = max(tx_date for tx_date, _ in cashflows)
    cashflows.append((final_date, abs(float(current_value))))

    if not (any(amount < 0 for _, amount in cashflows) and any(amount > 0 for _, amount in cashflows)):
        return None

    low = -0.9999
    high = 1.0
    low_value = _xnpv(low, cashflows)
    high_value = _xnpv(high, cashflows)

    while low_value * high_value > 0 and high < 100:
        high *= 2
        high_value = _xnpv(high, cashflows)

    if low_value * high_value > 0:
        return None

    for _ in range(120):
        mid = (low + high) / 2
        mid_value = _xnpv(mid, cashflows)
        if abs(mid_value) < 1e-6:
            return round(mid * 100, 2)
        if low_value * mid_value <= 0:
            high = mid
            high_value = mid_value
        else:
            low = mid
            low_value = mid_value

    return round(((low + high) / 2) * 100, 2)


def calculate_overlap(
    holdings_a: dict[str, float] | list[dict[str, Any]],
    holdings_b: dict[str, float] | list[dict[str, Any]],
) -> float:
    normalized_a = _normalize_holdings(holdings_a)
    normalized_b = _normalize_holdings(holdings_b)
    if not normalized_a or not normalized_b:
        return 0.0

    overlap = 0.0
    for stock_name, weight_a in normalized_a.items():
        weight_b = normalized_b.get(stock_name)
        if weight_b is not None:
            overlap += min(weight_a, weight_b)
    return round(overlap, 2)


def calculate_wealth_bleed(
    principal: float | None,
    gross_return: float | None,
    expense_ratio: float | None,
    alt_ter: float = 0.1,
    years: int = 10,
) -> float:
    if principal is None or principal <= 0 or gross_return is None or expense_ratio is None:
        return 0.0

    gross_rate = gross_return / 100
    current_net = max(gross_rate - (expense_ratio / 100), -0.99)
    low_cost_net = max(gross_rate - (alt_ter / 100), -0.99)

    current_future_value = principal * ((1 + current_net) ** years)
    low_cost_future_value = principal * ((1 + low_cost_net) ** years)
    return round(max(low_cost_future_value - current_future_value, 0.0), 2)


def compute_alpha_r_squared(
    historical_returns: list[float] | None,
    benchmark_returns: list[float] | None,
) -> tuple[float | None, float | None]:
    if not historical_returns or not benchmark_returns:
        return None, None

    count = min(len(historical_returns), len(benchmark_returns))
    if count < 3:
        return None, None

    fund_returns = [_normalize_return(value) for value in historical_returns[:count]]
    benchmark = [_normalize_return(value) for value in benchmark_returns[:count]]

    fund_mean = mean(fund_returns)
    benchmark_mean = mean(benchmark)
    fund_variance = mean([(value - fund_mean) ** 2 for value in fund_returns])
    benchmark_variance = mean([(value - benchmark_mean) ** 2 for value in benchmark])
    if fund_variance == 0 or benchmark_variance == 0:
        return None, None

    covariance = mean(
        [
            (fund_returns[index] - fund_mean) * (benchmark[index] - benchmark_mean)
            for index in range(count)
        ]
    )
    correlation = covariance / math.sqrt(fund_variance * benchmark_variance)
    r_squared = max(min(correlation**2, 1.0), 0.0)
    alpha = (fund_mean - benchmark_mean) * 12 * 100
    return round(alpha, 2), round(r_squared, 2)


def compute_portfolio_metrics(funds: list[dict[str, Any]]) -> dict[str, Any]:
    fund_metrics: list[dict[str, Any]] = []
    all_cashflows: list[dict[str, Any]] = []
    current_values: list[float] = []
    expense_ratios: list[float] = []
    top_issues: list[str] = []
    missing_data = False

    overlaps: dict[tuple[int, int], float] = {}
    for left_index, left_fund in enumerate(funds):
        for right_index in range(left_index + 1, len(funds)):
            overlap = calculate_overlap(left_fund.get("holdings", {}), funds[right_index].get("holdings", {}))
            overlaps[(left_index, right_index)] = overlap

    max_portfolio_overlap = max(overlaps.values(), default=0.0)

    for index, fund in enumerate(funds):
        xirr = calculate_xirr(fund.get("transactions", []), fund.get("current_value"))
        benchmark_return = fund.get("benchmark_return")
        benchmark_difference = None
        if xirr is not None and benchmark_return is not None:
            benchmark_difference = round(xirr - float(benchmark_return), 2)

        alpha, r_squared = compute_alpha_r_squared(
            fund.get("historical_returns"),
            fund.get("benchmark_returns"),
        )
        max_overlap_score = max(
            [score for pair, score in overlaps.items() if index in pair],
            default=0.0,
        )

        principal = fund.get("current_value")
        if principal is None:
            principal = sum(
                float(transaction.get("amount", 0) or 0)
                for transaction in fund.get("transactions", [])
            )
        gross_return = xirr if xirr is not None else benchmark_return
        wealth_bleed = calculate_wealth_bleed(principal, gross_return, fund.get("expense_ratio"))

        flags = {
            "is_expensive": bool((fund.get("expense_ratio") or 0) > 1.0),
            "is_underperforming": bool(benchmark_difference is not None and benchmark_difference < -1.5),
            "is_high_overlap": bool(max_overlap_score > 40),
            "is_critical_overlap": bool(max_overlap_score > 60),
            "is_closet_indexer": bool(r_squared is not None and r_squared > 0.90),
            "is_value_destroyer": bool(alpha is not None and alpha < 0),
        }
        flags["is_strong_sell"] = bool(flags["is_closet_indexer"] and alpha is not None and alpha <= 0)
        flags["is_expensive_tracker"] = bool(flags["is_closet_indexer"] and flags["is_expensive"])

        if fund.get("expense_ratio") is not None:
            expense_ratios.append(float(fund["expense_ratio"]))
        if fund.get("current_value") is not None:
            current_values.append(float(fund["current_value"]))
        all_cashflows.extend(fund.get("transactions", []))

        if xirr is None and fund.get("expense_ratio") is None:
            missing_data = True

        fund_metrics.append(
            {
                "fund_name": fund["fund_name"],
                "expense_ratio": round(float(fund.get("expense_ratio") or 0.0), 2),
                "xirr": xirr,
                "benchmark_difference": benchmark_difference,
                "alpha": alpha,
                "r_squared": r_squared,
                "max_overlap_score": round(max_overlap_score, 2),
                "wealth_bleed_10yr": wealth_bleed,
                "flags": flags,
            }
        )

    if any(fund["flags"]["is_critical_overlap"] for fund in fund_metrics):
        top_issues.append("CRITICAL_OVERLAP")
    if any(fund["flags"]["is_expensive"] for fund in fund_metrics):
        top_issues.append("HIGH_EXPENSE_DRAG")
    if any(fund["flags"]["is_strong_sell"] for fund in fund_metrics):
        top_issues.append("CLOSET_INDEXING_DETECTED")
    if any(fund["flags"]["is_underperforming"] for fund in fund_metrics):
        top_issues.append("UNDERPERFORMANCE")
    if missing_data:
        top_issues.append("MISSING_DATA")

    overall_current_value = sum(current_values) if current_values else None
    overall_xirr = calculate_xirr(all_cashflows, overall_current_value)
    average_expense_ratio = round(mean(expense_ratios), 2) if expense_ratios else 0.0

    return {
        "portfolio_metrics": {
            "overall_xirr": overall_xirr,
            "average_expense_ratio": average_expense_ratio,
            "max_portfolio_overlap": round(max_portfolio_overlap, 2),
            "top_issues": top_issues,
            "health_score": compute_health_score(fund_metrics, max_portfolio_overlap),
        },
        "fund_metrics": fund_metrics,
    }


def compute_health_score(
    fund_metrics: list[dict[str, Any]],
    max_portfolio_overlap: float,
) -> int:
    """Compute a 0-100 portfolio health score.

    Starts at 100 and deducts penalties for identified issues.
    Higher is better.
    """
    score = 100.0

    if not fund_metrics:
        return 50

    total_flags = {
        "critical_overlap": 0,
        "high_overlap": 0,
        "expensive": 0,
        "closet_indexer": 0,
        "underperforming": 0,
        "value_destroyer": 0,
        "strong_sell": 0,
    }

    for fund in fund_metrics:
        flags = fund.get("flags", {})
        if flags.get("is_critical_overlap"):
            total_flags["critical_overlap"] += 1
        elif flags.get("is_high_overlap"):
            total_flags["high_overlap"] += 1
        if flags.get("is_expensive"):
            total_flags["expensive"] += 1
        if flags.get("is_closet_indexer"):
            total_flags["closet_indexer"] += 1
        if flags.get("is_underperforming"):
            total_flags["underperforming"] += 1
        if flags.get("is_value_destroyer"):
            total_flags["value_destroyer"] += 1
        if flags.get("is_strong_sell"):
            total_flags["strong_sell"] += 1

    num_funds = len(fund_metrics)

    # Overlap penalties (portfolio-wide)
    if max_portfolio_overlap > 60:
        score -= 25
    elif max_portfolio_overlap > 40:
        score -= 12

    # Per-fund penalties (scaled by proportion)
    expensive_ratio = total_flags["expensive"] / num_funds
    score -= expensive_ratio * 20

    closet_ratio = total_flags["closet_indexer"] / num_funds
    score -= closet_ratio * 20

    underperform_ratio = total_flags["underperforming"] / num_funds
    score -= underperform_ratio * 15

    destroyer_ratio = total_flags["value_destroyer"] / num_funds
    score -= destroyer_ratio * 10

    strong_sell_ratio = total_flags["strong_sell"] / num_funds
    score -= strong_sell_ratio * 10

    return max(0, min(100, round(score)))


def _xnpv(rate: float, cashflows: list[tuple[date, float]]) -> float:
    start_date = cashflows[0][0]
    return sum(
        amount / ((1 + rate) ** (((cashflow_date - start_date).days) / 365.0))
        for cashflow_date, amount in cashflows
    )


def _normalize_holdings(holdings: dict[str, float] | list[dict[str, Any]]) -> dict[str, float]:
    if isinstance(holdings, dict):
        items = holdings.items()
    else:
        items = ((item.get("stock_name", ""), item.get("weight")) for item in holdings)

    normalized: dict[str, float] = {}
    for stock_name, weight in items:
        if not stock_name or weight is None:
            continue
        numeric_weight = float(weight)
        if numeric_weight <= 1:
            numeric_weight *= 100
        normalized[" ".join(stock_name.strip().lower().split())] = numeric_weight
    return normalized


def _normalize_return(value: float) -> float:
    numeric = float(value)
    if abs(numeric) > 1:
        return numeric / 100
    return numeric


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
