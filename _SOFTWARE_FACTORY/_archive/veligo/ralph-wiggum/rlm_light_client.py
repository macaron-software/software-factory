#!/usr/bin/env python3
"""
RLM Light Client - Agent minimaliste avec tools
Bypass opencode (40-60k overhead) en gardant les outils essentiels

Architecture:
1. Multi-backend: Local Qwen, Minimax M2, fallback chain
2. Tools intégrés: read, edit, bash, grep
3. Agentic loop avec tool calling
4. ~2k tokens system prompt vs 40-60k pour opencode
5. Rate limiting pour API cloud (200 calls/h)
"""

import json
import subprocess
import sys
import re
import os
from pathlib import Path
import requests
from typing import Optional, Dict, Any, List
import time

# Configuration
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # /Users/sylvain/_LAPOSTE/_VELIGO2 (veligo root)

# Backend configuration
LLM_BACKEND = os.getenv("LLM_BACKEND", "local")  # "local", "minimax", "auto"

# Local Qwen configuration
LOCAL_API_URL = os.getenv("LOCAL_API_URL", "http://127.0.0.1:8002/v1/chat/completions")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen3")

# Cloud API configuration (MiniMax Coding Plan or OpenAI-compatible)
CLOUD_API_URL = os.getenv("CLOUD_API_URL", "https://api.minimax.io/v1/chat/completions")
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", os.getenv("MINIMAX_API_KEY", ""))
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "MiniMax-M2.1")  # Coding Plan model

# Shared config
LLAMA_MAX_TOKENS = int(os.getenv("LLAMA_MAX_TOKENS", "8192"))
TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "7200"))

# Rate limiter import
sys.path.insert(0, str(SCRIPT_DIR))
try:
    from rate_limiter import can_make_call, record_call, get_wait_time, get_stats
    RATE_LIMITER_AVAILABLE = True
except ImportError:
    RATE_LIMITER_AVAILABLE = False
    def can_make_call(): return (True, 0, 200)
    def record_call(): return 0
    def get_wait_time(): return 0
    def get_stats(): return {}

# System prompt minimaliste (~2k tokens)
SYSTEM_PROMPT = """Tu es un agent RLM (Read-Like-Modify). Tu as accès à ces outils:

## OUTILS DISPONIBLES

### read
Lit un fichier. Usage: {"tool": "read", "path": "<chemin>"}

### edit
Modifie un fichier (find/replace). Usage: {"tool": "edit", "path": "<chemin>", "old": "<texte à remplacer>", "new": "<nouveau texte>"}

### bash
Exécute une commande bash. Usage: {"tool": "bash", "command": "<commande>"}

### grep
Recherche dans les fichiers. Usage: {"tool": "grep", "pattern": "<regex>", "path": "<chemin ou glob>"}

### done
Termine la tâche. Usage: {"tool": "done", "result": "<résumé>"}

## RÈGLES RLM (Read-Like-Modify)

1. **VERIFY BEFORE MODIFY**: Toujours lire (read/grep) avant d'éditer
2. **SMALL BATCHES**: Un seul changement à la fois
3. **NO HALLUCINATION**: Ne jamais inventer de fichiers ou de code
4. **TEST AFTER CHANGE**: Toujours vérifier avec bash après modification

## FORMAT DE RÉPONSE

Pour utiliser un outil, réponds EXACTEMENT avec ce format JSON sur une ligne:
{"tool": "<nom>", ...params}

Tu peux ajouter du texte explicatif AVANT l'appel d'outil, mais l'appel doit être sur une ligne seule.
"""

def call_local_llm(messages: List[Dict[str, str]], max_tokens: int = LLAMA_MAX_TOKENS) -> Optional[str]:
    """Appel direct à llama.cpp API locale"""
    payload = {
        "model": LOCAL_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }

    try:
        response = requests.post(
            LOCAL_API_URL,
            json=payload,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        print(f"ERROR: Local LLM call failed: {e}", file=sys.stderr)
        return None


def call_cloud_llm(messages: List[Dict[str, str]], max_tokens: int = LLAMA_MAX_TOKENS) -> Optional[str]:
    """Appel à API Cloud OpenAI-compatible (DeepSeek, Together, etc.) avec rate limiting"""
    if not CLOUD_API_KEY:
        print("ERROR: CLOUD_API_KEY not set", file=sys.stderr)
        return None

    # Check rate limit
    can_call, current, max_calls = can_make_call()
    if not can_call:
        wait_time = get_wait_time()
        print(f"RATE_LIMIT: {current}/{max_calls} calls/h - waiting {wait_time:.0f}s", file=sys.stderr)
        if wait_time > 60:  # If more than 1 min wait, fallback to local
            print("FALLBACK: Switching to local LLM", file=sys.stderr)
            return call_local_llm(messages, max_tokens)
        time.sleep(wait_time + 1)

    # OpenAI-compatible API format
    payload = {
        "model": CLOUD_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }

    headers = {
        "Authorization": f"Bearer {CLOUD_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        print(f"CLOUD: Calling {CLOUD_API_URL} with model {CLOUD_MODEL}", file=sys.stderr)
        response = requests.post(
            CLOUD_API_URL,
            json=payload,
            headers=headers,
            timeout=120
        )
        response.raise_for_status()

        # Record successful call
        record_call()

        data = response.json()
        # OpenAI-compatible response format
        if "choices" in data:
            return data["choices"][0].get("message", {}).get("content", "")
        elif "reply" in data:  # Some APIs use this
            return data["reply"]
        else:
            print(f"ERROR: Unexpected response format: {data}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"ERROR: Cloud API call failed: {e}", file=sys.stderr)
        # Fallback to local on error
        print("FALLBACK: Switching to local LLM", file=sys.stderr)
        return call_local_llm(messages, max_tokens)


def call_llm(messages: List[Dict[str, str]], max_tokens: int = LLAMA_MAX_TOKENS) -> Optional[str]:
    """Appel LLM avec sélection de backend et fallback automatique"""
    backend = LLM_BACKEND.lower()

    if backend == "cloud" or backend == "minimax":
        return call_cloud_llm(messages, max_tokens)
    elif backend == "local":
        return call_local_llm(messages, max_tokens)
    elif backend == "auto":
        # Try Cloud API first if API key is set and rate limit allows
        if CLOUD_API_KEY:
            can_call, current, max_calls = can_make_call()
            if can_call:
                result = call_cloud_llm(messages, max_tokens)
                if result:
                    return result
        # Fallback to local
        return call_local_llm(messages, max_tokens)
    else:
        print(f"ERROR: Unknown backend: {backend}", file=sys.stderr)
        return call_local_llm(messages, max_tokens)

def execute_tool(tool_call: Dict[str, Any]) -> str:
    """Exécute un outil et retourne le résultat"""
    tool = tool_call.get("tool", "")

    if tool == "read":
        path = tool_call.get("path", "")
        full_path = PROJECT_ROOT / path if not path.startswith("/") else Path(path)
        try:
            if not full_path.exists():
                return f"ERROR: File not found: {path}"
            content = full_path.read_text(encoding="utf-8")
            # Limiter à 10k chars
            if len(content) > 10000:
                content = content[:10000] + "\n... (truncated)"
            return content
        except Exception as e:
            return f"ERROR: {e}"

    elif tool == "edit":
        path = tool_call.get("path", "")
        old = tool_call.get("old", "")
        new = tool_call.get("new", "")
        full_path = PROJECT_ROOT / path if not path.startswith("/") else Path(path)
        try:
            if not full_path.exists():
                return f"ERROR: File not found: {path}"
            content = full_path.read_text(encoding="utf-8")
            if old not in content:
                return f"ERROR: Old text not found in file"
            new_content = content.replace(old, new, 1)
            full_path.write_text(new_content, encoding="utf-8")
            return f"OK: Edited {path}"
        except Exception as e:
            return f"ERROR: {e}"

    elif tool == "bash":
        command = tool_call.get("command", "")
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=300
            )
            output = result.stdout + result.stderr
            # Limiter à 5k chars
            if len(output) > 5000:
                output = output[:5000] + "\n... (truncated)"
            return f"exit_code={result.returncode}\n{output}"
        except subprocess.TimeoutExpired:
            return "ERROR: Command timed out (300s)"
        except Exception as e:
            return f"ERROR: {e}"

    elif tool == "grep":
        pattern = tool_call.get("pattern", "")
        path = tool_call.get("path", ".")
        try:
            # Handle glob patterns: tools/ralph-wiggum/** -> search in tools/ralph-wiggum/
            # ripgrep doesn't support ** in path, only --glob
            search_path = path.rstrip("*").rstrip("/") if "**" in path or path.endswith("*") else path
            if not search_path:
                search_path = "."

            cmd = ["rg", "-n", "--max-count=50", pattern, search_path]
            result = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=60
            )
            output = result.stdout
            if len(output) > 5000:
                output = output[:5000] + "\n... (truncated)"
            return output or "No matches found"
        except Exception as e:
            return f"ERROR: {e}"

    elif tool == "done":
        return f"TASK_COMPLETE: {tool_call.get('result', 'Done')}"

    else:
        return f"ERROR: Unknown tool: {tool}"

def extract_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """Extrait l'appel d'outil JSON de la réponse"""
    # Cherche une ligne JSON avec "tool"
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("{") and '"tool"' in line:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None

def run_agent(task: str, max_iterations: int = 20) -> str:
    """Boucle agentique RLM Light"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task}
    ]

    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1}/{max_iterations} ---", file=sys.stderr)

        # Appel LLM
        response = call_llm(messages)
        if not response:
            return "ERROR: LLM call failed"

        print(f"LLM: {response[:500]}...", file=sys.stderr)

        # Ajoute la réponse à l'historique
        messages.append({"role": "assistant", "content": response})

        # Extrait l'appel d'outil
        tool_call = extract_tool_call(response)

        if not tool_call:
            # Pas d'outil = réponse finale (pas idéal mais on continue)
            print("WARNING: No tool call found, asking for completion", file=sys.stderr)
            messages.append({"role": "user", "content": "Tu dois utiliser un outil. Si tu as terminé, utilise: {\"tool\": \"done\", \"result\": \"<résumé>\"}"})
            continue

        # Exécute l'outil
        tool_result = execute_tool(tool_call)
        print(f"TOOL [{tool_call.get('tool')}]: {tool_result[:200]}...", file=sys.stderr)

        # Vérifie si terminé
        if "TASK_COMPLETE:" in tool_result:
            return tool_result.replace("TASK_COMPLETE: ", "")

        # Ajoute le résultat à l'historique
        messages.append({"role": "user", "content": f"Résultat de l'outil:\n{tool_result}"})

    return "ERROR: Max iterations reached without completion"

def main():
    if len(sys.argv) < 2:
        print("Usage: rlm_light_client.py '<task description>'", file=sys.stderr)
        print("\nExemple: rlm_light_client.py 'Corrige le test auth.spec.ts qui échoue'", file=sys.stderr)
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    print(f"RLM Light Agent - Task: {task}", file=sys.stderr)
    print(f"Backend: {LLM_BACKEND}", file=sys.stderr)
    print(f"Local: {LOCAL_API_URL} ({LOCAL_MODEL})", file=sys.stderr)
    print(f"Cloud: {CLOUD_API_URL} ({CLOUD_MODEL})", file=sys.stderr)

    result = run_agent(task)
    print(f"\n=== RESULT ===\n{result}")

if __name__ == "__main__":
    main()
