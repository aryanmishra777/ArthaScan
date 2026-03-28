from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import ExtractionResult

DATE_PATTERN = re.compile(r"(\d{2}[/-](?:\d{2}|[A-Za-z]{3})[/-]\d{4})")
NUMBER_PATTERN = re.compile(r"\d[\d,]*\.?\d*")
FUND_NAME_PATTERN = re.compile(
    r"(?i).*(fund|scheme|small cap|mid cap|large cap|equity|balanced|flexi cap|index).*"
)
TRANSACTION_PAIR_PATTERN = re.compile(
    r"(\d{2}[/-](?:\d{2}|[A-Za-z]{3})[/-]\d{4})\s*[₹■]?\s*([\d,]+(?:\.\d+)?)"
)
SUMMARY_VALUE_PATTERN = re.compile(r"[₹■]?\s*([\d,]+(?:\.\d+)?)")

DEMO_FUND_ENRICHMENT: dict[str, dict[str, Any]] = {
    "axis bluechip fund (regular)": {
        "expense_ratio": 1.5,
        "benchmark_return": 12.0,
        "historical_returns": [0.75, 0.68, 0.71, 0.64, 0.67, 0.63],
        "benchmark_returns": [0.82, 0.74, 0.79, 0.72, 0.75, 0.73],
        "holdings": {"HDFC Bank": 9, "Infosys": 8, "ICICI Bank": 7, "TCS": 6},
    },
    "mirae asset large cap fund (regular)": {
        "expense_ratio": 1.4,
        "benchmark_return": 12.0,
        "historical_returns": [0.77, 0.7, 0.72, 0.66, 0.68, 0.64],
        "benchmark_returns": [0.82, 0.74, 0.79, 0.72, 0.75, 0.73],
        "holdings": {"HDFC Bank": 8, "Infosys": 7, "Reliance": 6, "ICICI Bank": 5},
    },
    "nifty 50 index fund (direct)": {
        "expense_ratio": 0.2,
        "benchmark_return": 12.0,
        "historical_returns": [0.82, 0.74, 0.79, 0.72, 0.75, 0.73],
        "benchmark_returns": [0.82, 0.74, 0.79, 0.72, 0.75, 0.73],
        "holdings": {"HDFC Bank": 8, "Reliance": 8, "Infosys": 7, "ICICI Bank": 6},
    },
    "flexi cap fund (direct)": {
        "expense_ratio": 0.6,
        "benchmark_return": 12.5,
        "historical_returns": [0.9, 0.81, 0.88, 0.76, 0.83, 0.79],
        "benchmark_returns": [0.8, 0.72, 0.77, 0.7, 0.74, 0.72],
        "holdings": {"Bharti Airtel": 7, "Larsen & Toubro": 6, "HDFC Bank": 5, "Infosys": 4},
    },
    "icici bluechip fund (regular)": {
        "expense_ratio": 1.5,
        "benchmark_return": 12.0,
        "historical_returns": [0.7, 0.65, 0.68, 0.62, 0.63, 0.61],
        "benchmark_returns": [0.81, 0.73, 0.78, 0.71, 0.74, 0.72],
        "holdings": {"HDFC Bank": 8, "Infosys": 7, "Reliance": 6, "ICICI Bank": 5},
    },
    "sbi bluechip fund (regular)": {
        "expense_ratio": 1.5,
        "benchmark_return": 12.0,
        "historical_returns": [0.69, 0.64, 0.67, 0.61, 0.62, 0.6],
        "benchmark_returns": [0.81, 0.73, 0.78, 0.71, 0.74, 0.72],
        "holdings": {"HDFC Bank": 8, "Infosys": 7, "TCS": 6, "ICICI Bank": 5},
    },
    "hdfc top 100 fund (regular)": {
        "expense_ratio": 1.4,
        "benchmark_return": 12.0,
        "historical_returns": [0.68, 0.63, 0.66, 0.6, 0.61, 0.59],
        "benchmark_returns": [0.81, 0.73, 0.78, 0.71, 0.74, 0.72],
        "holdings": {"HDFC Bank": 7, "Infosys": 7, "Reliance": 6, "ICICI Bank": 5},
    },
    "small cap fund (regular)": {
        "expense_ratio": 1.6,
        "benchmark_return": 13.0,
        "historical_returns": [0.52, 0.48, 0.5, 0.43, 0.45, 0.42],
        "benchmark_returns": [0.8, 0.74, 0.78, 0.71, 0.73, 0.7],
        "holdings": {"ABC Smallcap": 6, "XYZ Industrials": 5, "PQR Finance": 4},
    },
    "elss fund (regular)": {
        "expense_ratio": 1.5,
        "benchmark_return": 12.5,
        "historical_returns": [0.56, 0.5, 0.54, 0.46, 0.48, 0.45],
        "benchmark_returns": [0.79, 0.72, 0.76, 0.7, 0.72, 0.69],
        "holdings": {"ABC Smallcap": 5, "PQR Finance": 4, "Tax Saver Ltd": 6},
    },
}


class ExtractionError(RuntimeError):
    """Raised when deterministic extraction cannot produce usable data."""


def extract_pdf_to_json(pdf_path: str | Path) -> dict[str, Any]:
    import logging

    logger = logging.getLogger(__name__)
    from pypdf import PdfReader

    pdf_file = Path(pdf_path)
    if pdf_file.suffix.lower() != ".pdf":
        raise ExtractionError("invalid file type")

    # Strategy 1: Gemini Vision extraction (spec-mandated primary path)
    try:
        from .vision_extractor import extract_pdf_with_vision

        vision_result = extract_pdf_with_vision(pdf_file)
        if vision_result is not None:
            result = ExtractionResult.model_validate(vision_result)
            if result.funds:
                logger.info("Vision extraction succeeded with %d funds", len(result.funds))
                return result.model_dump()
    except Exception as exc:
        logger.warning("Vision extraction path failed, falling back to text: %s", exc)

    # Strategy 2: Text-based regex extraction (fallback)
    logger.info("Using text-based regex extraction as fallback")
    reader = PdfReader(str(pdf_file))
    extracted_pages: list[dict[str, Any]] = []

    for page in reader.pages[:2]:
        page_text = page.extract_text() or ""
        extracted_pages.append({"funds": _extract_with_placeholder_model(page_text)})

    merged = merge_funds_by_name(extracted_pages)
    result = ExtractionResult.model_validate(merged)
    if not result.funds:
        raise ExtractionError("no funds detected")
    return result.model_dump()


def merge_funds_by_name(extracted_pages: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}

    for page in extracted_pages:
        for fund in page.get("funds", []):
            normalized_name = _normalize_fund_name(fund.get("fund_name", ""))
            if not normalized_name:
                continue

            target = merged.setdefault(
                normalized_name,
                {
                    "fund_name": fund["fund_name"].strip(),
                    "plan_type": fund.get("plan_type"),
                    "expense_ratio": fund.get("expense_ratio"),
                    "transactions": [],
                    "holdings": [],
                    "current_value": fund.get("current_value"),
                },
            )

            if target["plan_type"] is None and fund.get("plan_type") is not None:
                target["plan_type"] = fund["plan_type"]
            if target["expense_ratio"] is None and fund.get("expense_ratio") is not None:
                target["expense_ratio"] = fund["expense_ratio"]
            if target["current_value"] is None and fund.get("current_value") is not None:
                target["current_value"] = fund["current_value"]

            existing_transactions = {
                (
                    transaction.get("date"),
                    transaction.get("amount"),
                    transaction.get("extraction_status"),
                )
                for transaction in target["transactions"]
            }
            for transaction in fund.get("transactions", []):
                signature = (
                    transaction.get("date"),
                    transaction.get("amount"),
                    transaction.get("extraction_status"),
                )
                if signature not in existing_transactions:
                    target["transactions"].append(transaction)
                    existing_transactions.add(signature)

            existing_holdings = {
                (_normalize_holding_name(holding.get("stock_name", "")), holding.get("weight"))
                for holding in target["holdings"]
            }
            for holding in fund.get("holdings", []):
                signature = (_normalize_holding_name(holding.get("stock_name", "")), holding.get("weight"))
                if signature[0] and signature not in existing_holdings:
                    target["holdings"].append(holding)
                    existing_holdings.add(signature)

    return {"funds": list(merged.values())}


def transform_extracted_data(extracted_data: dict[str, Any]) -> list[dict[str, Any]]:
    result = ExtractionResult.model_validate(extracted_data)
    transformed: list[dict[str, Any]] = []

    for fund in result.funds:
        enrichment = _fuzzy_enrich(_normalize_fund_name(fund.fund_name))
        transactions = [
            {"date": transaction.date, "amount": transaction.amount}
            for transaction in fund.transactions
            if transaction.date is not None and transaction.amount is not None
        ]
        holdings = {
            holding.stock_name: holding.weight
            for holding in fund.holdings
            if holding.stock_name and holding.weight is not None
        }
        if not holdings:
            holdings = enrichment.get("holdings", {})
        transformed.append(
            {
                "fund_name": fund.fund_name,
                "transactions": transactions,
                "holdings": holdings,
                "expense_ratio": fund.expense_ratio
                if fund.expense_ratio is not None
                else enrichment.get("expense_ratio", _default_expense_ratio(fund.plan_type, fund.fund_name)),
                "benchmark_return": enrichment.get("benchmark_return", 12.0),
                "historical_returns": enrichment.get("historical_returns"),
                "benchmark_returns": enrichment.get("benchmark_returns"),
                "current_value": fund.current_value,
                "plan_type": fund.plan_type,
            }
        )

    if not transformed:
        raise ExtractionError("transformation produced no funds")
    return transformed


def _extract_with_placeholder_model(page_text: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    funds: list[dict[str, Any]] = []
    current_fund: dict[str, Any] | None = None
    summary_queue: list[str] = []
    pending_transaction_date: str | None = None

    for line in lines:
        normalized_line = _clean_text(line)
        if _is_fund_name(normalized_line):
            if current_fund:
                funds.append(current_fund)
            current_fund = {
                "fund_name": normalized_line,
                "plan_type": _extract_plan_type(normalized_line),
                "expense_ratio": _extract_expense_ratio(normalized_line),
                "transactions": [],
                "holdings": [],
                "current_value": None,
            }
            summary_queue = []
            pending_transaction_date = None
            continue

        if current_fund is None:
            continue

        lower_line = normalized_line.lower()

        if lower_line == "units":
            summary_queue = ["units"]
            continue
        if lower_line == "invested amount":
            if summary_queue == ["units"]:
                summary_queue.append("invested")
            continue
        if lower_line == "current value":
            if summary_queue == ["units", "invested"]:
                summary_queue.append("current")
            else:
                summary_queue = ["current"]
            continue

        inline_current = _extract_labeled_amount(normalized_line, ("current value", "current"))
        if inline_current is not None:
            current_fund["current_value"] = inline_current
            if "transactions:" in lower_line:
                current_fund["transactions"].extend(_extract_inline_transactions(normalized_line))
            continue

        if lower_line.startswith("transactions:"):
            current_fund["transactions"].extend(_extract_inline_transactions(normalized_line))
            pending_transaction_date = None
            continue
        if lower_line in {"transactions", "date", "amount"}:
            continue

        if summary_queue:
            summary_values = _extract_all_numbers(normalized_line)
            if summary_values:
                for value in summary_values:
                    if not summary_queue:
                        break
                    label = summary_queue.pop(0)
                    if label == "current":
                        current_fund["current_value"] = value
                if not summary_queue:
                    continue

        maybe_date = _extract_date(normalized_line)
        if maybe_date is not None and _line_is_just_date(normalized_line):
            pending_transaction_date = maybe_date
            continue

        maybe_amount = _extract_amount_without_date(normalized_line)
        if pending_transaction_date is not None and maybe_amount is not None:
            current_fund["transactions"].append(
                {
                    "date": pending_transaction_date,
                    "amount": maybe_amount,
                    "extraction_status": "confident",
                }
            )
            pending_transaction_date = None
            continue

        if maybe_date is not None and maybe_amount is not None:
            current_fund["transactions"].append(
                {
                    "date": maybe_date,
                    "amount": maybe_amount,
                    "extraction_status": _resolve_status(maybe_date, maybe_amount),
                }
            )

    if current_fund:
        funds.append(current_fund)

    return funds


def _extract_date(value: str) -> str | None:
    match = DATE_PATTERN.search(value)
    if not match:
        return None
    raw = match.group(1).replace("-", "/")
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d/%b/%Y"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _extract_number(value: str) -> float | None:
    cleaned = _clean_text(value).replace("Rs.", "").replace("INR", "").replace("₹", "")
    numbers = NUMBER_PATTERN.findall(cleaned)
    if not numbers:
        return None
    for raw in reversed(numbers):
        try:
            return float(raw.replace(",", ""))
        except ValueError:
            continue
    return None


def _extract_plan_type(value: str) -> str | None:
    upper = value.upper()
    if "DIRECT" in upper:
        return "DIRECT"
    if "REGULAR" in upper:
        return "REGULAR"
    return None


def _extract_expense_ratio(value: str) -> float | None:
    lower = value.lower()
    if "expense" not in lower and "%" not in lower:
        return None
    return _extract_number(value)


def _resolve_status(maybe_date: str | None, maybe_amount: float | None) -> str:
    if maybe_date is not None and maybe_amount is not None:
        return "confident"
    if maybe_date is not None or maybe_amount is not None:
        return "partial_answer"
    return "no_answer"


def _default_expense_ratio(plan_type: str | None, fund_name: str = "") -> float:
    name = fund_name.lower()
    if any(k in name for k in ("index", "nifty", "sensex", "etf", "bees")):
        return 0.1 if plan_type == "DIRECT" else 0.2
    if "liquid" in name or "overnight" in name:
        return 0.1 if plan_type == "DIRECT" else 0.3
    if plan_type == "DIRECT":
        return 0.6
    if plan_type == "REGULAR":
        return 1.5
    return 1.0


def _fuzzy_enrich(normalized_name: str) -> dict[str, Any]:
    best_score = 0.0
    best_match: str | None = None
    name_words = set(normalized_name.split())
    if not name_words:
        return {}

    for key in DEMO_FUND_ENRICHMENT:
        key_words = set(key.replace("(", "").replace(")", "").split())
        if not key_words:
            continue
        score = len(key_words & name_words) / len(key_words)
        if score > best_score:
            best_score = score
            best_match = key

    if best_score >= 0.70 and best_match:
        return DEMO_FUND_ENRICHMENT[best_match]
    return {}


def _normalize_fund_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _normalize_holding_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _clean_text(value: str) -> str:
    return value.replace("■", "").replace("\u25a0", "").replace("₹", "₹").strip()


def _is_fund_name(line: str) -> bool:
    if not FUND_NAME_PATTERN.match(line) or len(line) <= 6:
        return False
    lower = line.lower()
    blocked_prefixes = ("transactions", "investor", "period", "note", "notes", "disclaimer")
    return not lower.startswith(blocked_prefixes)


def _extract_all_numbers(value: str) -> list[float]:
    matches = SUMMARY_VALUE_PATTERN.findall(_clean_text(value))
    parsed: list[float] = []
    for raw in matches:
        try:
            parsed.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return parsed


def _extract_labeled_amount(value: str, labels: tuple[str, ...]) -> float | None:
    lower = value.lower()
    for label in labels:
        if label in lower:
            match = re.search(rf"{re.escape(label)}\s*[:|]?\s*[₹]?\s*([\d,]+(?:\.\d+)?)", lower, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(",", ""))
                except ValueError:
                    return None
    return None


def _extract_inline_transactions(value: str) -> list[dict[str, Any]]:
    transactions: list[dict[str, Any]] = []
    for raw_date, raw_amount in TRANSACTION_PAIR_PATTERN.findall(_clean_text(value)):
        parsed_date = _extract_date(raw_date)
        if parsed_date is None:
            continue
        try:
            amount = float(raw_amount.replace(",", ""))
        except ValueError:
            continue
        transactions.append(
            {
                "date": parsed_date,
                "amount": amount,
                "extraction_status": "confident",
            }
        )
    return transactions


def _line_is_just_date(value: str) -> bool:
    return DATE_PATTERN.fullmatch(value.strip()) is not None


def _extract_amount_without_date(value: str) -> float | None:
    stripped = DATE_PATTERN.sub("", _clean_text(value)).strip()
    if not stripped:
        return None
    return _extract_number(stripped)
