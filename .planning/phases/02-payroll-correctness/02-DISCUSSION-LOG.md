# Phase 2: Payroll Correctness — Discussion Log

**Date:** 2026-03-28
**Status:** Complete

---

## Area 1: Mirror-Fallback-Strategie

**Q: Was soll passieren wenn payroll_service.py keinen ContractHistory-Eintrag findet?**
Options: Hard fail (422) / Soft-Fehler im Report / Mirror-Felder als Notfallwert
→ **Soft-Fehler im Report**

**Q: Gilt 'Soft-Fehler' auch für compliance_service.py und pdf_service.py?**
Options: Alle Dienste überspringen + Warning / Nur payroll Soft-Fehler
→ **Alle Dienste: überspringen + Warning**

**Q: Soll Planner eine Migration für die 5 SJ-Mitarbeiter ohne CH anlegen?**
Options: Nein — manuell ausfüllen / Ja — Placeholder-Migration
→ **Nein — manuell ausfüllen**

---

## Area 2: DEBT-04 Demo-Trennung

**Q: Was ist das konkrete Problem auf dem VPS?**
Options: Demo-Daten landen im Produktions-Tenant / Kein Route-Guard / Prävention
→ **Demo-Daten landen im Produktions-Tenant**

**Q: Wie soll das verhindert werden?**
Options: seed_demo.py erzwingt eigenen Tenant / Konfigurations-Guard via ENV
→ **seed_demo.py erzwingt eigenen Tenant**

**Q: Gibt es Demo-Mitarbeiter die bereinigt werden müssen?**
Options: Nein — kein Bereinigungsbedarf / Ja — braucht SQL-Cleanup
→ **Nein — kein Bereinigungsbedarf**

---

## Area 3: assign_contract_type Scope

**Q: Soll fix auch für create_employee Endpoint gelten?**
Options: Ja — beide Pfade / Nur assign-Endpoint
→ **Ja — beide Pfade**
