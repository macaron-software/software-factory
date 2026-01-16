#!/usr/bin/env python3
"""
Ralph Meta-Orchestrator - Analyse LEAN & Génération automatique de queues
=========================================================================

CONTEXTE COMPLET:
- Lit TOUS les fichiers AO (Appel d'Offres)
- Lit TOUT le code source (Rust, TS, Svelte, Proto)
- Lit TOUS les markdown (_docs, CLAUDE.md, README)
- Utilise le RAG veligo pour enrichir le contexte

MODÈLES PAR COMPLEXITÉ:
- TIER 1 (Complex): Claude Opus 4.5 via Claude Code headless (Claude Max subscription)
- TIER 2 (Medium): GLM-4.7 / Minimax via OpenCode server (gratuit)
- TIER 3 (Simple): Qwen3-Coder local via llama-server

ACCÈS MODÈLES (PAS d'appels API!):
- Claude: subprocess `claude -p "prompt"` (Claude Code headless, Claude Max abo)
- GLM/Minimax: subprocess `opencode run "prompt"` (OpenCode server, gratuit)
- Local: HTTP llama-server:8000 (Qwen3-Coder-30B local)

GUARDRAILS ANTI-LOOP:
- Turn limits (max 25 appels par tâche)
- Timeout (5 min par exécution)
- Repetition detection (sliding window)
- Token budget avec circuit breaker
"""

import os
import sys
import json
import time
import hashlib
import subprocess
import re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple, Set
from collections import deque
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import signal
import socket

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
TASKS_DIR = Path(__file__).parent / "tasks"
LOGS_DIR = Path(__file__).parent / "logs"
ANALYSIS_CACHE = Path(__file__).parent / ".analysis_cache"

# RAG Integration
RAG_INDEX_PATH = PROJECT_ROOT / ".ralph-rag"
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from ralph_rag import query_rag, get_context_for_task
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("[WARN] RAG not available - will use direct file reading")

# MCP RAG Integration
try:
    from mcp_rag_server import search_code, search_ao
    MCP_RAG_AVAILABLE = True
except ImportError:
    MCP_RAG_AVAILABLE = False

# ============================================================================
# MODEL TIERS
# ============================================================================

class ModelTier(Enum):
    TIER1_COMPLEX = "opus"      # Architecture, security, complex design
    TIER2_MEDIUM = "glm"        # Implementation, refactoring
    TIER3_SIMPLE = "local"      # Fixes, tests, documentation

# Model configurations - NO API CALLS, uses subprocess or local HTTP
MODELS = {
    "opus": {
        "name": "Claude Opus 4.5 (Claude Code headless)",
        "cli": "claude",                    # Claude Code CLI
        "model_id": "claude-opus-4-5-20251101",
        "max_tokens": 16000,
        "context_window": 200000,
        "type": "claude_cli"                # subprocess claude -p
    },
    "glm": {
        "name": "GLM-4.7 Free (OpenCode)",
        "cli": "opencode",                  # OpenCode CLI
        "model_id": "opencode/glm-4.7-free",  # Free model
        "max_tokens": 8000,
        "context_window": 128000,
        "type": "opencode"                  # subprocess opencode run
    },
    "minimax": {
        "name": "Minimax M2.1 Free (OpenCode)",
        "cli": "opencode",                  # OpenCode CLI
        "model_id": "opencode/minimax-m2.1-free",  # Free model
        "max_tokens": 8000,
        "context_window": 64000,
        "type": "opencode"                  # subprocess opencode run
    },
    "deepseek": {
        "name": "DeepSeek-V3 (Local llama-server)",
        "url": "http://127.0.0.1:8001/v1/completions",  # DeepSeek on port 8001
        "model_id": "deepseek-v3",
        "max_tokens": 8000,
        "context_window": 64000,
        "type": "llama"                     # HTTP llama-server
    },
    "local": {
        "name": "Qwen3-Coder-30B (Local llama-server)",
        "url": "http://127.0.0.1:8000/v1/completions",  # Qwen on port 8000
        "model_id": "qwen3-coder",
        "max_tokens": 16000,
        "context_window": 65536,
        "type": "llama"                     # HTTP llama-server
    }
}

FALLBACK_CHAIN = {
    ModelTier.TIER1_COMPLEX: ["opus", "glm", "deepseek"],
    ModelTier.TIER2_MEDIUM: ["glm", "minimax", "local"],
    ModelTier.TIER3_SIMPLE: ["local", "deepseek", "minimax"]
}

# ============================================================================
# GUARDRAILS (Anti-Loop Protection)
# ============================================================================

MAX_TURNS_PER_TASK = 25
MAX_EXECUTION_TIME_SECONDS = 300
REPETITION_WINDOW = 3
TOKEN_BUDGET = 500000  # 500K tokens max per run

@dataclass
class GuardrailState:
    turn_count: int = 0
    start_time: float = field(default_factory=time.time)
    action_history: deque = field(default_factory=lambda: deque(maxlen=REPETITION_WINDOW))
    token_budget: int = TOKEN_BUDGET
    tokens_used: int = 0

    def is_safe(self, action: str) -> Tuple[bool, str]:
        if self.turn_count >= MAX_TURNS_PER_TASK:
            return False, f"Turn limit ({MAX_TURNS_PER_TASK})"
        if (time.time() - self.start_time) >= MAX_EXECUTION_TIME_SECONDS:
            return False, f"Timeout ({MAX_EXECUTION_TIME_SECONDS}s)"
        self.action_history.append(action[:50])
        if len(self.action_history) == REPETITION_WINDOW and len(set(self.action_history)) == 1:
            return False, "Loop detected"
        if self.tokens_used >= self.token_budget:
            return False, f"Token budget ({self.token_budget})"
        return True, "OK"

# ============================================================================
# RLM SERVER MANAGER (arXiv:2512.24601 - Recursive Language Models)
# ============================================================================

class RLMServeManager:
    """
    RLM Server Manager - Manages opencode serve instances for sub-agents.

    Pattern from MIT CSAIL paper (arXiv:2512.24601 - Zhang, Kraska, Khattab):
    - Meta-Orchestrator spawns headless server
    - Sub-agents connect via --attach for shared context
    - Enables parallel execution with coordinated state

    Usage:
        with RLMServeManager(port=4096) as rlm:
            result = rlm.run_subagent("task prompt", agent="build")
    """

    def __init__(self, port: int = 0, model: str = "opencode/glm-4.7-free"):
        self.port = port  # 0 = random available port
        self.model = model
        self.process: Optional[subprocess.Popen] = None
        self.actual_port: Optional[int] = None
        self._started = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def _find_free_port(self) -> int:
        """Find a free port if none specified."""
        if self.port != 0:
            return self.port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    def start(self) -> int:
        """Start opencode serve and return the port."""
        if self._started:
            return self.actual_port

        self.actual_port = self._find_free_port()

        cmd = [
            "opencode", "serve",
            "--port", str(self.actual_port),
            "--hostname", "127.0.0.1",
            "--log-level", "WARN"
        ]

        print(f"[RLM] Starting opencode serve on port {self.actual_port}...")

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(PROJECT_ROOT)
        )

        # Wait for server to be ready
        time.sleep(2)

        if self.process.poll() is not None:
            stderr = self.process.stderr.read().decode()
            raise RuntimeError(f"opencode serve failed to start: {stderr}")

        self._started = True
        print(f"[RLM] Server ready at http://127.0.0.1:{self.actual_port}")
        return self.actual_port

    def stop(self):
        """Stop the opencode serve process."""
        if self.process and self.process.poll() is None:
            print(f"[RLM] Stopping server on port {self.actual_port}...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self._started = False

    def run_subagent(
        self,
        prompt: str,
        agent: str = "build",
        timeout: int = 300
    ) -> Tuple[str, int]:
        """
        Run a sub-agent connected to this RLM serve instance.

        Args:
            prompt: The task prompt for the sub-agent
            agent: Agent type (build, explore, general)
            timeout: Max execution time in seconds

        Returns:
            Tuple of (response content, estimated tokens)
        """
        if not self._started:
            raise RuntimeError("RLM server not started. Use 'with RLMServeManager() as rlm:'")

        attach_url = f"http://127.0.0.1:{self.actual_port}"

        cmd = [
            "opencode", "run",
            "--attach", attach_url,
            "--agent", agent,
            "-m", self.model,
            prompt
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(PROJECT_ROOT)
            )

            content = result.stdout.strip()
            if result.returncode != 0 and not content:
                content = f"[ERROR] {result.stderr[:500]}"

            # Estimate tokens (~4 chars per token)
            tokens = len(prompt) // 4 + len(content) // 4
            return content, tokens

        except subprocess.TimeoutExpired:
            return f"[TIMEOUT] Sub-agent exceeded {timeout}s", 0
        except Exception as e:
            return f"[ERROR] {str(e)}", 0

    def run_parallel_subagents(
        self,
        tasks: List[Dict[str, str]],
        max_workers: int = 3
    ) -> List[Dict]:
        """
        Run multiple sub-agents in parallel.

        Args:
            tasks: List of {"id": "T001", "prompt": "task prompt", "agent": "build"}
            max_workers: Max concurrent sub-agents

        Returns:
            List of {"id": "T001", "result": "...", "tokens": 123, "success": True}
        """
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for task in tasks:
                future = executor.submit(
                    self.run_subagent,
                    task.get("prompt", ""),
                    task.get("agent", "build"),
                    task.get("timeout", 300)
                )
                futures[future] = task.get("id", "unknown")

            for future in as_completed(futures):
                task_id = futures[future]
                try:
                    content, tokens = future.result()
                    success = not content.startswith("[ERROR]") and not content.startswith("[TIMEOUT]")
                    results.append({
                        "id": task_id,
                        "result": content,
                        "tokens": tokens,
                        "success": success
                    })
                except Exception as e:
                    results.append({
                        "id": task_id,
                        "result": f"[EXCEPTION] {str(e)}",
                        "tokens": 0,
                        "success": False
                    })

        return results


# Global RLM instance for reuse
_rlm_instance: Optional[RLMServeManager] = None

def get_rlm_server(port: int = 4096) -> RLMServeManager:
    """Get or create a singleton RLM server instance."""
    global _rlm_instance
    if _rlm_instance is None or not _rlm_instance._started:
        _rlm_instance = RLMServeManager(port=port)
        _rlm_instance.start()
    return _rlm_instance

def shutdown_rlm_server():
    """Shutdown the global RLM server."""
    global _rlm_instance
    if _rlm_instance:
        _rlm_instance.stop()
        _rlm_instance = None


# ============================================================================
# FULL PROJECT CONTEXT BUILDER
# ============================================================================

class ProjectContextBuilder:
    """Build complete project context for analysis"""

    # File patterns to include
    INCLUDE_PATTERNS = {
        # Code
        "**/*.rs": "rust",
        "**/*.ts": "typescript",
        "**/*.tsx": "typescript",
        "**/*.svelte": "svelte",
        "**/*.proto": "protobuf",
        "**/*.sql": "sql",
        # Config
        "**/*.toml": "toml",
        "**/package.json": "json",
        # Docs
        "**/*.md": "markdown",
        # AO Documents
        "_ao/**/*": "ao",
        "_docs/**/*": "docs",
    }

    EXCLUDE_PATTERNS = [
        "node_modules", "target", "dist", "build", ".git",
        "__pycache__", ".next", ".svelte-kit", "coverage",
        ".ralph-rag", "tdd-output", "*.lock"
    ]

    def __init__(self, project_root: Path):
        self.root = project_root
        self.files: Dict[str, Dict] = {}
        self.ao_documents: List[Dict] = []
        self.code_stats: Dict = {}

    def scan_all(self) -> Dict:
        """Scan entire project"""
        print("\n[CONTEXT] Scanning project...")

        # Scan all file types
        for pattern, filetype in self.INCLUDE_PATTERNS.items():
            for filepath in self.root.glob(pattern):
                if self._should_exclude(filepath):
                    continue
                self._process_file(filepath, filetype)

        # Build stats
        self._compute_stats()

        print(f"[CONTEXT] Found {len(self.files)} files, {len(self.ao_documents)} AO docs")
        return {
            "files": self.files,
            "ao_documents": self.ao_documents,
            "stats": self.code_stats
        }

    def _should_exclude(self, path: Path) -> bool:
        path_str = str(path)
        return any(exc in path_str for exc in self.EXCLUDE_PATTERNS)

    def _process_file(self, filepath: Path, filetype: str):
        try:
            content = filepath.read_text(errors='ignore')
            rel_path = str(filepath.relative_to(self.root))

            file_info = {
                "path": rel_path,
                "type": filetype,
                "lines": len(content.splitlines()),
                "size": len(content),
                "content": content if len(content) < 50000 else content[:50000] + "\n... [TRUNCATED]"
            }

            # Special handling for AO documents
            if filetype == "ao" or "_ao" in rel_path or "ao-" in rel_path.lower():
                self.ao_documents.append(file_info)
            else:
                self.files[rel_path] = file_info

        except Exception as e:
            print(f"[WARN] Could not read {filepath}: {e}")

    def _compute_stats(self):
        by_type = {}
        total_lines = 0

        for path, info in self.files.items():
            ftype = info["type"]
            by_type[ftype] = by_type.get(ftype, 0) + 1
            total_lines += info["lines"]

        self.code_stats = {
            "total_files": len(self.files),
            "total_lines": total_lines,
            "by_type": by_type,
            "ao_documents": len(self.ao_documents)
        }

    def get_context_for_tier(self, tier: ModelTier, max_tokens: int = 100000) -> str:
        """Get context sized for model's context window"""
        context_parts = []
        current_size = 0
        char_limit = max_tokens * 4  # ~4 chars per token

        # 1. Always include CLAUDE.md and key docs
        priority_files = [
            "CLAUDE.md",
            "veligo-platform/backend/Cargo.toml",
            "veligo-platform/frontend/package.json",
        ]

        for pf in priority_files:
            if pf in self.files:
                content = self.files[pf]["content"]
                if current_size + len(content) < char_limit:
                    context_parts.append(f"=== {pf} ===\n{content}\n")
                    current_size += len(content)

        # 2. Include AO documents (critical for requirements)
        context_parts.append("\n=== APPEL D'OFFRES (Requirements) ===\n")
        for ao in self.ao_documents[:10]:  # Top 10 AO docs
            summary = ao["content"][:5000] if ao["lines"] > 100 else ao["content"]
            if current_size + len(summary) < char_limit * 0.3:  # 30% budget for AO
                context_parts.append(f"\n--- {ao['path']} ---\n{summary}\n")
                current_size += len(summary)

        # 3. Include code based on tier
        if tier == ModelTier.TIER1_COMPLEX:
            # Complex: Focus on architecture files
            arch_patterns = ["mod.rs", "lib.rs", "main.rs", "+page.svelte", "+layout.svelte", ".proto"]
            for path, info in self.files.items():
                if any(p in path for p in arch_patterns):
                    if current_size + len(info["content"]) < char_limit * 0.5:
                        context_parts.append(f"\n=== {path} ===\n{info['content']}\n")
                        current_size += len(info["content"])

        elif tier == ModelTier.TIER2_MEDIUM:
            # Medium: Include service implementations
            svc_patterns = ["service", "handler", "api", "grpc"]
            for path, info in self.files.items():
                if any(p in path.lower() for p in svc_patterns):
                    if current_size + len(info["content"]) < char_limit * 0.5:
                        context_parts.append(f"\n=== {path} ===\n{info['content']}\n")
                        current_size += len(info["content"])

        else:
            # Simple: Just file list
            context_parts.append("\n=== File List ===\n")
            for path, info in list(self.files.items())[:200]:
                context_parts.append(f"- {path} ({info['type']}, {info['lines']} lines)\n")

        return "".join(context_parts)

    def get_full_ao_context(self) -> str:
        """Get all AO documents as context"""
        parts = ["# APPEL D'OFFRES - Complete Requirements\n\n"]
        for ao in self.ao_documents:
            parts.append(f"## {ao['path']}\n\n{ao['content']}\n\n---\n\n")
        return "".join(parts)

# ============================================================================
# MODEL CLIENT - Subprocess-based (NO API calls!)
# ============================================================================

class ModelClient:
    """
    Model client using subprocess calls instead of HTTP API.

    - Claude: `claude -p "prompt"` (Claude Code headless, Claude Max subscription)
    - GLM/Minimax: `opencode run "prompt"` (OpenCode server, free)
    - Local: HTTP to llama-server (Qwen3-Coder / DeepSeek local)
    """

    def __init__(self, model_key: str):
        self.key = model_key
        self.config = MODELS[model_key]
        self.name = self.config["name"]

    def call(self, prompt: str, system: str = "", context: str = "", max_tokens: int = None) -> Tuple[str, int]:
        max_tokens = max_tokens or self.config["max_tokens"]

        # Prepend system and context to prompt
        full_prompt = ""
        if system:
            full_prompt += f"SYSTEM:\n{system}\n\n"
        if context:
            full_prompt += f"CONTEXT:\n{context}\n\n---\n\n"
        full_prompt += prompt

        model_type = self.config["type"]

        if model_type == "claude_cli":
            return self._call_claude_cli(full_prompt, max_tokens)
        elif model_type == "opencode":
            return self._call_opencode(full_prompt, max_tokens)
        elif model_type == "llama":
            return self._call_llama(full_prompt, system, max_tokens)
        else:
            raise ValueError(f"Unknown type: {model_type}")

    def _call_claude_cli(self, prompt: str, max_tokens: int) -> Tuple[str, int]:
        """
        Call Claude via Claude Code CLI (headless mode).
        Uses Claude Max subscription - no API costs.

        Command: claude -p "prompt" --output-format text --dangerously-skip-permissions
        """
        import tempfile

        # Write prompt to temp file to avoid shell escaping issues
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            # Claude CLI command (no --max-tokens option available)
            # Use --model opus for best results, --dangerously-skip-permissions for headless
            result = subprocess.run(
                f'cat "{prompt_file}" | claude -p --output-format text --model opus --dangerously-skip-permissions',
                shell=True,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(PROJECT_ROOT)
            )

            if result.returncode != 0:
                print(f"[WARN] Claude CLI error: {result.stderr[:200]}")
                raise RuntimeError(f"Claude CLI failed: {result.stderr}")

            content = result.stdout.strip()
            # Estimate tokens (~4 chars per token)
            tokens = len(prompt) // 4 + len(content) // 4
            return content, tokens

        finally:
            os.unlink(prompt_file)

    def _call_opencode(self, prompt: str, max_tokens: int) -> Tuple[str, int]:
        """
        Call GLM/Minimax via OpenCode CLI.
        Free access - no API costs.

        Command: opencode run -m opencode/glm-4.7-free "prompt"
        """
        import tempfile

        model_id = self.config["model_id"]

        # Write prompt to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            # OpenCode CLI command: opencode run -m model -f file "message"
            # Use -f to attach the prompt file
            result = subprocess.run(
                ["opencode", "run", "-m", model_id, "-f", prompt_file, "Analyze and respond to the attached prompt"],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(PROJECT_ROOT)
            )

            if result.returncode != 0:
                print(f"[WARN] OpenCode CLI error: {result.stderr[:200]}")
                raise RuntimeError(f"OpenCode CLI failed: {result.stderr}")

            content = result.stdout.strip()
            tokens = len(prompt) // 4 + len(content) // 4
            return content, tokens

        finally:
            os.unlink(prompt_file)

    def _call_llama(self, prompt: str, system: str, max_tokens: int) -> Tuple[str, int]:
        """
        Call local llama-server via HTTP.
        Qwen3-Coder on :8000, DeepSeek on :8001.
        """
        full = f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
        payload = {
            "prompt": full,
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "stop": ["<|im_end|>"]
        }

        resp = requests.post(self.config["url"], json=payload, timeout=600)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["text"]
        # Remove <think> blocks if present
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        return content, len(prompt) // 4 + len(content) // 4

    def is_available(self) -> bool:
        """Check if the model is available."""
        try:
            model_type = self.config["type"]

            if model_type == "claude_cli":
                # Check if claude CLI is installed and working
                result = subprocess.run(
                    ["claude", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return result.returncode == 0

            elif model_type == "opencode":
                # Check if opencode CLI is installed
                result = subprocess.run(
                    ["opencode", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return result.returncode == 0

            elif model_type == "llama":
                # Check if llama-server is running
                url = self.config["url"].replace("/completions", "/health")
                resp = requests.get(url, timeout=2)
                return resp.status_code == 200

            return False

        except Exception as e:
            print(f"[DEBUG] {self.key} not available: {e}")
            return False


def get_model(tier: ModelTier) -> Optional[ModelClient]:
    """Get the first available model for the given tier."""
    for key in FALLBACK_CHAIN[tier]:
        client = ModelClient(key)
        if client.is_available():
            print(f"      ✓ Using {client.name}")
            return client
        else:
            print(f"      ✗ {MODELS[key]['name']} not available")
    return None

# ============================================================================
# LEAN ANALYSIS PROMPTS
# ============================================================================

LEAN_SYSTEM = """Tu es un expert LEAN en ingénierie logicielle. Tu analyses le code avec les principes:

## MUDA (7 Gaspillages)
1. Défauts - Bugs, failles sécurité, tests cassés
2. Surproduction - Code mort, over-engineering
3. Attente - Blocages, dépendances manquantes
4. Talent non-utilisé - Code trop complexe
5. Transport - Appels API redondants
6. Inventaire - Dette technique accumulée
7. Mouvement - Mauvaise DX, structure floue
8. Sur-traitement - Abstractions inutiles

## MURI (Surcharge)
- Fichiers > 500 lignes
- Fonctions > 50 lignes
- Complexité cyclomatique > 10

## MURA (Irrégularité)
- Patterns incohérents entre modules
- Styles de code mixtes
- Couverture de tests inégale

## VALUE STREAM
Identifier le flux de la demande utilisateur au déploiement."""

LEAN_PROMPT = """Analyse ce projet avec une vision LEAN et génère les queues de tâches.

# CONTEXTE PROJET
{project_context}

# EXIGENCES AO (Appel d'Offres)
{ao_context}

# STATISTIQUES
{stats}

# TA MISSION

1. **ANALYSER** le code avec les 7 gaspillages MUDA
2. **IDENTIFIER** les problèmes MURI (surcharge) et MURA (irrégularité)
3. **MAPPER** le Value Stream (goulots d'étranglement)
4. **PRIORISER** avec WSJF = (Valeur + Criticité + Risque) / Taille
5. **GÉNÉRER** les tâches Ralph Wiggum

# FORMAT DE SORTIE

```json
{{
  "analysis": {{
    "muda": [
      {{"type": "defect|overproduction|waiting|...", "description": "...", "file": "...", "severity": "P0|P1|P2|P3", "wsjf": 8.5}}
    ],
    "muri": [...],
    "mura": [...],
    "value_stream": {{
      "bottlenecks": ["..."],
      "blockers": ["..."]
    }}
  }},
  "queues": {{
    "tdd": [
      {{
        "id": "T001",
        "title": "...",
        "priority": "P0",
        "wsjf": 9.5,
        "complexity": "simple|medium|complex",
        "tier": "TIER1|TIER2|TIER3",
        "description": "...",
        "success_criteria": ["...", "..."],
        "actions": ["1. ...", "2. ..."],
        "files": ["path/to/file"]
      }}
    ],
    "deploy": [...]
  }}
}}
```

Génère au moins 15 tâches TDD et 5 tâches Deploy, triées par WSJF décroissant.
"""

# ============================================================================
# TASK GENERATOR
# ============================================================================

class TaskGenerator:
    def __init__(self, tasks_dir: Path):
        self.tasks_dir = tasks_dir
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def generate_from_analysis(self, analysis: Dict) -> List[Path]:
        queues = analysis.get("queues", {})
        generated = []

        # Generate TDD tasks
        for task in queues.get("tdd", []):
            path = self._write_task(task)
            generated.append(path)

        # Generate Deploy tasks
        for task in queues.get("deploy", []):
            path = self._write_task(task)
            generated.append(path)

        return generated

    def _write_task(self, task: Dict) -> Path:
        task_id = task.get("id", "T000")
        tier = task.get("tier", "TIER2")
        complexity = task.get("complexity", "medium")

        criteria = "\n".join([f"- [ ] {c}" for c in task.get("success_criteria", ["Complete task"])])
        actions = "\n".join(task.get("actions", ["1. Analyze", "2. Implement", "3. Test"]))
        files = "\n".join([f"- [ ] {f} (MODIFY)" for f in task.get("files", [])])

        content = f"""# Task {task_id}: {task.get('title', 'Unnamed Task')}

**Priority**: {task.get('priority', 'P2')}
**Time Estimate**: {self._time_estimate(complexity)}h
**WSJF Score**: {task.get('wsjf', 5.0)}
**Complexity**: {complexity}
**Queue**: {'TDD' if task_id.startswith('T') else 'DEPLOY'}

## Description
{task.get('description', 'No description provided.')}

## Success Criteria
{criteria}

## Actions
{actions}

## Files to Create/Modify
{files if files else '- [ ] TBD'}

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: {complexity}
MODEL_TIER: {tier}
WSJF: {task.get('wsjf', 5.0)}
---END_RALPH_STATUS---
"""

        path = self.tasks_dir / f"{task_id}.md"
        path.write_text(content)
        print(f"  ✓ {task_id}: {task.get('title', '')[:50]}")
        return path

    def _time_estimate(self, complexity: str) -> float:
        return {"simple": 0.5, "medium": 1.5, "complex": 3.0}.get(complexity, 1.0)

# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

class RalphMetaOrchestrator:
    def __init__(self, project_root: Path, tasks_dir: Path):
        self.project_root = project_root
        self.tasks_dir = tasks_dir
        self.guardrails = GuardrailState()
        self.context_builder = ProjectContextBuilder(project_root)

    def run(self) -> Dict:
        print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║  RALPH META-ORCHESTRATOR v2.0                                        ║
║  Full Project Context + LEAN Analysis + Auto Queue Generation        ║
╠══════════════════════════════════════════════════════════════════════╣
║  Guardrails: {MAX_TURNS_PER_TASK} turns, {MAX_EXECUTION_TIME_SECONDS}s timeout, {TOKEN_BUDGET:,} token budget           ║
╚══════════════════════════════════════════════════════════════════════╝
""")

        # 1. Scan entire project
        print("[1/4] Building complete project context...")
        project_data = self.context_builder.scan_all()
        print(f"      Stats: {json.dumps(project_data['stats'], indent=2)}")

        # 2. Check models
        print("\n[2/4] Checking model availability...")
        tier1 = get_model(ModelTier.TIER1_COMPLEX)
        tier2 = get_model(ModelTier.TIER2_MEDIUM)
        tier3 = get_model(ModelTier.TIER3_SIMPLE)

        print(f"      TIER1 (Complex): {tier1.name if tier1 else '✗ None'}")
        print(f"      TIER2 (Medium):  {tier2.name if tier2 else '✗ None'}")
        print(f"      TIER3 (Simple):  {tier3.name if tier3 else '✗ None'}")

        # Use best available model
        model = tier1 or tier2 or tier3
        if not model:
            print("[ERROR] No model available!")
            return {"error": "No model available"}

        # 3. Run LEAN analysis with full context
        print(f"\n[3/4] Running LEAN analysis with {model.name}...")

        # Get appropriately sized context
        tier = ModelTier.TIER1_COMPLEX if tier1 else ModelTier.TIER2_MEDIUM if tier2 else ModelTier.TIER3_SIMPLE
        context = self.context_builder.get_context_for_tier(tier)
        ao_context = self.context_builder.get_full_ao_context()[:50000]  # Limit AO context

        prompt = LEAN_PROMPT.format(
            project_context=context[:100000],
            ao_context=ao_context,
            stats=json.dumps(project_data["stats"], indent=2)
        )

        # Check guardrails
        safe, reason = self.guardrails.is_safe("lean_analysis")
        if not safe:
            print(f"[GUARDRAIL] {reason}")
            return {"error": reason}

        self.guardrails.turn_count += 1

        try:
            response, tokens = model.call(prompt, system=LEAN_SYSTEM)
            self.guardrails.tokens_used += tokens
            print(f"      Used {tokens:,} tokens")

            # Parse JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                print("[WARN] Could not parse JSON, using raw response")
                analysis = {"raw_response": response[:2000]}

        except Exception as e:
            print(f"[ERROR] Analysis failed: {e}")
            return {"error": str(e)}

        # Save analysis
        ANALYSIS_CACHE.mkdir(parents=True, exist_ok=True)
        cache_file = ANALYSIS_CACHE / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(cache_file, "w") as f:
            json.dump(analysis, f, indent=2, default=str)
        print(f"      Saved to {cache_file}")

        # 4. Generate tasks
        print("\n[4/4] Generating task queues...")
        generator = TaskGenerator(self.tasks_dir)

        if "queues" in analysis:
            generated = generator.generate_from_analysis(analysis)
            print(f"\n      Generated {len(generated)} tasks")
        else:
            print("[WARN] No queues in analysis, generating defaults")
            generated = []

        return {
            "stats": project_data["stats"],
            "analysis": analysis,
            "tasks_generated": len(generated),
            "tokens_used": self.guardrails.tokens_used
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ralph Meta-Orchestrator")
    parser.add_argument("--project", "-p", default=str(PROJECT_ROOT))
    parser.add_argument("--output", "-o", default=str(TASKS_DIR))
    args = parser.parse_args()

    orchestrator = RalphMetaOrchestrator(
        project_root=Path(args.project),
        tasks_dir=Path(args.output)
    )

    result = orchestrator.run()

    print(f"""
{'='*70}
  COMPLETE

  Files analyzed: {result.get('stats', {}).get('total_files', 0)}
  AO documents:   {result.get('stats', {}).get('ao_documents', 0)}
  Tasks generated: {result.get('tasks_generated', 0)}
  Tokens used:    {result.get('tokens_used', 0):,}
{'='*70}

Next steps:
  1. Review tasks in {args.output}
  2. ./ralph_wiggum_veligo.sh tdd
  3. ./ralph_wiggum_veligo.sh deploy
""")


if __name__ == "__main__":
    main()
