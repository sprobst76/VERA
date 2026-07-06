"""Zentrale, jahresbezogene Sozialversicherungs-/Minijob-Konstanten.

`money()` rundet Geldbeträge korrekt kaufmännisch (ROUND_HALF_UP) statt mit
Pythons `round()`, das für floats Banker's Rounding nutzt und bei Werten wie
2.675 durch Gleitkomma-Ungenauigkeit sogar auf 2.67 statt 2.68 runden kann —
bei Lohnabrechnung ein reales Cent-Fehlerrisiko, besonders an der
Minijob-Grenze (analog zur Analyse 2026-07-06, Finding "Geld als float statt
Decimal").

Vorher an 7 Stellen dupliziert (compliance_service, payroll_service,
matching_service, pdf_service, reports.py, schemas/employee.py,
models/employee.py) — bei einer Gesetzesänderung musste jede Stelle
einzeln gefunden und angepasst werden.

Bei einer neuen Minijob-Grenze: neuen Jahres-Eintrag in
MINIJOB_ANNUAL_LIMIT_BY_YEAR ergänzen, MINIJOB_ANNUAL_LIMIT_CURRENT
auf das neue Jahr zeigen lassen.
"""
from decimal import Decimal, ROUND_HALF_UP

# Offizielle Minijob-Jahresgrenzen (§8 Abs. 1a SGB IV). Nur ab dem Jahr
# aufgenommen, in dem VERA produktiv genutzt wird — ältere Jahre (2022-2024)
# nicht verifiziert und daher bewusst nicht eingetragen.
MINIJOB_ANNUAL_LIMIT_BY_YEAR: dict[int, float] = {
    2025: 6672.00,
}

MINIJOB_ANNUAL_LIMIT_CURRENT = MINIJOB_ANNUAL_LIMIT_BY_YEAR[2025]
MINIJOB_MONTHLY_LIMIT_CURRENT = MINIJOB_ANNUAL_LIMIT_CURRENT / 12


def minijob_annual_limit(year: int) -> float:
    """Minijob-Jahresgrenze für ein Kalenderjahr.

    Fällt auf die jüngste bekannte Grenze zurück, wenn das Jahr (noch)
    nicht eingetragen ist — sicherer Default als ein KeyError oder eine
    stillschweigend falsche Zahl für zukünftige Jahre.
    """
    known_years = sorted(MINIJOB_ANNUAL_LIMIT_BY_YEAR)
    applicable = max((y for y in known_years if y <= year), default=known_years[0])
    return MINIJOB_ANNUAL_LIMIT_BY_YEAR[applicable]


def money(value: float | int | Decimal) -> float:
    """Rundet einen Geldbetrag kaufmännisch auf 2 Nachkommastellen.

    Ersetzt `round(value, 2)` für Euro-Beträge — Pythons round() auf floats
    nutzt Banker's Rounding (round-half-to-even) und ist zusätzlich von
    Gleitkomma-Repräsentationsfehlern betroffen. `str(value)` vor der
    Decimal-Konstruktion vermeidet genau diese Fehler (Decimal(2.675) wäre
    exakt 2.67499999999999982236..., Decimal(str(2.675)) ist exakt 2.675).
    Gibt bewusst wieder float zurück, da die DB-Spalten (Numeric) und
    bestehenden Schemas (float) unverändert bleiben — nur die Rundung selbst
    wird korrekt.
    """
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
