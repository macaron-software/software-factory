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

# Contribuer a Software Factory

Merci de votre interet pour contribuer a Software Factory ! Ce document fournit les lignes directrices et les instructions pour contribuer.

## Code de Conduite

En participant, vous acceptez de respecter notre [Code de Conduite](CODE_OF_CONDUCT.fr.md).

## Comment Contribuer

### Signaler des Bugs

1. Verifiez les [issues existantes](https://github.com/macaron-software/software-factory/issues) pour eviter les doublons
2. Utilisez le [modele de rapport de bug](.github/ISSUE_TEMPLATE/bug_report.md)
3. Incluez : etapes de reproduction, comportement attendu vs reel, details de l'environnement

### Proposer des Fonctionnalites

1. Ouvrez une issue avec le [modele de demande de fonctionnalite](.github/ISSUE_TEMPLATE/feature_request.md)
2. Decrivez le cas d'usage et le comportement attendu
3. Expliquez pourquoi cela serait utile aux autres utilisateurs

### Pull Requests

1. Forkez le depot
2. Creez une branche : `git checkout -b feature/ma-fonctionnalite`
3. Effectuez vos modifications en respectant les standards ci-dessous
4. Ecrivez ou mettez a jour les tests
5. Lancez les tests : `make test`
6. Commitez avec des messages clairs (voir conventions ci-dessous)
7. Poussez et ouvrez une Pull Request

## Installation pour le Developpement

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt

# Lancer les tests
make test

# Demarrer le serveur de dev
make dev
```

## Standards de Code

### Python

- **Style** : PEP 8, applique par `ruff`
- **Type hints** : requis pour les APIs publiques
- **Docstrings** : style Google pour modules, classes, fonctions publiques
- **Imports** : `from __future__ import annotations` dans tous les fichiers

### Messages de Commit

Suivez les [Conventional Commits](https://www.conventionalcommits.org/) :

```
feat: ajout du canal WebSocket temps reel
fix: correction de l'ordre des routes missions API
refactor: decoupage de api.py en sous-modules
docs: mise a jour des diagrammes d'architecture
test: ajout des tests de la file de travaux
```

### Tests

- Tests unitaires dans `tests/` avec `pytest`
- Tests asynchrones avec `pytest-asyncio`
- Tests E2E dans `platform/tests/e2e/` avec Playwright
- Toute nouvelle fonctionnalite doit avoir des tests

### Regles d'Architecture

- **Le LLM genere, les outils deterministes valident** — IA pour les taches creatives, scripts/compilateurs pour la validation
- **Pas de fichiers monolithiques** — decouper les modules de plus de 500 lignes en sous-packages
- **SQLite pour la persistance** — pas de dependance a une base de donnees externe
- **LLM multi-provider** — ne jamais coder en dur un seul fournisseur
- **Retrocompatible** — les nouvelles fonctionnalites ne doivent pas casser les APIs existantes

## Licence

En contribuant, vous acceptez que vos contributions soient licenciees sous la [Licence AGPL v3](LICENSE).
