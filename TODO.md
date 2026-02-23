# VERA – Feature-Backlog

## Schuljahrdienste (Regeltermine)

**Idee:** Ein "Schuljahr-Regeltermin" läuft das gesamte Schuljahr und lässt Ferien und Feiertage automatisch aus. Da jeder Wochentag andere Zeiten haben kann, wird pro Wochentag ein eigener Regeltermin angelegt.

**Kernfunktionen:**
- Regeltermin anlegen: Wochentag, Zeiten, Mitarbeiter, Schuljahr (Start/Ende), Ferien-Profil (BW, BY, …)
- Aus einem Regeltermin werden automatisch alle Einzeldienste für das Schuljahr erzeugt (analog dem heutigen Bulk-Create)
- Feiertage und Schulferien werden beim Generieren übersprungen
- Einzelne Dienste können nachträglich abweichend geändert werden (Ausnahme, z. B. Elterngespräch mit anderer Uhrzeit)
- **"Ab Datum ändern"**: Wenn sich z. B. zum Halbjahr der Stundenplan ändert, kann man den Regeltermin ab einem bestimmten Datum anpassen. Alle bereits angelegten Dienste ab diesem Datum werden aktualisiert (oder die zukünftigen werden neu generiert), vergangene Dienste bleiben unverändert.
- Gelöschte oder manuell geänderte Einzeltermine werden beim "Ab-Datum"-Update nicht überschrieben (oder zumindest mit Hinweis markiert)

**Datenmodell (Vorüberlegung):**
- `RecurringShift`: Wochentag, start_time, end_time, break_minutes, employee_id, template_id, valid_from, valid_until, holiday_profile (z. B. "BW"), parent_id (für "ab Datum"-Varianten)
- `Shift.recurring_shift_id`: Verknüpfung zum Regeltermin (damit man weiß, welche Einzeldienste zu welchem Regeltermin gehören)
- `Shift.is_override`: Flag, wenn ein Einzeldienst manuell abgeändert wurde → beim "ab Datum"-Update nicht anfassen

**UI-Flow:**
1. "Regeltermin anlegen" → Wochentag(e) wählen, Zeiten, MA, Gültigkeitszeitraum, Ferien-Profil
2. System zeigt Vorschau: "Es werden X Dienste generiert (Y Tage übersprungen wegen Ferien/Feiertage)"
3. Bestätigen → Einzeldienste werden angelegt
4. Auf einem bestehenden Regeltermin: "Ab [Datum] ändern" → neue Zeiten eingeben → zukünftige Dienste werden angepasst

**Offene Fragen:**
- Ferien-Profile: Nur BW hardcodiert oder konfigurierbar pro Tenant (für andere Bundesländer)?
- Was passiert mit bereits bestätigten (`confirmed`) Diensten beim "ab Datum"-Update → wahrscheinlich: nicht anfassen, nur `planned`-Dienste aktualisieren
- Soll der Regeltermin auch im Kalender als "Schiene" sichtbar sein (z. B. farbige Hintergrundmarkierung)?
