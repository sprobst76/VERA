# Token-Optimierung durch Modell-Vorauswahl im Implementierungsplan

**Kurzfassung:** Statt jede Aufgabe mit dem stärksten (und teuersten) Modell zu erledigen, wird
**vorab pro Aufgabe** das *schwächste noch ausreichende* Modell festgelegt. Diese Vorauswahl
trifft ein **strategisches Modell (Fable, ersatzweise Opus)** einmalig beim Erstellen des Plans.
Die Ausführung liest die Vorauswahl nur noch ab. Ergebnis: gleiche Qualität, deutlich weniger
Tokens/Kosten.

---

## 1. Kernidee

Ein Implementierungsplan listet die Aufgaben ohnehin auf. Der Trick: **jede Aufgabenzeile trägt
ein Modell-Etikett.** Die teure Denkarbeit („welches Modell reicht hier?") passiert **einmal**
beim Planen — nicht immer wieder während der Ausführung.

```
Aufgabe                                   Modell     Begründung
1.1  MC-Module aus Mastery entfernen      Haiku      Migration nach Muster
1.5  ErrorBoundary + Chunk-Retry          Sonnet     React-Logik, 2 Dateien
4.3  85%-Difficulty-Controller            Opus       Algorithmus, Edge-Cases
5.1  Konzept: visueller Sternenpfad       Fable      strategisch/didaktisch
```

Der Plan wird so zu einem **Routing-Tabellenblatt**: Er sagt nicht nur *was* zu tun ist,
sondern auch *mit welchem Modell* — und damit *zu welchen Kosten*.

---

## 2. Warum das Tokens spart

- **Das teuerste Modell ist nicht das Standard-Modell.** Ohne Vorauswahl neigt man dazu, für
  *alles* das stärkste Modell zu nehmen („sicher ist sicher"). Repetitive Arbeit (Migrationen
  nach Muster, Boilerplate, UI-Fixes, Content-Texte) kostet dann ein Vielfaches, ohne dass die
  Qualität steigt.
- **Die Modellwahl-Entscheidung selbst kostet Tokens.** Trifft man sie *einmal* im Plan statt
  bei jeder Ausführung neu, spart man die wiederholte Abwägung.
- **Klarer Scope = weniger Nachfrage-Runden.** Ein Plan, der pro Aufgabe schon Modell + Scope +
  Abhängigkeit festhält, reduziert Rückfragen und Fehlversuche (die auch Tokens kosten).
- **Günstige Modelle sind schnell.** Haiku/Sonnet für die Masse der Arbeit heißt: mehr Durchsatz
  pro Token-Budget; die teuren Modelle bleiben den wenigen wirklich schweren Stellen vorbehalten.

**Faustregel:** *Nimm das billigste Modell, das die Aufgabe noch zuverlässig löst* — und lege das
vorab fest, damit die Ausführung nicht überprovisioniert.

---

## 3. Wer den Plan erstellt — und warum Fable / ersatzweise Opus

Die Modell-Vorauswahl ist eine **strategische** Aufgabe: Man muss die Aufgaben nach kognitiver
Schwere einschätzen, Abhängigkeiten sehen und die pädagogische/architektonische Tragweite
gewichten. Genau das ist die Stärke eines **strategischen Modells**:

- **Fable** (Erstwahl): strategische Einordnung, Architektur- und Progressions-Entscheidungen,
  gutes Urteil über „was ist hier wirklich schwer?". Erstellt den Plan inkl. Modell-Etiketten.
- **Opus** (Rückfall, falls Fable nicht verfügbar): ebenfalls stark im Planen und in der
  Aufwands-/Schwere-Abschätzung; übernimmt die Rolle nahtlos.

> Die Vorauswahl lohnt sich, weil ein einmaliger *strategischer* Blick (teuer, aber kurz) die
> Ausführung über *viele* Aufgaben hinweg auf günstige Modelle lenkt (billig, aber häufig).
> Das ist der eigentliche Hebel: **einmal teuer denken, oft billig ausführen.**

---

## 4. Die Modell-Legende (wann welches Modell)

| Modell | Wofür | Typische Aufgaben |
|--------|-------|-------------------|
| **Haiku** | Klare, repetitive Arbeit | Migrationen nach Muster, UI-Fixes, Boilerplate, Content-/Aufgaben-Texte |
| **Sonnet** | Standard-Entwicklung | Neue Komponenten, Bugfixes mit Logik, Integration, Test-Gerüste |
| **Opus** | Algorithmen & kniffliges Denken | Difficulty-Controller, Skill-/Fehlertyp-Schätzung, gefaltete Server-Logik |
| **Fable** | Strategie & Design | Architektur-Entscheidungen, pädagogische Progression, Konzept-Weichen |
| **? Nachfragen** | Scope unklar / Entscheidung nötig | Produkt-/Einwilligungs-Forks, alles, wo eine Meinung fehlt |

**Prinzip der Stufen:** von oben (billig, häufig) nach unten (teuer, selten). Eine Aufgabe
„rutscht hoch", sobald echte Logik/Algorithmik/Strategie ins Spiel kommt — nicht vorsorglich.

---

## 5. Ablauf in der Praxis

```
1. PLANEN  (einmalig, strategisches Modell = Fable / sonst Opus)
   └─ Aufgaben auflisten → je Aufgabe Modell-Etikett + Begründung + Abhängigkeit
        │
2. AUSFÜHREN  (pro Aufgabe, mit dem im Plan hinterlegten Modell)
   ├─ Haiku-Aufgaben  → Haiku-Executor
   ├─ Sonnet-Aufgaben → Sonnet-Executor
   ├─ Opus-Aufgaben   → Opus-Executor
   └─ „?"-Aufgaben     → erst Rückfrage an Stefan, dann ausführen
        │
3. VERIFIZIEREN  (Tests/Build/Deploy-Smoke — modell-unabhängig)
```

- Der Plan ist die **Single Source of Truth** fürs Modell-Routing.
- Nur die als **„?"** markierten Aufgaben unterbrechen für eine Entscheidung — der Rest läuft
  durch, ohne bei jedem Schritt neu über die Modellwahl nachzudenken.

---

## 6. Beispiel: Sternenweg-Implementierungsplan

Der Sternenweg-Plan setzt genau das um. Auszug aus der realen Modell-Verteilung:

- **Haiku** — Telemetrie-Migration nach Muster (1.2), MC-Module aus Mastery (1.1),
  Konfetti-nur-bei-Mastery (2.2), A11y-Attribut-Umbenennungen (2.3), Content für neue Module.
- **Sonnet** — Sternenreihe-Ergebnis (2.1), StarPath-Komponente (5.2), Fachkraft-Feedback-UI
  (7.3), die meisten Modul-Umbauten.
- **Opus** — 85%-Difficulty-Controller (4.3), Spaced-Review-Scheduling-Algorithmus (6.2).
- **Fable** — pädagogische Stufen-Zuordnung neuer Module (3.1), Sternenpfad-Konzept (5.1),
  Bewertungskonzept der Fachkraft (7.1), **strategische Gesamteinschätzung** des Projekts.
- **? Nachfragen** — z. B. „Förderplan-Schritt weist aktiv ein Modul zu" (Einwilligungs-Fork:
  wer steuert den Kind-Pfad?) → erst nach Stefans Richtungsentscheidung gebaut.

Der Plan selbst ist Fable-erstellt und Clara-validiert — die Modell-Legende steht direkt im
Plan-Artefakt, sodass jede Aufgabe ihr Kostenprofil offen trägt.

---

## 7. Grenzen & Leitplanken

- **Nicht unter-provisionieren.** Wenn eine „Haiku-Aufgabe" wider Erwarten echte Logik enthält,
  hochstufen — lieber einmal richtig als dreimal billig-falsch (das kostet am Ende *mehr* Tokens).
- **„?" ist kein Ausweichen, sondern Ökonomie.** Eine falsch geratene Produktentscheidung ist die
  teuerste Token-Ausgabe überhaupt (Neubau). Kurze Rückfrage schlägt langes Raten.
- **Die Vorauswahl ist ein Vorschlag, kein Dogma.** Sie darf beim Ausführen korrigiert werden,
  wenn sich die tatsächliche Schwere anders zeigt — dann das Etikett im Plan nachziehen.
- **Verifikation bleibt unabhängig.** Tests, Build und Deploy-Smoke laufen gleich, egal welches
  Modell die Aufgabe erledigt hat — „fertig" heißt weiterhin *verifiziert*, nicht nur *gebaut*.

---

*Stand: 2026-07-16 · Konzept hinter dem Sternenweg-Implementierungsplan
(`.planning/implementierungsplan.html`).*
