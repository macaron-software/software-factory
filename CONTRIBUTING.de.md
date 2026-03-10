<p align="center">
  <a href="CONTRIBUTING.md">English</a> |
  <a href="CONTRIBUTING.fr.md">Français</a> |
  <a href="CONTRIBUTING.zh-CN.md">中文</a> |
  <a href="CONTRIBUTING.es.md">Español</a> |
  <a href="CONTRIBUTING.ja.md">日本語</a> |
  <a href="CONTRIBUTING.pt.md">Português</a> |
  <a href="CONTRIBUTING.de.md">Deutsch</a> |
  <a href="CONTRIBUTING.ko.md">한국어</a>
</p>

# Beitrag zu Software Factory

Vielen Dank fuer Ihr Interesse an Software Factory! Dieses Dokument enthaelt Richtlinien und Anweisungen fuer Beitraege.

## Verhaltenskodex

Mit der Teilnahme stimmen Sie unserem [Verhaltenskodex](CODE_OF_CONDUCT.de.md) zu.

## Wie Sie beitragen koennen

### Fehler melden

1. Pruefen Sie [bestehende Issues](https://github.com/macaron-software/software-factory/issues), um Duplikate zu vermeiden
2. Verwenden Sie die [Fehlerbericht-Vorlage](.github/ISSUE_TEMPLATE/bug_report.md)
3. Enthalten: Schritte zur Reproduktion, erwartetes vs. tatsaechliches Verhalten, Umgebungsdetails

### Funktionen vorschlagen

1. Eroeffnen Sie eine Issue mit der [Feature-Request-Vorlage](.github/ISSUE_TEMPLATE/feature_request.md)
2. Beschreiben Sie den Anwendungsfall und das erwartete Verhalten
3. Erklaeren Sie, warum dies fuer andere Benutzer nuetzlich waere

### Pull Requests

1. Forken Sie das Repository
2. Erstellen Sie einen Feature-Branch: `git checkout -b feature/mein-feature`
3. Nehmen Sie Ihre Aenderungen gemaess den untenstehenden Standards vor
4. Schreiben oder aktualisieren Sie Tests
5. Fuehren Sie Tests aus: `make test`
6. Committen Sie mit klaren Nachrichten (siehe Konventionen unten)
7. Pushen Sie und eroeffnen Sie eine Pull Request

## Entwicklungsumgebung

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt
make test
make dev
```

## Code-Standards

### Python

- **Stil**: PEP 8, durchgesetzt durch `ruff`
- **Type Hints**: erforderlich fuer oeffentliche APIs
- **Docstrings**: Google-Stil fuer Module, Klassen, oeffentliche Funktionen
- **Imports**: `from __future__ import annotations` in allen Dateien

### Commit-Nachrichten

Folgen Sie [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: WebSocket-Echtzeitkanal hinzufuegen
fix: Routenreihenfolge in Missions-API korrigieren
refactor: api.py in Sub-Module aufteilen
docs: Architekturdiagramme aktualisieren
test: Worker-Queue-Tests hinzufuegen
```

### Tests

- Unit-Tests in `tests/` mit `pytest`
- Asynchrone Tests mit `pytest-asyncio`
- E2E-Tests in `platform/tests/e2e/` mit Playwright
- Alle neuen Funktionen muessen Tests haben

### Architekturregeln

- **LLM generiert, deterministische Tools validieren** — KI fuer kreative Aufgaben, Skripte/Compiler fuer Validierung
- **Keine monolithischen Dateien** — Module ueber 500 Zeilen in Sub-Pakete aufteilen
- **SQLite fuer Persistenz** — keine externen Datenbankabhaengigkeiten
- **Multi-Provider-LLM** — niemals einen einzelnen Anbieter fest codieren
- **Abwaertskompatibel** — neue Funktionen duerfen bestehende APIs nicht brechen

## Lizenz

Mit Ihrem Beitrag stimmen Sie zu, dass Ihre Beitraege unter der [AGPL v3 Lizenz](LICENSE) lizenziert werden.
