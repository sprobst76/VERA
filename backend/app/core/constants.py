"""Zentrale, jahresbezogene Sozialversicherungs-/Minijob-Konstanten.

Vorher an 7 Stellen dupliziert (compliance_service, payroll_service,
matching_service, pdf_service, reports.py, schemas/employee.py,
models/employee.py) — bei einer Gesetzesänderung musste jede Stelle
einzeln gefunden und angepasst werden.

Bei einer neuen Minijob-Grenze: neuen Jahres-Eintrag in
MINIJOB_ANNUAL_LIMIT_BY_YEAR ergänzen, MINIJOB_ANNUAL_LIMIT_CURRENT
auf das neue Jahr zeigen lassen.
"""

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
