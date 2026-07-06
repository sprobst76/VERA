"""
Regressionstest für app.core.constants.money() — kaufmännische Rundung statt
Pythons Banker's-Rounding-round() auf floats (Analyse 2026-07-06, "Geld als
float statt Decimal", Rundungsrisiko an der Minijob-Grenze).
"""
from app.core.constants import money


def test_money_fixes_float_round_half_up_bug():
    """round(2.675, 2) == 2.67 in Python (Gleitkomma + Banker's Rounding).
    money() muss korrekt kaufmännisch auf 2.68 runden."""
    assert round(2.675, 2) == 2.67  # dokumentiert den Python-Bug, den money() umgeht
    assert money(2.675) == 2.68


def test_money_rounds_half_up_not_half_even():
    """Banker's Rounding würde 0.125 auf 0.12 runden (gerade Ziffer); kaufmännisch immer aufrunden."""
    assert money(0.125) == 0.13


def test_money_handles_plain_values():
    assert money(100.0) == 100.0
    assert money(0) == 0.0
    assert money(13.999) == 14.0
