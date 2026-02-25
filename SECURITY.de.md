<p align="center">
  <a href="SECURITY.md">English</a> |
  <a href="SECURITY.fr.md">Français</a> |
  <a href="SECURITY.zh-CN.md">中文</a> |
  <a href="SECURITY.es.md">Español</a> |
  <a href="SECURITY.ja.md">日本語</a> |
  <a href="SECURITY.pt.md">Português</a> |
  <a href="SECURITY.de.md">Deutsch</a> |
  <a href="SECURITY.ko.md">한국어</a>
</p>

# Sicherheitsrichtlinie

## Unterstuetzte Versionen

| Version | Unterstuetzt |
|---------|----------|
| 2.2.x   | Ja       |
| 2.1.x   | Ja       |
| < 2.1   | Nein        |

## Eine Schwachstelle melden

Wenn Sie eine Sicherheitsluecke entdecken, melden Sie diese bitte verantwortungsvoll:

1. Eroeffnen Sie **keine** oeffentliche GitHub-Issue
2. Senden Sie eine E-Mail an **security@macaron-software.com**
3. Enthalten:
   - Beschreibung der Schwachstelle
   - Schritte zur Reproduktion
   - Moegliche Auswirkungen
   - Vorgeschlagene Korrektur (falls vorhanden)

Wir bestaetigen den Empfang innerhalb von 48 Stunden und geben innerhalb von 7 Tagen eine detaillierte Antwort.

## Sicherheitsmassnahmen

### Authentifizierung und Autorisierung

- JWT-basierte Authentifizierung mit Token-Erneuerung
- Rollenbasierte Zugriffskontrolle (RBAC): admin, project_manager, developer, viewer
- OAuth 2.0 Integration (GitHub, Azure AD)
- Sitzungsverwaltung mit sicheren Cookies

### Eingabevalidierung

- Prompt-Injection-Schutz bei allen LLM-Eingaben
- Eingabebereinigung bei allen API-Endpunkten
- Parametrisierte SQL-Abfragen (keine rohe SQL-Interpolation)
- Dateipfad-Traversal-Schutz

### Datenschutz

- Geheimnis-Bereinigung in Agenten-Ausgaben (API-Schluessel, Passwoerter, Tokens)
- Keine Geheimnisse im Quellcode oder Logs gespeichert
- Umgebungsbasierte Konfiguration fuer sensible Werte
- SQLite WAL-Modus fuer Datenintegritaet

### Netzwerksicherheit

- Content Security Policy (CSP) Header
- CORS-Konfiguration fuer API-Endpunkte
- Ratenbegrenzung pro Benutzer/IP
- HTTPS in Produktion erzwungen (via Nginx)

### Abhaengigkeitsverwaltung

- Regelmaessige Abhaengigkeits-Audits via `pip-audit`
- SAST-Scanning mit bandit und semgrep
- Automatisierte Sicherheitsmissionen pro Projekt (woechentliche Scans)

## Offenlegungsrichtlinie

Wir folgen der koordinierten Offenlegung. Nach der Veroeffentlichung einer Korrektur:
1. Nennung des Melders (sofern keine Anonymitaet gewuenscht)
2. Veroeffentlichung eines Sicherheitshinweises auf GitHub
3. Aktualisierung des Changelogs mit Sicherheitskorrekturen
