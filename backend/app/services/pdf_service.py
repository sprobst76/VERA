"""
PDF-Generierung für Lohnzettel (Lohnabrechnung).
Gibt bytes zurück – kein Dateisystem-Storage nötig.
"""
from __future__ import annotations

import io
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable

if TYPE_CHECKING:
    from app.models.payroll import PayrollEntry
    from app.models.employee import Employee


# ── Farben (Catppuccin-inspiriert, druckfreundlich) ──────────────────────────

_NAVY   = colors.HexColor("#1E3A5F")   # Header-Hintergrund
_LIGHT  = colors.HexColor("#F0F4F8")   # Tabellen-Zebrierung
_WHITE  = colors.white
_GRAY   = colors.HexColor("#6B7280")
_GREEN  = colors.HexColor("#16A34A")
_AMBER  = colors.HexColor("#D97706")
_RED    = colors.HexColor("#DC2626")


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

CONTRACT_LABELS = {
    "minijob":   "Minijob",
    "part_time": "Teilzeit",
    "full_time": "Vollzeit",
}

MONTH_NAMES = [
    "", "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]

STATUS_LABELS = {
    "draft":    "Entwurf",
    "approved": "Genehmigt",
    "paid":     "Bezahlt",
}

SURCHARGE_LABELS = {
    "early":   "Frühzuschlag (00–06 Uhr, 12,5 %)",
    "late":    "Spätzuschlag (20–24 Uhr, 12,5 %)",
    "night":   "Nachtzuschlag (23–06 Uhr, 25 %)",
    "weekend": "Wochenend-Zuschlag Sa (25 %)",
    "sunday":  "Sonntagszuschlag (50 %)",
    "holiday": "Feiertagszuschlag (125 %)",
}


def _fmt_euro(val: float | None) -> str:
    if val is None:
        return "–"
    return f"{val:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_hours(val: float | None) -> str:
    if val is None or val == 0.0:
        return "–"
    return f"{val:.2f} h"


def _tbl_style(base: list) -> TableStyle:
    return TableStyle(base)


# ── Haupt-Funktion ────────────────────────────────────────────────────────────

def generate_payslip_pdf(
    entry: "PayrollEntry",
    employee: "Employee",
    tenant_name: str,
) -> bytes:
    """Erstellt einen Lohnzettel als PDF und gibt die Bytes zurück."""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 9
    normal.leading = 13

    heading = ParagraphStyle(
        "heading",
        parent=normal,
        fontSize=11,
        fontName="Helvetica-Bold",
        textColor=_NAVY,
        spaceAfter=4,
    )
    small_gray = ParagraphStyle(
        "small_gray",
        parent=normal,
        fontSize=8,
        textColor=_GRAY,
    )

    month_label = f"{MONTH_NAMES[entry.month.month]} {entry.month.year}"
    emp_name = f"{employee.first_name} {employee.last_name}"
    contract_label = CONTRACT_LABELS.get(employee.contract_type, employee.contract_type)

    story = []
    page_w = A4[0] - 4 * cm  # nutzbare Breite

    # ── Header ────────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph("<font color='white'><b>VERA – Lohnabrechnung</b></font>", styles["Normal"]),
        Paragraph(f"<font color='white'>{tenant_name}</font>", styles["Normal"]),
    ]]
    header_tbl = Table(header_data, colWidths=[page_w * 0.6, page_w * 0.4])
    header_tbl.setStyle(_tbl_style([
        ("BACKGROUND",  (0, 0), (-1, -1), _NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, -1), _WHITE),
        ("FONTNAME",    (0, 0), (0, 0),   "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 11),
        ("ALIGN",       (1, 0), (1, 0),   "RIGHT"),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # ── Mitarbeiter + Monat ───────────────────────────────────────────────────
    info_data = [
        [Paragraph("<b>Mitarbeiter</b>", styles["Normal"]),
         Paragraph(emp_name, styles["Normal"]),
         Paragraph("<b>Monat</b>", styles["Normal"]),
         Paragraph(month_label, styles["Normal"])],
        [Paragraph("<b>Vertragsart</b>", styles["Normal"]),
         Paragraph(contract_label, styles["Normal"]),
         Paragraph("<b>Stundenlohn</b>", styles["Normal"]),
         Paragraph(_fmt_euro(float(employee.hourly_rate)), styles["Normal"])],
        [Paragraph("<b>Status</b>", styles["Normal"]),
         Paragraph(STATUS_LABELS.get(entry.status, entry.status), styles["Normal"]),
         Paragraph("", styles["Normal"]),
         Paragraph("", styles["Normal"])],
    ]
    col_w = page_w / 4
    info_tbl = Table(info_data, colWidths=[col_w * 0.7, col_w * 1.3, col_w * 0.7, col_w * 1.3])
    info_tbl.setStyle(_tbl_style([
        ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",    (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND",  (0, 0), (-1, -1), _LIGHT),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_WHITE, _LIGHT, _WHITE]),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # ── Stunden-Tabelle ───────────────────────────────────────────────────────
    story.append(Paragraph("Stunden", heading))

    hours_rows = [
        ["", "Stunden"],
        ["Geplant",    _fmt_hours(float(entry.planned_hours) if entry.planned_hours else None)],
        ["Gearbeitet", _fmt_hours(float(entry.actual_hours) if entry.actual_hours else None)],
        ["Übertrag",   _fmt_hours(float(entry.carryover_hours) if entry.carryover_hours else 0)],
        ["Bezahlt",    _fmt_hours(float(entry.paid_hours) if entry.paid_hours else None)],
    ]

    surcharge_fields = [
        ("early_hours",   "early"),
        ("late_hours",    "late"),
        ("night_hours",   "night"),
        ("weekend_hours", "weekend"),
        ("sunday_hours",  "sunday"),
        ("holiday_hours", "holiday"),
    ]
    for field, key in surcharge_fields:
        val = float(getattr(entry, field, 0) or 0)
        if val > 0:
            hours_rows.append([SURCHARGE_LABELS[key], _fmt_hours(val)])

    hours_tbl = Table(hours_rows, colWidths=[page_w * 0.7, page_w * 0.3])
    hours_tbl.setStyle(_tbl_style([
        ("BACKGROUND",    (0, 0), (-1, 0),  _NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  _WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (0, -1),  "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ALIGN",         (1, 0), (1, -1),  "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_WHITE, _LIGHT]),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("GRID",          (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
    ]))
    story.append(hours_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # ── Vergütungs-Tabelle ────────────────────────────────────────────────────
    story.append(Paragraph("Vergütung", heading))

    wage_rows = [["", "Betrag"]]

    base = float(entry.base_wage or 0)
    if base > 0:
        wage_rows.append(["Grundlohn", _fmt_euro(base)])

    surcharge_amount_fields = [
        ("early_surcharge",   "early"),
        ("late_surcharge",    "late"),
        ("night_surcharge",   "night"),
        ("weekend_surcharge", "weekend"),
        ("sunday_surcharge",  "sunday"),
        ("holiday_surcharge", "holiday"),
    ]
    for field, key in surcharge_amount_fields:
        val = float(getattr(entry, field, 0) or 0)
        if val > 0:
            wage_rows.append([SURCHARGE_LABELS[key], _fmt_euro(val)])

    # Brutto-Summe fett + hervorgehoben
    wage_rows.append(["Brutto gesamt", _fmt_euro(float(entry.total_gross or 0))])
    gross_row_idx = len(wage_rows) - 1

    wage_tbl = Table(wage_rows, colWidths=[page_w * 0.7, page_w * 0.3])
    wage_style = [
        ("BACKGROUND",    (0, 0),              (-1, 0),              _NAVY),
        ("TEXTCOLOR",     (0, 0),              (-1, 0),              _WHITE),
        ("FONTNAME",      (0, 0),              (-1, 0),              "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0),              (-1, -1),             9),
        ("ALIGN",         (1, 0),              (1, -1),              "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1),             (-1, gross_row_idx - 1), [_WHITE, _LIGHT]),
        ("BACKGROUND",    (0, gross_row_idx),  (-1, gross_row_idx),  _LIGHT),
        ("FONTNAME",      (0, gross_row_idx),  (-1, gross_row_idx),  "Helvetica-Bold"),
        ("TOPPADDING",    (0, 0),              (-1, -1),             4),
        ("BOTTOMPADDING", (0, 0),              (-1, -1),             4),
        ("LEFTPADDING",   (0, 0),              (-1, -1),             6),
        ("RIGHTPADDING",  (0, 0),              (-1, -1),             6),
        ("GRID",          (0, 0),              (-1, -1),             0.25, colors.HexColor("#E5E7EB")),
        ("LINEABOVE",     (0, gross_row_idx),  (-1, gross_row_idx),  0.5, _NAVY),
    ]
    wage_tbl.setStyle(_tbl_style(wage_style))
    story.append(wage_tbl)

    # ── Minijob-Block ─────────────────────────────────────────────────────────
    if employee.contract_type == "minijob":
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("Minijob-Jahresgrenze", heading))

        ytd = float(entry.ytd_gross or 0)
        limit = float(employee.annual_salary_limit or 6672)
        remaining = float(entry.annual_limit_remaining or 0)
        pct = min(ytd / limit * 100, 100) if limit > 0 else 0

        if pct >= 95:
            warn_color = _RED
            warn_text = "⚠ Jahresgrenze nahezu ausgeschöpft!"
        elif pct >= 80:
            warn_color = _AMBER
            warn_text = "Jahresgrenze zu 80 % erreicht"
        else:
            warn_color = _GREEN
            warn_text = ""

        mj_rows = [
            ["YTD-Brutto (kumuliert)", _fmt_euro(ytd)],
            ["Jahresgrenze 2025",      _fmt_euro(limit)],
            ["Verbleibend",            _fmt_euro(remaining)],
            ["Ausschöpfung",           f"{pct:.1f} %"],
        ]
        mj_tbl = Table(mj_rows, colWidths=[page_w * 0.7, page_w * 0.3])
        mj_style_list = [
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("FONTNAME",      (0, 0), (0, -1),  "Helvetica-Bold"),
            ("ALIGN",         (1, 0), (1, -1),  "RIGHT"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_WHITE, _LIGHT]),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("GRID",          (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
        ]
        if pct >= 80:
            mj_style_list.append(("TEXTCOLOR", (1, 2), (1, 2), warn_color))
            mj_style_list.append(("TEXTCOLOR", (1, 3), (1, 3), warn_color))
        mj_tbl.setStyle(_tbl_style(mj_style_list))
        story.append(mj_tbl)

        if warn_text:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph(warn_text, ParagraphStyle(
                "warn", parent=normal, fontSize=8, textColor=warn_color, fontName="Helvetica-Bold"
            )))

    # ── Notizen ───────────────────────────────────────────────────────────────
    if entry.notes:
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("Notizen", heading))
        story.append(Paragraph(entry.notes, normal))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_GRAY))
    story.append(Spacer(1, 0.15 * cm))
    now = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    story.append(Paragraph(
        f"Erstellt am {now} · VERA Schichtplanner · Status: {STATUS_LABELS.get(entry.status, entry.status)}",
        small_gray,
    ))

    doc.build(story)
    return buf.getvalue()
