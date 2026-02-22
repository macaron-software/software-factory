# GitHub Actions Workflows

## quality.yml

Pipeline de qualité automatisé qui s'exécute sur chaque push/PR vers main/master/develop.

**Jobs parallèles:**
1. **Python Quality** - Ruff linting + formatting, Bandit security scan
2. **JavaScript Quality** - ESLint + Prettier
3. **PHP Quality** - PHPLint (désactivé jusqu'à présence de code PHP)
4. **Security Scan** - Trivy vulnerability scanner avec SARIF output vers GitHub Security
5. **Secrets Detection** - TruffleHog pour détecter credentials hardcodés
6. **Tests & Coverage** - Pytest avec upload vers Codecov

**Caractéristiques:**
- ✅ Tous les jobs sont non-bloquants (warnings uniquement) pour adoption progressive
- ✅ Utilise le cache NPM/Pip pour vitesse optimale
- ✅ Génère des artifacts (rapports Bandit, coverage)
- ✅ Integration GitHub Security (SARIF)
- ✅ Déclenchement manuel possible via workflow_dispatch

**Local testing:**
```bash
# Reproduire localement
make quality        # Quick: staged files only
make quality-full   # Full: all files
make test-coverage  # Tests avec coverage
```
