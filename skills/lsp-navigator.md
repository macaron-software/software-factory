---
name: lsp-navigator
version: 1.0.0
description: >
  Quand et comment utiliser les outils LSP (lsp_definition, lsp_references,
  lsp_diagnostics, lsp_symbols) plutôt que code_search/grep pour naviguer dans
  le code Python de la Software Factory. LSP donne des résultats structurels
  exacts là où grep fait de la correspondance textuelle.
metadata:
  category: development
  triggers:
    - "when looking for the definition of a function or class"
    - "when finding all usages or call sites of a symbol"
    - "when checking for type errors after editing a Python file"
    - "when listing all functions or classes in a file"
    - "when refactoring and need exact symbol locations"

eval_cases:
  - id: prefer-lsp-definition-over-grep
    prompt: |
      Dans platform/tools/registry.py, où est définie exactement la classe BaseTool ?
      Donne le numéro de ligne.
    tools: [lsp_symbols, lsp_definition]
    should_trigger: true
    checks:
      - "regex:BaseTool"
      - "regex:\\d+"
      - "no_placeholder"
      - "not_regex:code_search|subprocess.*grep"
    expectations:
      - "utilise lsp_symbols ou lsp_definition, pas code_search"
      - "retourne le numéro de ligne exact de BaseTool dans registry.py"
      - "réponse concise et directe, pas de lecture de fichier entier"
    tags: [lsp, definition, prefer-lsp]

  - id: find-all-references
    prompt: |
      Combien de fichiers appellent register_code_tools() dans le projet ?
      La fonction est définie dans platform/tools/code_tools.py à la ligne 164.
      Utilise lsp_references sur ce fichier/ligne pour trouver tous les call sites.
    tools: [lsp_references]
    should_trigger: true
    checks:
      - "regex:register_code_tools"
      - "regex:tool_runner|code_tools"
      - "regex:\\d+"
      - "no_placeholder"
    expectations:
      - "utilise lsp_references pour trouver tous les call sites"
      - "liste les fichiers et numéros de lignes exacts"
      - "ne fait pas de grep textuel approximatif"
    tags: [lsp, references, call-sites]

  - id: diagnostics-after-edit
    prompt: |
      J'ai modifié platform/tools/lsp_tools.py. Vérifie s'il y a des erreurs
      de type ou d'import dans ce fichier. Utilise lsp_diagnostics.
    tools: [lsp_diagnostics]
    should_trigger: true
    checks:
      - "regex:No syntax errors|No errors|0 error|clean|✓"
      - "no_placeholder"
      - "length_min:30"
    expectations:
      - "appelle lsp_diagnostics sur le fichier modifié"
      - "rapporte clairement : soit aucune erreur, soit la liste des erreurs avec numéros de ligne"
      - "n'invente pas les erreurs — se fie au résultat de l'outil"
    tags: [lsp, diagnostics, post-edit]

  - id: symbols-file-overview
    prompt: |
      Liste toutes les classes et fonctions définies dans platform/agents/executor.py.
      Utilise lsp_symbols pour obtenir la liste structurelle.
    tools: [lsp_symbols]
    should_trigger: true
    checks:
      - "regex:class|function|module"
      - "regex:\\d+"
      - "no_placeholder"
      - "length_min:100"
    expectations:
      - "utilise lsp_symbols pour obtenir la liste structurelle"
      - "retourne les noms avec type (class/function) et numéro de ligne"
      - "n'utilise pas code_read pour lire tout le fichier"
    tags: [lsp, symbols, file-overview]

  - id: lsp-vs-grep-decision
    prompt: |
      Je cherche tous les endroits où la méthode execute() est définie dans
      platform/tools/. Quelle approche utilises-tu ?
    tools: [lsp_definition, lsp_symbols]
    should_trigger: true
    checks:
      - "regex:lsp_symbols|lsp_definition|lsp_references"
      - "regex:execute"
      - "no_placeholder"
      - "not_regex:subprocess.*grep|os\\.system"
    expectations:
      - "choisit LSP (lsp_symbols ou lsp_references) plutôt que grep"
      - "justifie brièvement pourquoi LSP est plus précis ici"
      - "retourne des locations exactes avec file:line"
    tags: [lsp, decision, grep-vs-lsp]

  - id: ac-refactor-callsites
    prompt: |
      L'AC codex veut renommer la fonction register_code_tools() en register_code_tools_v2().
      Trouve tous les endroits dans le projet qui appellent register_code_tools().
      La définition est dans platform/tools/code_tools.py ligne 164.
      Utilise lsp_references pour lister les call sites exacts.
    tools: [lsp_references]
    should_trigger: true
    checks:
      - "regex:register_code_tools"
      - "regex:tool_runner"
      - "regex:\\d+"
      - "no_placeholder"
      - "length_min:80"
    expectations:
      - "utilise lsp_references pour trouver tous les call sites de register_code_tools"
      - "liste les fichiers impactés avec leurs lignes (tool_runner.py au minimum)"
      - "aide l'agent à planifier le refactor sans rien oublier"
    tags: [lsp, refactor, ac-codex]
---

# Skill : LSP Navigator — Intelligence de code structurelle

## Principe

LSP traite le code comme une **structure** (AST, types, portées).
`code_search`/grep traite le code comme du **texte**.

Utilise LSP quand tu veux une réponse exacte sur la structure du code.
Utilise grep quand tu cherches une chaîne arbitraire (logs, configs, YAML).

## Règle de décision

| Question | Outil LSP | Pourquoi pas grep |
|---|---|---|
| Où est défini `X` ? | `lsp_definition` | grep trouve aussi les commentaires, imports, strings |
| Qui appelle `f()` ? | `lsp_references` | grep ne distingue pas définition vs appel vs string |
| Ce fichier a des erreurs de type ? | `lsp_diagnostics` | grep ne comprend pas les types |
| Quelles classes sont dans ce fichier ? | `lsp_symbols` | grep ne donne pas la hiérarchie |

## Paramètres LSP

Tous les outils LSP prennent :
- `file` : chemin absolu ou relatif depuis la racine du projet
- `line` / `column` : position 1-based pour `lsp_definition` et `lsp_references`
- `project_root` : optionnel, racine du projet Python (améliore la résolution)

Pour `lsp_definition` et `lsp_references` : positionne le curseur **sur le nom** du symbole.
Exemple pour trouver où `BaseTool` est défini depuis `tool_runner.py` ligne 12, col 8 :
```
lsp_definition(file="platform/agents/tool_runner.py", line=12, column=8)
```

## Quand garder code_search

- Recherche cross-langage (Python + YAML + SQL ensemble)
- Patterns non-symboliques (URLs, strings de config, commentaires)
- Codebase < 50 fichiers où grep est déjà instantané
- Symboles dans des fichiers non-Python (JS/TS des missions)

## Intégration avec les agents AC

Les agents `ac-architect` et `ac-codex` peuvent utiliser LSP pour :
- `ac-architect` : vérifier que les noms de classes/fonctions planifiés n'existent pas déjà (`lsp_symbols`)
- `ac-codex` : après chaque `code_write`, appeler `lsp_diagnostics` pour détecter les erreurs immédiatement
- `ac-adversarial` : lister tous les symboles d'un fichier pour une revue exhaustive (`lsp_symbols`)
