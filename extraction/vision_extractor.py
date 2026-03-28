"""Gemini Vision-based PDF extraction engine.

Converts PDF pages → high-resolution images → Gemini Vision → structured JSON.
Includes a self-healing repair loop (up to 2 retries) and strict Pydantic validation.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from .schema import ExtractionResult

logger = logging.getLogger(__name__)

MAX_PAGES = 2
MAX_REPAIR_RETRIES = 2
IMAGE_DPI = 200

EXTRACTION_SYSTEM_PROMPT = (
    "You are a deterministic financial data extraction engine.\n"
    "Your ONLY output must be a valid JSON object.\n"
    "No explanations, no markdown, no extra text.\n\n"
    "If any value is unreadable or missing:\n"
    "→ return null\n"
    "→ set extraction_status appropriately\n\n"
    "Do NOT guess.\n"
)

EXTRACTION_RULES = (
    "Rules:\n"
    "- Extract all mutual funds separately\n"
    "- Group transactions under correct fund\n"
    "- Convert dates to YYYY-MM-DD\n"
    "- Convert numbers to float (remove commas)\n"
    "- Normalize plan_type to DIRECT or REGULAR\n"
    "- Ignore non-financial entries\n"
    "- If unsure → return null, set extraction_status = \"ambiguous\"\n\n"
    "Return JSON strictly matching this schema:\n"
    "{\n"
    '  "funds": [\n'
    "    {\n"
    '      "fund_name": "string",\n'
    '      "plan_type": "DIRECT | REGULAR | null",\n'
    '      "expense_ratio": "number | null",\n'
    '      "transactions": [\n'
    "        {\n"
    '          "date": "YYYY-MM-DD | null",\n'
    '          "amount": "number | null",\n'
    '          "extraction_status": "confident | partial_answer | ambiguous | no_answer"\n'
    "        }\n"
    "      ],\n"
    '      "holdings": [\n'
    "        {\n"
    '          "stock_name": "string",\n'
    '          "weight": "number | null"\n'
    "        }\n"
    "      ],\n"
    '      "current_value": "number | null"\n'
    "    }\n"
    "  ]\n"
    "}\n"
)

REPAIR_PROMPT = (
    "The following JSON failed validation. Fix it so it matches the schema exactly. "
    "Return ONLY valid JSON, no markdown, no explanation.\n\n"
    "Schema requires: funds[] → fund_name (string), plan_type (DIRECT|REGULAR|null), "
    "expense_ratio (number|null), transactions[] (date YYYY-MM-DD|null, amount number|null, "
    "extraction_status confident|partial_answer|ambiguous|no_answer), "
    "holdings[] (stock_name string, weight number|null), current_value (number|null).\n\n"
    "Broken JSON:\n"
)


def extract_pdf_with_vision(pdf_path: str | Path) -> dict[str, Any] | None:
    """Extract structured fund data from a PDF using Gemini Vision.

    Returns validated extraction result dict, or None if vision extraction fails.
    """
    if not _vision_enabled():
        logger.info("Vision extraction disabled (GEMINI_API_KEY not set)")
        return None

    try:
        page_images = _pdf_to_images(Path(pdf_path))
    except Exception as exc:
        logger.warning("PDF to image conversion failed: %s", exc)
        return None

    if not page_images:
        logger.warning("No page images produced from PDF")
        return None

    client = _get_client()
    if client is None:
        return None

    all_page_extractions: list[dict[str, Any]] = []
    model_name = _model_name()

    for page_index, image_bytes in enumerate(page_images):
        logger.info("Vision extracting page %d/%d...", page_index + 1, len(page_images))
        page_result = _extract_single_page(client, model_name, image_bytes, page_index)
        if page_result is not None:
            all_page_extractions.append(page_result)

    if not all_page_extractions:
        logger.warning("Vision extraction produced no results from any page")
        return None

    # Merge pages and validate
    from .extractor import merge_funds_by_name

    merged = merge_funds_by_name(all_page_extractions)

    try:
        result = ExtractionResult.model_validate(merged)
        if not result.funds:
            logger.warning("Vision extraction merged result has no funds")
            return None
        logger.info(
            "Vision extraction successful: %d funds extracted",
            len(result.funds),
        )
        return result.model_dump()
    except Exception as exc:
        logger.warning("Vision extraction final validation failed: %s", exc)
        return None


def _extract_single_page(
    client: Any,
    model_name: str,
    image_bytes: bytes,
    page_index: int,
) -> dict[str, Any] | None:
    """Extract from a single page image with repair retries."""
    prompt = (
        f"{EXTRACTION_SYSTEM_PROMPT}\n"
        f"{EXTRACTION_RULES}\n"
        f"Extract all mutual fund data from this CAMS/KFintech statement page (page {page_index + 1})."
    )

    try:
        from google.genai import types

        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                prompt,
            ],
        )
        raw_text = getattr(response, "text", "") or ""
        parsed = _parse_json_from_response(raw_text)

        # Validate immediately
        try:
            ExtractionResult.model_validate(parsed)
            return parsed
        except Exception:
            pass

        # Self-healing repair loop
        for retry in range(MAX_REPAIR_RETRIES):
            logger.info("Repair attempt %d for page %d", retry + 1, page_index + 1)
            repaired = _repair_json(client, model_name, raw_text)
            if repaired is not None:
                try:
                    ExtractionResult.model_validate(repaired)
                    return repaired
                except Exception:
                    raw_text = json.dumps(repaired)

        logger.warning("Final validation failed for page %d after all repairs, returning None", page_index + 1)
        return None

    except Exception as exc:
        logger.warning("Vision extraction failed for page %d: %s", page_index + 1, exc)
        return None


def _repair_json(client: Any, model_name: str, broken_json: str) -> dict[str, Any] | None:
    """Send broken JSON to Gemini for repair."""
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=f"{REPAIR_PROMPT}{broken_json}",
        )
        raw = getattr(response, "text", "") or ""
        return _parse_json_from_response(raw)
    except Exception as exc:
        logger.warning("JSON repair call failed: %s", exc)
        return None


def _pdf_to_images(pdf_path: Path) -> list[bytes]:
    """Convert PDF pages to PNG images using PyMuPDF."""
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    images: list[bytes] = []

    for page_index in range(min(len(doc), MAX_PAGES)):
        page = doc[page_index]
        # Render at target DPI (default is 72, so scale factor = DPI/72)
        zoom = IMAGE_DPI / 72
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix)
        images.append(pixmap.tobytes("png"))

    doc.close()
    return images


def _parse_json_from_response(raw_text: str) -> dict[str, Any]:
    """Parse JSON from LLM response, stripping markdown fences."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in response")
    return json.loads(text[start : end + 1])


def _vision_enabled() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def _get_client() -> Any | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai

        return genai.Client(api_key=api_key)
    except Exception:
        return None


def _model_name() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
