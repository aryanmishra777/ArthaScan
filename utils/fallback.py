from __future__ import annotations

DEMO_DATA = {
    "xirr": 11.2,
    "overlap": 65.0,
    "expense_ratio": 1.5,
    "alpha": -1.4,
    "wealth_bleed_10yr": 320000.0,
}


def build_demo_finance_output() -> dict:
    return {
        "portfolio_metrics": {
            "overall_xirr": DEMO_DATA["xirr"],
            "average_expense_ratio": DEMO_DATA["expense_ratio"],
            "max_portfolio_overlap": DEMO_DATA["overlap"],
            "health_score": 10,
            "is_demo": True,
            "top_issues": [
                "CRITICAL_OVERLAP",
                "HIGH_EXPENSE_DRAG",
                "CLOSET_INDEXING_DETECTED",
                "UNDERPERFORMANCE",
            ],
        },
        "fund_metrics": [
            {
                "fund_name": "Axis Large Cap Fund",
                "expense_ratio": DEMO_DATA["expense_ratio"],
                "xirr": DEMO_DATA["xirr"],
                "benchmark_difference": -1.8,
                "alpha": DEMO_DATA["alpha"],
                "r_squared": 0.96,
                "max_overlap_score": DEMO_DATA["overlap"],
                "wealth_bleed_10yr": DEMO_DATA["wealth_bleed_10yr"],
                "flags": {
                    "is_expensive": True,
                    "is_underperforming": True,
                    "is_high_overlap": True,
                    "is_critical_overlap": True,
                    "is_closet_indexer": True,
                    "is_value_destroyer": True,
                    "is_strong_sell": True,
                    "is_expensive_tracker": True,
                },
            },
            {
                "fund_name": "Nippon Large Cap Fund",
                "expense_ratio": DEMO_DATA["expense_ratio"],
                "xirr": 10.9,
                "benchmark_difference": -2.1,
                "alpha": -0.8,
                "r_squared": 0.91,
                "max_overlap_score": DEMO_DATA["overlap"],
                "wealth_bleed_10yr": 275000.0,
                "flags": {
                    "is_expensive": True,
                    "is_underperforming": True,
                    "is_high_overlap": True,
                    "is_critical_overlap": True,
                    "is_closet_indexer": True,
                    "is_value_destroyer": True,
                    "is_strong_sell": True,
                    "is_expensive_tracker": True,
                },
            },
        ],
    }
