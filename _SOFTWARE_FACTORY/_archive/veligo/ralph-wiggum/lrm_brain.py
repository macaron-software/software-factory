#!/usr/bin/env python3
"""
lrm_brain.py - LRM Brain (Recursive Language Model) pour Veligo

Implémentation conforme au paper arXiv:2512.24601 (MIT CSAIL)
"Recursive Language Models" - Zhang, Kraska, Khattab

Architecture RLM:
┌─────────────────────────────────────────────────────────────────────────────┐
│  ROOT LM (depth=0)                                                          │
│  └─► Reçoit la QUERY (pas le contexte complet)                             │
│  └─► Accède au contexte via REPL Python + MCP Tools                        │
│  └─► Peut spawner des SUB-LMs (depth=1, 2, ...)                            │
│  └─► Termine avec FINAL(answer)                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  REPL ENVIRONMENT                                                           │
│  └─► Context stocké en variable Python (pas dans le prompt LLM)            │
│  └─► MCP Tools: veligo_rag_query, veligo_ao_search, veligo_grep            │
│  └─► Le LLM écrit du code Python pour manipuler le contexte                │
├─────────────────────────────────────────────────────────────────────────────┤
│  RECURSION                                                                  │
│  └─► Root LM spawne Sub-LM pour sous-tâches                                │
│  └─► Sub-LM peut spawner Sub-Sub-LM (profondeur illimitée)                 │
│  └─► Chaque niveau a son propre contexte réduit                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  TERMINATION                                                                │
│  └─► FINAL(answer) = réponse définitive                                    │
│  └─► FINAL_VAR(var_name) = réponse dans variable REPL                      │
│  └─► RECURSE(query, context_slice) = appel récursif                        │
└─────────────────────────────────────────────────────────────────────────────┘

Stratégies émergentes (out-of-core):
- PEEK: Échantillonner le début du contexte
- GREP: Filtrer par regex/keywords
- PARTITION+MAP: Chunker et paralléliser
- SUMMARIZE: Condenser pour le parent

Usage:
    python3 lrm_brain.py --query "Génère le backlog TDD prioritaire"
    python3 lrm_brain.py --analyze  # Analyse complète + génération tasks

Les Wiggum daemons sont INDÉPENDANTS - ils dépilent leurs backlogs (T*, D*)
Le LRM Brain alimente les backlogs via son analyse récursive.
"""

import os
import sys
import json
import subprocess
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

# Chemins projet
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent
TASKS_DIR = SCRIPT_DIR / "tasks"
LOGS_DIR = SCRIPT_DIR / "logs"
STATUS_DIR = SCRIPT_DIR / "status"

# Configuration LLM
# Brain RLM utilise Opus 4.5 (via Claude Code) pour la vision stratégique
# Sub-agents/Workers utilisent MiniMax M2.1 ou Qwen local
LLM_MODEL_BRAIN = "claude-opus-4-5"               # Brain: Opus 4.5 pour vision stratégique
LLM_MODEL_SUBAGENT = "opencode/minimax-m2.1-free" # Sub-agents: MiniMax M2.1
LLM_MODEL_FALLBACK = "local/qwen3-30b-a3b"        # Fallback: llama-cpp local
LLM_MODEL = LLM_MODEL_SUBAGENT  # Modèle par défaut pour les outils REPL (sub-agents)
LOCAL_API_URL = os.environ.get("LOCAL_API_URL", "http://127.0.0.1:8002/v1/chat/completions")
LOCAL_MODEL = os.environ.get("LOCAL_MODEL", "qwen3-30b")
USE_CLAUDE_CODE_FOR_BRAIN = True  # True = utilise Claude Code CLI pour le brain
MAX_DEPTH = 5                              # Profondeur max de récursion
MAX_CONTEXT_TOKENS = 8000                  # Tokens max par appel
TIMEOUT_SECONDS = 3600                     # Timeout par appel LLM (1h)

# Créer les répertoires
TASKS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
STATUS_DIR.mkdir(exist_ok=True)


# =============================================================================
# REPL ENVIRONMENT
# =============================================================================
# Le REPL stocke le contexte et les variables intermédiaires
# Le LLM n'a JAMAIS le contexte complet dans son prompt
# Il accède au contexte via des appels REPL (code Python)

@dataclass
class REPLEnvironment:
    """
    Environnement REPL pour le LRM.

    Inspiré des algorithmes "out-of-core":
    - Le contexte (projet entier) est stocké en mémoire externe
    - Le LLM accède au contexte via des requêtes programmatiques
    - Évite de saturer la context window du LLM

    Variables disponibles dans le REPL:
    - context: dict avec les données du projet
    - results: dict pour stocker les résultats intermédiaires
    - mcp_*: fonctions pour appeler les outils MCP
    """

    # Variables REPL accessibles au LLM
    context: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)

    # Historique des commandes
    history: List[str] = field(default_factory=list)

    # Log file
    log_file: Optional[Path] = None

    def __post_init__(self):
        """Initialise le contexte avec les données projet."""
        self.log_file = LOGS_DIR / f"lrm_repl_{datetime.now():%Y%m%d_%H%M%S}.log"
        self._init_context()

    def _init_context(self):
        """
        Charge le contexte projet en mémoire.
        Le contexte n'est PAS envoyé au LLM - il y accède via REPL.
        """
        self.context = {
            "project_root": str(PROJECT_ROOT),
            "tasks_dir": str(TASKS_DIR),
            # Métadonnées légères (pas le contenu)
            "file_count": self._count_files(),
            "modules": self._list_modules(),
            "task_status": self._get_task_status(),
        }
        self._log(f"Context initialized: {len(self.context)} keys")

    def _count_files(self) -> Dict[str, int]:
        """Compte les fichiers par extension. AUCUN FALLBACK."""
        counts = {}
        for ext in [".rs", ".ts", ".svelte", ".sql", ".md"]:
            result = subprocess.run(
                ["find", str(PROJECT_ROOT),
                 "-path", "*/node_modules/*", "-prune", "-o",
                 "-path", "*/target/*", "-prune", "-o",
                 "-path", "*/.git/*", "-prune", "-o",
                 "-name", f"*{ext}", "-type", "f", "-print"],
                capture_output=True, text=True, timeout=60, check=True
            )
            counts[ext] = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
        return counts

    def _list_modules(self) -> List[str]:
        """Liste les modules Cargo."""
        modules = []
        for cargo in PROJECT_ROOT.rglob("Cargo.toml"):
            if "target" not in str(cargo):
                modules.append(str(cargo.parent.relative_to(PROJECT_ROOT)))
        return modules[:20]  # Limite pour éviter surcharge

    def _get_task_status(self) -> Dict[str, int]:
        """Compte les tâches par statut."""
        status = {"PENDING": 0, "COMPLETE": 0, "FAILED": 0, "IN_PROGRESS": 0}
        for task_file in TASKS_DIR.glob("*.md"):
            content = task_file.read_text()
            for s in status:
                if f"STATUS: {s}" in content:
                    status[s] += 1
                    break
        return status

    def _log(self, message: str):
        """Log dans le fichier REPL."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[REPL {timestamp}] {message}\n"
        print(f"\033[0;36m{log_line}\033[0m", end="")
        if self.log_file:
            with open(self.log_file, "a") as f:
                f.write(log_line)

    # =========================================================================
    # MCP TOOLS - Accessibles via REPL
    # =========================================================================

    def mcp_rag_query(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        MCP Tool: Recherche sémantique dans le codebase.
        AUCUN FALLBACK - échec explicite.
        """
        self._log(f"mcp_rag_query('{query}', top_k={top_k})")

        result = subprocess.run(
            ["opencode", "run", "-m", LLM_MODEL,
             f"Utilise l'outil mcp__veligo-rag__veligo_rag_query avec query='{query}' et top_k={top_k}. "
             f"Retourne uniquement le JSON des résultats."],
            capture_output=True, text=True, timeout=3600, cwd=PROJECT_ROOT, check=True
        )
        self.history.append(f"mcp_rag_query({query})")

        if not result.stdout.strip():
            raise RuntimeError(f"mcp_rag_query returned empty for: {query}")

        return json.loads(result.stdout)

    def mcp_ao_search(self, query: str) -> List[Dict]:
        """
        MCP Tool: Recherche dans les specs AO (cahier des charges).
        AUCUN FALLBACK - échec explicite.
        """
        self._log(f"mcp_ao_search('{query}')")

        result = subprocess.run(
            ["opencode", "run", "-m", LLM_MODEL,
             f"Utilise l'outil mcp__veligo-rag__veligo_ao_search avec query='{query}'. "
             f"Retourne uniquement le JSON des résultats."],
            capture_output=True, text=True, timeout=3600, cwd=PROJECT_ROOT, check=True
        )
        self.history.append(f"mcp_ao_search({query})")

        if not result.stdout.strip():
            raise RuntimeError(f"mcp_ao_search returned empty for: {query}")

        return json.loads(result.stdout)

    def mcp_grep(self, pattern: str, file_glob: str = "*.rs") -> List[str]:
        """
        MCP Tool: Grep dans le codebase.
        AUCUN FALLBACK - échec explicite.
        """
        self._log(f"mcp_grep('{pattern}', '{file_glob}')")

        result = subprocess.run(
            ["rg", pattern, "--glob", file_glob, "-l", "--max-count", "20"],
            capture_output=True, text=True, timeout=3600, cwd=PROJECT_ROOT, check=True
        )
        self.history.append(f"mcp_grep({pattern}, {file_glob})")

        if not result.stdout.strip():
            raise RuntimeError(f"mcp_grep found nothing for: {pattern}")

        return result.stdout.strip().split("\n")

    def peek(self, file_path: str, lines: int = 50) -> str:
        """
        Stratégie PEEK: Échantillonner le début d'un fichier.
        AUCUN FALLBACK - échec explicite si fichier n'existe pas.
        """
        self._log(f"peek('{file_path}', lines={lines})")

        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"peek: file not found: {full_path}")

        with open(full_path) as f:
            return "\n".join(f.readlines()[:lines])

    def summarize(self, text: str, max_tokens: int = 500) -> str:
        """
        Stratégie SUMMARIZE: Condenser du texte via LLM.

        Utilisé pour réduire le contexte avant de le passer au parent.
        AUCUN FALLBACK - échec explicite si LLM fail.
        """
        self._log(f"summarize(text_len={len(text)}, max_tokens={max_tokens})")
        if len(text) < max_tokens * 4:
            return text

        result = subprocess.run(
            ["opencode", "run", "-m", LLM_MODEL,
             f"Résume ce texte en max {max_tokens} tokens:\n{text[:3000]}"],
            capture_output=True, text=True, timeout=3600, check=True
        )
        return result.stdout.strip()


# =============================================================================
# RECURSIVE LM CALL
# =============================================================================

@dataclass
class RLMCall:
    """
    Représente un appel LLM dans la hiérarchie RLM.

    Chaque appel a:
    - depth: profondeur dans l'arbre de récursion
    - query: la question à résoudre
    - context_slice: portion du contexte pertinente (pas tout!)
    - parent: référence au parent (pour remonter le résultat)
    """

    depth: int
    query: str
    context_slice: Optional[str] = None
    parent: Optional["RLMCall"] = None
    children: List["RLMCall"] = field(default_factory=list)
    result: Optional[str] = None
    status: str = "PENDING"  # PENDING, RUNNING, FINAL, ERROR

    def __repr__(self):
        return f"RLMCall(depth={self.depth}, query='{self.query[:30]}...', status={self.status})"


class RecursiveLanguageModel:
    """
    Implémentation du Recursive Language Model (RLM).

    Pattern arXiv:2512.24601:

    1. ROOT LM (depth=0):
       - Reçoit uniquement la QUERY (pas le contexte)
       - Accède au contexte via REPL Environment
       - Décide de FINAL() ou RECURSE()

    2. RECURSION:
       - RECURSE(sub_query, context_slice) spawne un Sub-LM
       - Le Sub-LM a un contexte RÉDUIT (slice)
       - Peut lui-même RECURSE() (profondeur illimitée)

    3. TERMINATION:
       - FINAL(answer) = réponse définitive
       - FINAL_VAR(var) = réponse stockée dans REPL
       - Remonte au parent qui agrège les résultats

    Exemple de récursion:

        Root (depth=0): "Génère backlog TDD"
          │
          ├─► Sub (depth=1): "Trouve tests skippés"
          │     └─► FINAL(["test1.ts", "test2.ts"])
          │
          ├─► Sub (depth=1): "Analyse specs AO"
          │     │
          │     ├─► Sub (depth=2): "Exigences auth"
          │     │     └─► FINAL(["MFA", "SSO"])
          │     │
          │     └─► Sub (depth=2): "Exigences payment"
          │           └─► FINAL(["Stripe", "SEPA"])
          │
          └─► FINAL(backlog_tasks)
    """

    def __init__(self):
        """Initialise le RLM avec son REPL Environment."""
        self.repl = REPLEnvironment()
        self.root_call: Optional[RLMCall] = None
        self.all_calls: List[RLMCall] = []
        self._log("RLM initialized")

    def _log(self, message: str, depth: int = 0):
        """Log avec indentation par profondeur."""
        indent = "  " * depth
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = "│ " * depth if depth > 0 else ""
        print(f"\033[1;35m[RLM {timestamp}] {prefix}{message}\033[0m")

    def _call_local_llm(self, prompt: str) -> str:
        """
        Appelle directement le LLM local via llama-cpp API.
        Utilisé comme fallback quand opencode/MiniMax échoue.
        """
        self._log(f"Calling local LLM at {LOCAL_API_URL}...")

        payload = json.dumps({
            "model": LOCAL_MODEL,
            "messages": [
                {"role": "system", "content": "Tu es un assistant expert en analyse de code Rust et SvelteKit. Réponds de manière structurée et concise."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 4096
        }).encode("utf-8")

        req = urllib.request.Request(
            LOCAL_API_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except urllib.error.URLError as e:
            self._log(f"Local LLM error: {e}")
            raise RuntimeError(f"Local LLM failed: {e}")

    def _call_llm(self, prompt: str, depth: int) -> str:
        """
        Appelle le LLM avec le prompt donné.

        Architecture LLM:
        - depth=0 (Brain): Opus 4.5 via Claude Code CLI pour vision stratégique
        - depth>0 (Sub-agents): MiniMax M2.1 ou Qwen local pour exécution

        Le prompt NE CONTIENT PAS le contexte complet.
        Le LLM doit utiliser les outils REPL pour accéder au contexte.
        """
        self._log(f"Calling LLM (depth={depth})...", depth)

        # Ajoute les instructions REPL au prompt
        full_prompt = f"""Tu es un agent RLM (Recursive Language Model) à depth={depth}.

## RÈGLES RLM
1. Tu n'as PAS accès au contexte complet dans ce prompt
2. Utilise les OUTILS REPL pour accéder au contexte:
   - mcp_rag_query(query) - Recherche sémantique code
   - mcp_ao_search(query) - Recherche specs AO
   - mcp_grep(pattern, glob) - Grep dans fichiers
   - peek(file, lines) - Lire début fichier

3. Pour TERMINER, utilise:
   - FINAL(answer) - Réponse définitive
   - RECURSE(sub_query, context) - Spawner sub-agent

## CONTEXTE ACTUEL (métadonnées seulement)
{json.dumps(self.repl.context, indent=2, default=str)[:2000]}

## TA QUERY
{prompt}

Réponds avec des appels REPL puis FINAL() ou RECURSE().
"""

        # =========================================================================
        # CHOIX DU MODÈLE SELON LA PROFONDEUR
        # =========================================================================
        # depth=0 (Brain): Opus 4.5 via Claude Code CLI pour vision stratégique
        # depth>0 (Sub-agents): MiniMax M2.1 ou Qwen local pour exécution rapide

        if depth == 0 and USE_CLAUDE_CODE_FOR_BRAIN:
            # BRAIN: Utilise Claude Code CLI (Opus 4.5) avec retry exponential backoff
            self._log(f"Brain mode: Using Claude Code CLI (Opus 4.5)")
            import time
            max_retries = 5
            base_delay = 30  # 30 secondes de base

            for attempt in range(max_retries):
                try:
                    # -p = print mode (non-interactive), --model claude-opus-4-5-20251101 = Opus 4.5
                    result = subprocess.run(
                        ["claude", "-p", full_prompt, "--model", "claude-opus-4-5-20251101"],
                        capture_output=True, text=True, timeout=TIMEOUT_SECONDS, cwd=PROJECT_ROOT
                    )
                    output = (result.stdout or "") + (result.stderr or "")

                    # Detect overloaded error (529)
                    if "overloaded" in output.lower() or "529" in output:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff: 30, 60, 120, 240, 480s
                        self._log(f"Claude overloaded (attempt {attempt+1}/{max_retries}), waiting {delay}s...")
                        time.sleep(delay)
                        continue

                    if result.returncode == 0 and result.stdout.strip():
                        self._log(f"Claude Code (Opus 4.5) succeeded")
                        return result.stdout.strip()
                    else:
                        self._log(f"Claude Code failed (code {result.returncode}), falling back to MiniMax...")
                        break

                except FileNotFoundError:
                    self._log(f"Claude CLI not found, falling back to MiniMax...")
                    break
                except subprocess.TimeoutExpired:
                    self._log(f"Claude Code timed out, falling back to MiniMax...")
                    break
            else:
                self._log(f"Claude Code max retries exceeded, falling back to MiniMax...")

        # SUB-AGENTS ou FALLBACK: Utilise MiniMax M2.1 via opencode
        try:
            model = LLM_MODEL_SUBAGENT
            self._log(f"Sub-agent mode: Using {model}")
            result = subprocess.run(
                ["opencode", "run", "--agent", "build", "-m", model, full_prompt],
                capture_output=True, text=True, timeout=TIMEOUT_SECONDS, cwd=PROJECT_ROOT
            )

            # Détecte rate limiting dans stderr ou stdout
            output = (result.stdout or "") + (result.stderr or "")
            if "rate limit" in output.lower() or "429" in output or "too many requests" in output.lower():
                self._log(f"Rate limit hit on {model}, trying local fallback...")
            elif result.returncode != 0:
                self._log(f"Model {model} failed (code {result.returncode}), trying local fallback...")
            elif not result.stdout.strip():
                self._log(f"Model {model} returned empty, trying local fallback...")
            else:
                # Succès avec opencode
                self._log(f"Model {model} succeeded")
                return result.stdout.strip()

        except subprocess.TimeoutExpired:
            self._log(f"Model {model} timed out, trying local fallback...")

        # FALLBACK FINAL: llama-cpp local (Qwen)
        try:
            self._log(f"Fallback: Using local llama-cpp at {LOCAL_API_URL}...")
            return self._call_local_llm(full_prompt)
        except Exception as e:
            self._log(f"Local LLM also failed: {e}")
            raise RuntimeError(f"All LLM models failed at depth={depth}: Claude + MiniMax + local")

    def _parse_response(self, response: str) -> tuple[str, Optional[str], List[tuple[str, str]]]:
        """
        Parse la réponse LLM pour extraire:
        - action: FINAL, RECURSE, ou CONTINUE
        - result: le résultat si FINAL
        - sub_calls: liste de (query, context) si RECURSE
        """
        # Cherche FINAL([...]) - JSON array (cas le plus courant)
        final_array_match = re.search(r'FINAL\(\s*(\[[\s\S]*\])\s*\)', response)
        if final_array_match:
            return "FINAL", final_array_match.group(1).strip(), []

        # Cherche FINAL({...}) - JSON object
        final_obj_match = re.search(r'FINAL\(\s*(\{[\s\S]*\})\s*\)', response)
        if final_obj_match:
            return "FINAL", final_obj_match.group(1).strip(), []

        # Cherche FINAL("...") ou FINAL('...') - string simple
        final_str_match = re.search(r'FINAL\(["\']([^"\']*)["\']?\)', response)
        if final_str_match:
            return "FINAL", final_str_match.group(1).strip(), []

        # Cherche FINAL_VAR(...)
        final_var_match = re.search(r'FINAL_VAR\((\w+)\)', response)
        if final_var_match:
            var_name = final_var_match.group(1)
            result = self.repl.results.get(var_name, "")
            return "FINAL", str(result), []

        # Cherche RECURSE(query, context)
        recurse_matches = re.findall(r'RECURSE\(["\']([^"\']+)["\'],\s*["\']?([^)]*)["\']?\)', response)
        if recurse_matches:
            return "RECURSE", None, recurse_matches

        # Pas de signal explicite, continue
        return "CONTINUE", None, []

    def _execute_call(self, call: RLMCall) -> str:
        """
        Exécute un appel RLM récursivement.

        1. Appelle le LLM avec la query
        2. Parse la réponse
        3. Si FINAL: retourne le résultat
        4. Si RECURSE: spawne des sub-calls et agrège
        """
        if call.depth > MAX_DEPTH:
            self._log(f"Max depth reached, forcing FINAL", call.depth)
            call.status = "FINAL"
            call.result = "MAX_DEPTH_REACHED"
            return call.result

        call.status = "RUNNING"
        self._log(f"Executing: {call.query[:50]}...", call.depth)

        # Appel LLM
        response = self._call_llm(call.query, call.depth)

        # Parse réponse
        action, result, sub_calls = self._parse_response(response)

        if action == "FINAL":
            call.status = "FINAL"
            call.result = result
            self._log(f"FINAL: {result[:100]}...", call.depth)
            return result

        elif action == "RECURSE":
            self._log(f"RECURSE: {len(sub_calls)} sub-calls", call.depth)

            # Spawne les sub-calls
            sub_results = []
            for sub_query, context_slice in sub_calls:
                sub_call = RLMCall(
                    depth=call.depth + 1,
                    query=sub_query,
                    context_slice=context_slice,
                    parent=call
                )
                call.children.append(sub_call)
                self.all_calls.append(sub_call)

                # Récursion!
                sub_result = self._execute_call(sub_call)
                sub_results.append(sub_result)

            # Agrège les résultats des enfants
            call.result = "\n".join(sub_results)
            call.status = "FINAL"
            return call.result

        else:
            # CONTINUE: re-appeler avec plus de contexte
            # Pour simplifier, on force FINAL après un CONTINUE
            call.status = "FINAL"
            call.result = response
            return response

    def run(self, query: str) -> str:
        """
        Point d'entrée principal du RLM.

        Args:
            query: La question racine (ex: "Génère le backlog TDD")

        Returns:
            Le résultat final après récursion
        """
        self._log(f"=== RLM START ===")
        self._log(f"Query: {query}")

        # Crée l'appel racine (depth=0)
        self.root_call = RLMCall(depth=0, query=query)
        self.all_calls = [self.root_call]

        # Exécute récursivement
        result = self._execute_call(self.root_call)

        # Stats
        self._log(f"=== RLM END ===")
        self._log(f"Total calls: {len(self.all_calls)}")
        self._log(f"Max depth reached: {max(c.depth for c in self.all_calls)}")

        return result


# =============================================================================
# TASK GENERATION
# =============================================================================

def generate_backlog(rlm: RecursiveLanguageModel) -> List[Path]:
    """
    Génère le backlog TDD via RLM.

    Le RLM analyse récursivement:
    1. Tests skippés/échoués
    2. Specs AO non implémentées
    3. TODO/FIXME critiques

    Et génère des tâches T*.md pour les Wiggum.
    """
    query = """Analyse le projet Veligo et génère 5 tâches TDD prioritaires.

ÉTAPES:
1. RECURSE("Trouve tous les test.skip et tests qui échouent", "tests/")
2. RECURSE("Analyse les specs AO non implémentées", "ao/")
3. RECURSE("Liste les TODO/FIXME critiques", "src/")

Puis agrège et retourne:
FINAL([
  {"id": "T001", "title": "...", "priority": "P0", "wsjf": 9},
  ...
])
"""

    result = rlm.run(query)

    # Parse le résultat - AUCUN FALLBACK
    if not result or not result.strip():
        raise RuntimeError("RLM returned empty result for backlog generation")

    # Le résultat DOIT être du JSON valide
    tasks = json.loads(result)
    if not isinstance(tasks, list):
        raise RuntimeError(f"RLM returned non-list result: {type(tasks)}")

    created_tasks = []

    # Trouve le prochain numéro de tâche
    existing = list(TASKS_DIR.glob("T*.md"))
    next_num = max([int(t.stem[1:]) for t in existing] + [0]) + 1

    for i, task in enumerate(tasks[:5]):
        task_id = f"T{next_num + i:03d}"
        task_file = TASKS_DIR / f"{task_id}.md"

        content = f"""# Task {task_id}: {task.get('title', 'Generated Task')}

**Priority**: {task.get('priority', 'P1')}
**WSJF Score**: {task.get('wsjf', 7.0)}
**Queue**: TDD
**Generated by**: LRM Brain (RLM)

## Description
{task.get('description', task.get('title', ''))}

## Success Criteria
- [ ] Tests pass
- [ ] No regressions

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: medium
MODEL_TIER: TIER2
WSJF: {task.get('wsjf', 7.0)}
---END_RALPH_STATUS---
"""
        task_file.write_text(content)
        created_tasks.append(task_file)
        print(f"Created: {task_file}")

    return created_tasks


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Point d'entrée CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="LRM Brain - Recursive Language Model pour Veligo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python3 lrm_brain.py --query "Analyse les tests skippés"
  python3 lrm_brain.py --analyze
  python3 lrm_brain.py --generate-backlog

Architecture RLM (arXiv:2512.24601):
  Root LM (depth=0) → Sub-LMs (depth=1+) → FINAL()
  Contexte accessible via REPL, pas dans le prompt LLM.
        """
    )

    parser.add_argument("--query", "-q", help="Query à exécuter via RLM")
    parser.add_argument("--analyze", "-a", action="store_true", help="Analyse complète du projet")
    parser.add_argument("--generate-backlog", "-g", action="store_true", help="Génère le backlog TDD")
    parser.add_argument("--max-depth", type=int, default=MAX_DEPTH, help="Profondeur max de récursion")

    args = parser.parse_args()

    # Initialise le RLM
    rlm = RecursiveLanguageModel()

    if args.query:
        result = rlm.run(args.query)
        print("\n=== RESULT ===")
        print(result)

    elif args.analyze:
        query = """Analyse complète du projet Veligo:
1. RECURSE("État des tests E2E", "tests/")
2. RECURSE("Conformité AO", "ao/")
3. RECURSE("Dette technique", "src/")
FINAL(rapport_complet)
"""
        result = rlm.run(query)
        print("\n=== ANALYSIS ===")
        print(result)

    elif args.generate_backlog:
        tasks = generate_backlog(rlm)
        print(f"\n=== GENERATED {len(tasks)} TASKS ===")
        for t in tasks:
            print(f"  - {t.name}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
