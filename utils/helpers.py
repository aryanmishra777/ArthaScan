from __future__ import annotations

from pathlib import Path
from typing import Any


def ensure_tmp_dir() -> Path:
    tmp_dir = Path.cwd() / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir


def safe_delete(path: str | Path) -> None:
    target = Path(path)
    if target.exists():
        target.unlink()


def create_result_keyboard(language: str = "english") -> InlineKeyboardMarkup:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    english_label = "English ✅" if language == "english" else "English"
    hinglish_label = "Hinglish ✅" if language == "hinglish" else "Hinglish"
    buttons = [
        [
            InlineKeyboardButton(english_label, callback_data="lang_english"),
            InlineKeyboardButton(hinglish_label, callback_data="lang_hinglish"),
        ],
        [InlineKeyboardButton("Why this decision?", callback_data="why_decision")],
        [InlineKeyboardButton("Where should I move this?", callback_data="where_move")],
        [InlineKeyboardButton("What happens if I do nothing?", callback_data="do_nothing")],
        [InlineKeyboardButton("Explain this simply", callback_data="explain_simple")],
        [InlineKeyboardButton("Download detailed report", callback_data="download_report")],
    ]
    return InlineKeyboardMarkup(buttons)


def format_currency(value: float | int | None) -> str:
    if value is None:
        return "₹0"
    amount = float(value)
    absolute = abs(amount)
    if absolute >= 100000:
        return f"₹{amount / 100000:.1f}L"
    if absolute >= 1000:
        return f"₹{amount / 1000:.0f}K"
    return f"₹{amount:.0f}"


def generate_report(
    decision_output: dict[str, Any],
    metrics: dict[str, Any],
    output_path: str | Path,
    english_text: str,
    hinglish_text: str,
) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    target = Path(output_path)
    base_font, bold_font = _register_report_fonts(pdfmetrics, TTFont)
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#102a43"),
        alignment=1,
        spaceAfter=10,
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName=bold_font,
        fontSize=12,
        leading=14,
        textColor=colors.HexColor("#102a43"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName=base_font,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#243b53"),
    )
    body_bold = ParagraphStyle(
        "BodyBold",
        parent=body,
        fontName=bold_font,
    )
    hero = ParagraphStyle(
        "Hero",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#b42318"),
        alignment=1,
        spaceAfter=6,
    )
    hero_sub = ParagraphStyle(
        "HeroSub",
        parent=body,
        alignment=1,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#52606d"),
        spaceAfter=10,
    )
    small = ParagraphStyle(
        "Small",
        parent=body,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#52606d"),
    )
    action_heading = ParagraphStyle(
        "ActionHeading",
        parent=section_heading,
        fontSize=14,
        leading=16,
        textColor=colors.HexColor("#9a3412"),
        spaceBefore=12,
        spaceAfter=8,
    )

    document = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    primary_fund = decision_output.get("primary_fund") or "Portfolio"
    portfolio = metrics["portfolio_metrics"]
    primary_metrics = _get_primary_metrics(decision_output, metrics)
    hero_title, hero_subtitle = _build_report_hero(decision_output, primary_metrics)
    metrics_table = _build_metrics_table(portfolio, body, body_bold)
    action_table = _build_action_table(decision_output, primary_fund, body, body_bold)
    top_issues = _build_report_issues(decision_output, metrics)
    hinglish_lines = _split_report_lines(hinglish_text)
    health_score = portfolio.get("health_score")

    story = [
        Paragraph("ArthaScan — Portfolio Analysis Report", title),
        Paragraph(f"Focus Fund: {_safe_report_text(primary_fund)}", body),
        Paragraph(f"Confidence: {_safe_report_text(decision_output.get('confidence', 'LOW'))}", small),
        Spacer(1, 12),
    ]

    # Health score display
    if health_score is not None:
        score_label = _health_score_label(health_score)
        score_bar = _health_score_bar(health_score)
        story.append(
            Paragraph(
                f"<b>Portfolio Health Score: {health_score}/100</b>  {score_bar}  ({score_label})",
                ParagraphStyle(
                    "HealthScore",
                    parent=body_bold,
                    fontSize=14,
                    leading=18,
                    textColor=_health_score_color(health_score, colors),
                    alignment=1,
                    spaceBefore=6,
                    spaceAfter=10,
                ),
            )
        )

    story.extend(
        [
            Paragraph(hero_title, hero),
            Paragraph(hero_subtitle, hero_sub),
            Spacer(1, 12),
            Paragraph("Key Metrics", section_heading),
            metrics_table,
            Spacer(1, 12),
            Paragraph("Top Issues", section_heading),
        ]
    )

    for issue in top_issues:
        story.append(Paragraph(f"• {_safe_report_text(issue)}", body))

    story.extend(
        [
            Spacer(1, 12),
            Paragraph("Recommended Action", action_heading),
            action_table,
        ]
    )

    # Per-fund action breakdown table (big wow factor)
    fund_decisions = decision_output.get("fund_decisions", [])
    if fund_decisions:
        story.extend(
            [
                Spacer(1, 12),
                Paragraph("Fund-by-Fund Breakdown", section_heading),
                _build_fund_breakdown_table(fund_decisions, metrics, body, body_bold, colors, Paragraph, Table, TableStyle),
            ]
        )

    story.extend(
        [
            Spacer(1, 12),
            Paragraph("Hinglish Version", section_heading),
        ]
    )

    for line in hinglish_lines[:4]:
        story.append(Paragraph(_safe_report_text(line), body))

    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "This report is generated using deterministic financial analysis. "
            "No assumptions or market predictions are used. Powered by ArthaScan.",
            small,
        )
    )

    document.build(story)
    return target


def _register_report_fonts(pdfmetrics, TTFont) -> tuple[str, str]:
    candidates = [
        ("Arial", "C:/Windows/Fonts/arial.ttf", "Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"),
        ("Calibri", "C:/Windows/Fonts/calibri.ttf", "Calibri-Bold", "C:/Windows/Fonts/calibrib.ttf"),
        ("LiberationSans", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "LiberationSans-Bold", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    for base_name, base_path, bold_name, bold_path in candidates:
        if Path(base_path).exists() and Path(bold_path).exists():
            try:
                pdfmetrics.registerFont(TTFont(base_name, base_path))
                pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                return base_name, bold_name
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold"


def _build_report_hero(decision_output: dict[str, Any], primary_metrics: dict[str, Any]) -> tuple[str, str]:
    wealth_bleed = primary_metrics.get("wealth_bleed_10yr") or 0
    action = decision_output.get("action", "KEEP")
    if wealth_bleed > 0:
        return (
            f"YOU ARE LOSING {format_currency(wealth_bleed)} OVER 10 YEARS",
            "due to high fees and inefficient fund selection",
        )
    if action == "KEEP":
        return ("YOUR PORTFOLIO LOOKS HEALTHY", "with low friction and stable fund selection")
    return (f"{action} IS RECOMMENDED", "based on deterministic portfolio analysis")


def _build_metrics_table(portfolio: dict[str, Any], body, body_bold):
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    rows = [
        [
            Paragraph("XIRR", body_bold),
            Paragraph(f"{_format_percent(portfolio.get('overall_xirr'))} {_interpret_xirr(portfolio.get('overall_xirr'))}", body),
        ],
        [
            Paragraph("Fees", body_bold),
            Paragraph(f"{_format_percent(portfolio.get('average_expense_ratio'))} {_interpret_fees(portfolio.get('average_expense_ratio'))}", body),
        ],
        [
            Paragraph("Overlap", body_bold),
            Paragraph(f"{_format_percent(portfolio.get('max_portfolio_overlap'))} {_interpret_overlap(portfolio.get('max_portfolio_overlap'))}", body),
        ],
    ]
    table = Table(rows, colWidths=[90, 140])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f4f8")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#d9e2ec")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _build_action_table(decision_output: dict[str, Any], primary_fund: str, body, body_bold):
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    action = decision_output.get("action", "KEEP")
    if action == "SELL":
        lines = [
            f"SELL {_safe_report_text(primary_fund)}",
            "Move to a low-cost index fund (~0.1% fees) to maintain exposure",
        ]
    elif action == "SWITCH":
        lines = [
            f"SWITCH {_safe_report_text(primary_fund)}",
            "Move to a low-cost index fund (~0.1% fees) to maintain exposure",
        ]
    elif action == "CONSOLIDATE":
        lines = [
            "CONSOLIDATE duplicate funds",
            "Keep one strong fund and remove redundant exposure",
        ]
    else:
        lines = [
            "KEEP current investments",
            "No immediate portfolio change is required",
        ]

    content = Paragraph(
        f"<b>{_safe_report_text(lines[0])}</b><br/>{_safe_report_text(lines[1])}",
        body,
    )
    table = Table([[content]], colWidths=[520])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff7ed")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#f59e0b")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def _build_report_issues(decision_output: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    primary_metrics = _get_primary_metrics(decision_output, metrics)
    issues: list[str] = []
    overlap = primary_metrics.get("max_overlap_score") or metrics.get("portfolio_metrics", {}).get("max_portfolio_overlap", 0)
    fees = primary_metrics.get("expense_ratio") or metrics.get("portfolio_metrics", {}).get("average_expense_ratio", 0)
    benchmark_gap = primary_metrics.get("benchmark_difference")
    r_squared = primary_metrics.get("r_squared")

    if fees:
        issues.append(f"You are paying {fees:.2f}% in fees, which is well above low-cost options (~0.1%)")
    if r_squared is not None and r_squared >= 0.9:
        issues.append("Fund behaves very similar to the index, with low differentiation for an active-fee product")
    if overlap >= 40:
        issues.append(f"{overlap:.0f}% overlap means multiple funds are buying the same stocks")
    if benchmark_gap is not None and benchmark_gap < 0:
        issues.append(f"The fund is underperforming the benchmark by {abs(benchmark_gap):.2f}%")
    if not issues:
        issues.append("The portfolio does not show a major structural red flag in this run")
    if len(issues) == 1:
        if overlap > 0:
            issues.append(f"{overlap:.0f}% overlap suggests some duplication, but it is not the primary issue")
        else:
            issues.append("Portfolio structure looks stable, but fees should still be watched closely")
    return issues[:2]


def _split_report_lines(text: str) -> list[str]:
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = line.replace("🚨", "").replace("⚡", "").replace("✅", "").replace("⚠️", "").strip()
        cleaned_lines.append(line)
    return cleaned_lines


def _safe_report_text(text: Any) -> str:
    return str(text).replace("■", "").strip()


def _format_percent(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.2f}%"


def _interpret_xirr(value: Any) -> str:
    if value is None:
        return "(not available)"
    numeric = float(value)
    if numeric >= 15:
        return "(strong returns)"
    if numeric >= 8:
        return "(healthy returns)"
    if numeric >= 0:
        return "(muted returns)"
    return "(negative returns)"


def _interpret_fees(value: Any) -> str:
    if value is None:
        return "(not available)"
    numeric = float(value)
    if numeric > 1.0:
        return "(high vs low-cost options)"
    if numeric > 0.5:
        return "(acceptable, but not low-cost)"
    return "(low-cost)"


def _interpret_overlap(value: Any) -> str:
    if value is None:
        return "(not available)"
    numeric = float(value)
    if numeric > 60:
        return "(critical duplication)"
    if numeric >= 40:
        return "(high duplication)"
    if numeric > 0:
        return "(moderate duplication)"
    return "(well diversified)"


def _get_primary_metrics(decision_output: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    primary_name = decision_output.get("primary_fund")
    for fund in metrics.get("fund_metrics", []):
        if fund.get("fund_name") == primary_name:
            return fund
    return metrics.get("fund_metrics", [{}])[0] if metrics.get("fund_metrics") else {}


def _health_score_label(score: int) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Needs Attention"
    return "Critical"


def _health_score_bar(score: int) -> str:
    filled = round(score / 10)
    return "█" * filled + "░" * (10 - filled)


def _health_score_color(score: int, colors) -> Any:
    if score >= 80:
        return colors.HexColor("#16a34a")
    if score >= 60:
        return colors.HexColor("#ca8a04")
    if score >= 40:
        return colors.HexColor("#ea580c")
    return colors.HexColor("#dc2626")


def _build_fund_breakdown_table(
    fund_decisions: list[dict[str, Any]],
    metrics: dict[str, Any],
    body,
    body_bold,
    colors,
    Paragraph,
    Table,
    TableStyle,
) -> Any:
    """Build a per-fund action breakdown table for the PDF report."""
    header_row = [
        Paragraph("<b>Fund Name</b>", body_bold),
        Paragraph("<b>Action</b>", body_bold),
        Paragraph("<b>Issue</b>", body_bold),
        Paragraph("<b>Fees</b>", body_bold),
        Paragraph("<b>Overlap</b>", body_bold),
    ]
    rows = [header_row]

    action_colors = {
        "SELL": colors.HexColor("#fecaca"),
        "SWITCH": colors.HexColor("#fed7aa"),
        "CONSOLIDATE": colors.HexColor("#fef08a"),
        "KEEP": colors.HexColor("#bbf7d0"),
    }

    for fund_entry in fund_decisions:
        fund_name = fund_entry.get("fund_name", "Unknown")
        decision = fund_entry.get("decision", {})
        fund_metrics = fund_entry.get("metrics", {})
        action = decision.get("action", "KEEP")
        issues = decision.get("issues", [])
        fees = fund_metrics.get("expense_ratio", 0)
        overlap = fund_metrics.get("max_overlap_score", 0)

        rows.append(
            [
                Paragraph(_safe_report_text(fund_name), body),
                Paragraph(f"<b>{action}</b>", body_bold),
                Paragraph(_safe_report_text(issues[0] if issues else "—"), body),
                Paragraph(f"{fees:.2f}%", body),
                Paragraph(f"{overlap:.0f}%", body),
            ]
        )

    table = Table(rows, colWidths=[160, 70, 120, 55, 55])
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#102a43")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#d9e2ec")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]

    # Color-code each data row by action
    for row_index, fund_entry in enumerate(fund_decisions, start=1):
        action = fund_entry.get("decision", {}).get("action", "KEEP")
        bg_color = action_colors.get(action, colors.white)
        style_commands.append(("BACKGROUND", (0, row_index), (-1, row_index), bg_color))

    table.setStyle(TableStyle(style_commands))
    return table
