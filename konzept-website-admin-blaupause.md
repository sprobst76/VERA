# Blaupause: Kleine Website mit selbstgebautem Admin

Ein wiederverwendbares Konzept für **Marketing-/Coming-Soon-Seiten mit eigenem
Redaktions-Backend**, die von **nicht-technischen Betreiber:innen** gepflegt werden –
ohne Datenbank, ohne CMS-Framework, auf **einfachem Shared Hosting**.

Herausdestilliert aus dem Projekt *zeitFrei* (zeitfrei-studio.de). Alles hier ist
projekt-neutral formuliert; konkrete Namen/Domains sind nur Beispiele.

---

## 1. Wann dieses Konzept passt (und wann nicht)

**Passt, wenn:**
- 1 kleine Website (Landingpage, Coming-Soon, Vereins-/Studioseite), wenige Unterseiten.
- Betreiber:innen ohne IT-Wissen sollen **Texte selbst ändern** und **sehen, was passiert**
  (Besucher, Anmeldungen, Wünsche) – ohne WordPress-Wartung, Plugins, Updates.
- Nur Shared Hosting (FTP + PHP) verfügbar, keine Datenbank gewünscht/nötig.
- Datenmengen klein (hunderte Datensätze, nicht Millionen).
- DSGVO-Sparsamkeit ist erwünscht: kein Tracking-Cookie, keine Fremd-Dienste.

**Passt NICHT, wenn:**
- Viele Redakteur:innen gleichzeitig schreiben (JSON-Dateien haben keine echte
  Nebenläufigkeit/Sperren).
- Große Datenmengen, Volltextsuche, Relationen → dann echte DB.
- Komplexe Rechte-/Rollen-Modelle nötig.

---

## 2. Architektur in einem Satz

**PHP + JSON-Dateien als Datenspeicher, keine Datenbank.** Öffentliche Seite und
kryptisch benannter, passwortgeschützter Admin liegen im selben Webspace; alle
Nutzdaten liegen in einem per Server-Config gesperrten `data/`-Ordner und werden
nur über PHP ausgeliefert.

```
public_html/
├─ index.php              # öffentliche Startseite (liest content.json)
├─ impressum.php, …       # weitere öffentliche Seiten
├─ save-quiz.php          # nimmt Formular-Absendungen an (schreibt nach data/)
├─ assets/                # öffentlich: CSS, JS, Bilder
├─ inc/                   # gemeinsame PHP-Bausteine (nicht direkt aufrufbar)
│   ├─ store.php          #   JSON laden/speichern (atomar)
│   ├─ track.php          #   cookiefreie Besucherzählung
│   └─ mailer.php         #   zentrale E-Mail-Benachrichtigung
├─ data/                  # ⛔ per .htaccess 403 gesperrt – NUR über PHP lesbar
│   ├─ content.json       #   die pflegbaren Inhalte
│   ├─ responses.csv      #   Formular-Antworten (echte PII!)
│   ├─ visits.json        #   aggregierte Besucherzahlen
│   ├─ requests.json      #   Änderungswünsche
│   ├─ notify.json        #   Mail-Empfänger + Schalter
│   └─ .salt              #   Geheimnis für den Besucher-Hash
└─ steuer-<zufall>/       # der Admin – Ordnername bewusst nicht erratbar
    ├─ auth.php           #   HTTP Basic Auth Gate (require ganz oben)
    ├─ nav.php            #   Navigation + gemeinsames Layout
    ├─ admin.css
    ├─ index.php          #   Dashboard
    ├─ content.php        #   Inhalte bearbeiten (Formular ↔ content.json)
    ├─ besucher.php       #   Besucher-Statistik
    ├─ responses.php      #   Formular-Antworten + CSV-Export
    ├─ requests.php       #   Änderungswünsche (mit Bild-Upload)
    └─ img.php            #   geschützte Bild-Auslieferung
```

**Warum JSON statt DB:** versionierbar (Git), kein DB-Setup auf Shared Hosting,
trivial zu sichern (Dateien kopieren), gut lesbar bei Fehlersuche. Preis:
selbst für Atomarität und „keine zwei Schreiber gleichzeitig" sorgen.

---

## 3. Die Bausteine im Einzelnen

### 3.1 Öffentliche Seite = Template über JSON
Die Startseite ist ein PHP-Template, das `content.json` lädt und die Texte einsetzt.
Kein Redakteurs-Text steht im PHP-Code. So kann der Admin denselben JSON-Stand
schreiben, den die Seite liest.

### 3.2 Admin: kryptischer Ordner + Basic Auth
- **Zwei Schutzschichten:** (a) Ordnername ist ein Zufalls-Slug (steht in `.env`,
  nicht im Repo), (b) HTTP Basic Auth über `auth.php`, das als erste Zeile jeder
  Admin-Datei `require`d wird. Passwort als **SHA-256-Hash** im Code/`.env`,
  nie im Klartext.
- **Für Laien gebaut:** Jede Funktion mit „**Warum das wichtig ist**" +
  Schritt-für-Schritt-Anleitung (einklappbare `<details>`-Blöcke). Aufgaben tragen
  ein Aufwands-/Status-Badge. Sprache einfach, keine Fachbegriffe.
- **Responsive nicht vergessen:** `<meta name="viewport">` auf **jeder** Admin-Seite –
  das war hier der eigentliche Grund, warum mobil nichts brauchbar war (nicht das CSS).
  Tabellen auf Handy als Karten (`data-label`-Attribute + CSS), keine horizontalen
  Scroll-Wüsten.

### 3.3 Minimal-CMS: Formular baut die JSON komplett neu
`content.php` rendert ein Formular aus allen Feldern und schreibt beim Speichern die
JSON **vollständig aus dem Formular neu**.
> ⚠️ **Wichtigste Falle:** Ein neues Feld in der JSON braucht **zwingend** ein
> passendes Formularfeld – sonst löscht der nächste Speichervorgang der
> Betreiber:innen das Feld. Immer als Roundtrip testen: laden → speichern ohne
> Änderung → Datei muss bit-identisch sein.

### 3.4 Cookiefreie Besucherzählung
- `inc/track.php` wird von den öffentlichen Seiten eingebunden. Es:
  - überspringt Nicht-GET und Bots (User-Agent-Regex),
  - bildet einen **tages-rotierenden, nicht umkehrbaren Hash**
    `sha256(salt + tag + ip + user-agent)` als „Besucher-Kennung" – **keine IP,
    kein Cookie wird gespeichert**,
  - schreibt nur **Tagesaggregate** nach `visits.json` (Views, geschätzte Besucher,
    Quellen/Referrer, Gerätetyp, Seiten).
- **Folge: kein Cookie-Banner nötig, kein Google Analytics.** DSGVO-arm by design.
- Der `besucher.php`-Tab zeigt 7/30/90-Tage, Quellen, Geräte, und eine
  **Conversion-Rate** (Anmeldungen ÷ Besucher).

### 3.5 Formular-Eingänge (Anmeldungen / Fragebogen)
Ein `save-quiz.php`-artiger Endpoint nimmt POST an, validiert, hängt eine Zeile an
`responses.csv` und löst eine E-Mail-Benachrichtigung aus.

### 3.6 Änderungswünsche mit Bild-Upload
Eigener Admin-Tab, in dem Betreiber:innen Wünsche erfassen (Titel, Text, wer, Prio,
Status) – **inklusive Screenshot-Upload**. Sicherheitskritisch, siehe §5.

### 3.7 Zentrale E-Mail-Benachrichtigung
`inc/mailer.php` als **einzige** Stelle für Mailversand. Empfänger + An/Aus-Schalter
je Ereignis (Anmeldung / Änderungswunsch) in `notify.json`, im Admin einstellbar,
mit Testmail-Knopf. Deliverability ist der heikelste Teil → §6.

### 3.8 Deploy per Skript, nie von Hand
`scripts/deploy.sh` lädt per **FTPS** hoch. Zugangsdaten **nur aus `.env`**, an
`curl` **nur per `-K <configfile>`** – nie als Kommandozeilen-Argument (landet im
Shell-Verlauf), und bei FTP **kein `curl -v`** (druckt das Passwort im Klartext).
Das Skript **verweigert** den Upload der server-seitigen Laufzeitdaten (§4).

---

## 4. Die goldene Regel: Server-Daten sind das Original

Dateien, die **auf dem Server entstehen** (`responses.csv`, `visits.json`, `.salt`,
`notify.json`), existieren **nur dort** – der lokale Stand ist eine leere Hülle.

**Ein Upload überschreibt echte Daten mit einer Leiche.** Genau das ist hier einmal
passiert: eine lokal geleerte `responses.csv` hochgeladen → echte Anmeldungen weg,
nur durch Zufall aus der Terminal-Ausgabe rekonstruierbar.

**Zwei Konsequenzen, die ins Konzept gehören:**
1. `deploy.sh` führt eine **Protected-Liste**; solche Dateien werden nur mit
   explizitem `ZF_FORCE=1` hochgeladen. Standard = niemals.
2. **Vor jedem Anfassen einer `data/`-Datei: erst frisch vom Server ziehen, ansehen,
   gezielt ändern, zurück. Nie blind überschreiben.** Die Datei kann über den Admin
   geändert worden sein.

→ Und deshalb ist **automatisches Backup Pflichtteil des Konzepts**, kein Extra:
tägliche datierte Kopie aller `data/`-Dateien in einen gesperrten Ordner (Rotation),
Vorgänger-Sicherung vor jedem Admin-Speichern, **wöchentlich eine Kopie außer Haus**
(ein Backup auf demselben Server hilft bei Serverausfall nicht), und die
**Wiederherstellung einmal testen**.

---

## 5. Sicherheit (checklistentauglich)

- **`data/` per `.htaccess` auf 403** – Nutzdaten nie direkt über HTTP erreichbar.
- **Uploads gehören hinter die 403-Sperre**, nicht nach `assets/`. Ausgeliefert nur
  über ein PHP-Skript (`img.php`), das vorher das Admin-Passwort verlangt.
  *Erratbare Dateinamen sind kein Schutz* – Betreiber:innen laden evtl. Privates hoch.
- **Upload-Validierung über `getimagesize()`**, nicht über die Dateiendung. Eine als
  `.png` getarnte `.php` wird so erkannt und abgelehnt. Zusätzlich `.htaccess` im
  Upload-Ordner, die Skriptausführung verbietet. Feste Whitelist (jpg/png/webp/gif),
  Größenlimit, selbst generierte Dateinamen (kein Nutzer-Input im Pfad).
- **`X-Content-Type-Options: nosniff`** beim Ausliefern, Content-Type aus
  `getimagesize()`.
- **Pfad-Traversal** aktiv verhindern: Dateinamen gegen strikte Regex prüfen
  (`^[erlaubtes-muster]$`), nie `../` durchlassen.
- **Passwörter/Tokens nie im Repo, nie als CLI-Argument.** `.env` in `.gitignore`.
- **Admin-Ordner-Slug** aus `.env`, nicht im Code.

---

## 6. E-Mail-Zustellung – die unterschätzte Hürde

Reihenfolge der Schmerzen, die real aufgetreten sind:

1. **Absender muss ein real existierendes Postfach der eigenen Domain sein.**
   Erfundene Absender (`no-reply@`, `info@`, wenn es sie nicht gibt) sind ein
   Spam-Signal; Rückläufer verschwinden spurlos. Postfach-Existenz ohne Panel-Zugang
   per **SMTP-Probe** prüfen: Port 25, `MAIL FROM` mit **gültigem** Absender (der
   Server macht Sender-Verify und lehnt `test@example.com` ab), dann `RCPT TO` →
   250 = existiert, 550 = nicht.
2. **PHP `mail()`: den Envelope-Absender NICHT selbst setzen** (kein `-f` als
   5. Argument) auf Shared Hosting, wo der PHP-User kein „trusted user" von Exim ist.
   Sonst **verwirft der MTA die Mail stillschweigend** – und `mail()` liefert trotzdem
   `true`. Ohne `-f` setzt der Server einen gültigen Systemabsender und stellt zu.
   *(Symptom: „Code läuft, mail() gibt true, nichts kommt an." Fast immer das hier.)*
3. **Betreff RFC-2047-kodieren** (`=?UTF-8?B?…?=`), sonst zerschießen Umlaute die
   Kopfzeile.
4. **DKIM + DMARC** vor echtem Kundenversand nachrüsten (Gmail verlangt seit 2024
   belastbare Authentifizierung). SPF prüfen, dass `a`/`mx` den echten Sendeserver
   abdecken. DNS-Records dort setzen, wo die Domain verwaltet wird (nicht zwingend
   beim Webhoster).
5. **Diagnose-Methode, die zum Ziel führte:** dieselbe Mail zweimal senden – Variante
   A mit `-f`, Variante B ohne – und schauen, welche ankommt. Isoliert die Ursache
   sofort.

---

## 7. Betriebs-/Deploy-Fallstricke (aus echten Treffern)

- **`index.html` überschattet `index.php`** unter `/`. Sah aus, als greife das
  Deployment nicht.
- **Kein lokales PHP** zum Testen? Dann Syntax erst nach Upload prüfbar:
  HTTP-Status + `grep` auf `Fatal error|Parse error|Warning:`.
- **`.gitignore` kennt keine Kommentare am Zeilenende.**
- **Screenshots headless (Firefox):** isoliertes Profil (`-profile <tmpdir>
  --no-remote`), sonst hängt er an einer laufenden Instanz.
- **Vor jedem Deploy** die betroffene JSON **frisch vom Server ziehen** (§4).

---

## 8. Übertragen auf ein neues Projekt – Checkliste

1. **Ordnergerüst** aus §2 anlegen; Admin-Slug zufällig wählen, in `.env`.
2. `inc/store.php` (atomares JSON-Load/Save), `inc/track.php`, `inc/mailer.php`
   übernehmen und Domain/Absender anpassen.
3. **`data/`-403** per `.htaccess` sicherstellen; Upload-Ordner mit
   Skript-Verbots-`.htaccess`.
4. `content.json`-Schema definieren → **jedes Feld** bekommt ein Formularfeld in
   `content.php`. Roundtrip-Test (laden→speichern→bit-identisch).
5. `auth.php` (Basic Auth, gehashtes Passwort) an den Kopf **jeder** Admin-Datei.
6. `<meta name="viewport">` + Mobile-CSS auf allen Admin-Seiten.
7. `deploy.sh` mit **Protected-Liste** + `.env`-Credentials via `-K`.
8. **Backup zuerst** einbauen (täglich datiert + wöchentlich außer Haus + Restore
   getestet) – nicht als „später".
9. E-Mail: echtes Absender-Postfach, `mail()` ohne `-f`, Testmail-Knopf, DKIM/DMARC
   einplanen.
10. `.gitignore`: `.env`, alle PII-/Laufzeitdaten (`responses.csv`, `visits.json`,
    `.salt`, Upload-Ordner), keine Zeilenend-Kommentare.

---

## 9. Bewusste Entscheidungen (Kurzbegründung)

| Entscheidung | Warum |
|---|---|
| JSON statt DB | Shared Hosting, versionierbar, trivial sicherbar, lesbar bei Fehlern |
| Eigenbau statt WordPress | keine Update-/Plugin-/Angriffsfläche; exakt auf Laien zugeschnitten |
| Cookiefreies Tracking | kein Banner, DSGVO-arm, keine Fremd-Dienste |
| Uploads hinter 403 + PHP-Auslieferung | erratbare Namen sind kein Schutz |
| `mail()` ohne `-f`, echtes Postfach | sonst stille Mail-Verluste |
| Deploy-Skript mit Protected-Liste | verhindert Überschreiben echter Serverdaten |
| Admin-Texte mit „Warum + Anleitung" | Betreiber:innen ohne IT-Wissen |
