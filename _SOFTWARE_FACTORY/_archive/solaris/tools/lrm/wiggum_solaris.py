#!/usr/bin/env python3
"""
WIGGUM SOLARIS - Agent itératif avec contrôle Adversarial
==========================================================
Dépile les tâches du backlog et génère/corrige le code.

WIGGUM: MiniMax via opencode (itérations rapides)
ADVERSARIAL: Contrôle qualité après chaque itération

Cycle:
1. Lit tâche du backlog
2. Génère code (MiniMax)
3. Vérifie via Adversarial Agent
4. Si SLOP/FAKE détecté → retry avec feedback
5. Si OK → valide via ./solaris validate
6. Complete ou escalate

Usage:
    python3 tools/lrm/wiggum_solaris.py [--daemon]
"""

import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# Configuration
PROJECT_ROOT = Path("/Users/sylvain/_LAPOSTE/_SD3")
LOGS_DIR = PROJECT_ROOT / "logs" / "lrm"
TASKS_DIR = PROJECT_ROOT / "tools" / "lrm" / "tasks"
BACKLOG_FILE = PROJECT_ROOT / "tools" / "lrm" / "backlog_solaris.json"
COMPLETED_FILE = PROJECT_ROOT / "tools" / "lrm" / "completed_solaris.json"

# LLM Config - MiniMax M2.1 via opencode (Coding Plan)
MINIMAX_MODEL = "opencode/minimax-m2.1-free"  # Primary: MiniMax M2.1 Coding Plan

# Fallback: Qwen3 local via llama-cpp (port 8002)
QWEN3_BASE_URL = "http://localhost:8002/v1"
QWEN3_MODEL = "Qwen3-30B-A3B-Instruct-Q4_K_S.gguf"
USE_MINIMAX = True  # Use MiniMax M2.1 via opencode (1000 prompts/5h)

# Retry config
MAX_RETRIES = 10  # Augmenté pour plus d'itérations
RETRY_DELAY = 2

# Fractal config - décomposition automatique si tâche trop large
FRACTAL_ENABLED = True
FRACTAL_THRESHOLDS = {
    "max_components": 3,      # Plus de 3 composants = décomposer
    "max_criteria": 5,        # Plus de 5 critères = décomposer
    "max_files": 5,           # Plus de 5 fichiers = décomposer
    "max_loc_estimate": 200,  # Plus de 200 LOC estimées = décomposer
}
FRACTAL_MAX_DEPTH = 3  # Profondeur max de récursion fractale

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TASKS_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


class AdversarialAgent:
    """
    Agent Adversarial - Détecte SLOP, FAKE, HALLUCINATIONS
    
    Patterns détectés:
    - test.skip / @ts-ignore / TODO / STUB
    - Valeurs hardcodées sans source Figma
    - Mensonges ("100%", "perfect", "no issues")
    - Code incomplet (... / pass / NotImplemented)
    """
    
    SLOP_PATTERNS = [
        # CRITICAL - Contournements (score élevé)
        (r"test\.skip", 10, "test.skip INTERDIT - tests contournés"),
        (r"it\.skip|describe\.skip", 10, "skip INTERDIT - tests contournés"),
        (r"@ts-ignore", 5, "@ts-ignore détecté - types contournés"),
        (r"\.unwrap\(\)", 2, "unwrap() sans gestion d'erreur"),
        (r"type\s*=\s*['\"]any['\"]", 3, "type 'any' détecté"),
        (r"TODO|FIXME|STUB|HACK", 4, "TODO/STUB détecté - code incomplet"),
        (r"NotImplemented|pass\s*$", 5, "NotImplemented/pass - fonction vide"),
        (r"\.\.\.", 3, "... détecté - code tronqué"),
        (r"hardcoded|magic number", 3, "Valeur hardcodée"),
        (r"expect\([^)]+\)\.toBe\(\d+\)", 2, "Valeur de test hardcodée"),
        # OVERCONFIDENT CLAIMS - Affirmations suspectes
        (r"\b(ensures?|guaranteed?|always)\b", 3, "OVERCONFIDENT: 'ensures/guarantees' - affirmation non prouvée"),
        (r"\b(perfect|flawless|100%)\b", 5, "OVERCONFIDENT: 'perfect/100%' - affirmation suspecte"),
        (r"\b(no issues?|no problems?|all good)\b", 4, "OVERCONFIDENT: 'no issues' - affirmation suspecte"),
        (r"\b(complete|comprehensive|exhaustive)\b", 2, "OVERCONFIDENT: 'complete' - à vérifier"),
        (r"\bfully\s+(tested|validated|compliant)\b", 4, "OVERCONFIDENT: 'fully tested' - à prouver"),
        (r"\bsolves?\s+all\b", 4, "OVERCONFIDENT: 'solves all' - affirmation exagérée"),
    ]
    
    HALLUCINATION_PATTERNS = [
        (r"borderRadius:\s*['\"]?\d+px['\"]?", 3, "borderRadius hardcodé - doit venir de Figma"),
        (r"padding:\s*['\"]?\d+px['\"]?", 2, "padding hardcodé - doit venir de Figma"),
        (r"color:\s*#[0-9a-fA-F]{6}", 2, "couleur hardcodée - doit venir de tokens"),
    ]
    
    def __init__(self):
        self.threshold = 5  # Score au-delà duquel on rejette
    
    def analyze(self, code: str, task_description: str = "") -> Tuple[bool, int, list]:
        """
        Analyse le code pour détecter SLOP/FAKE/HALLUCINATIONS
        
        Returns:
            (approved, score, issues)
        """
        issues = []
        total_score = 0
        
        # Check SLOP patterns
        for pattern, score, msg in self.SLOP_PATTERNS:
            matches = re.findall(pattern, code, re.IGNORECASE | re.MULTILINE)
            if matches:
                count = len(matches)
                total_score += score * count
                issues.append(f"SLOP: {msg} ({count}x, +{score * count} pts)")
        
        # Check HALLUCINATION patterns
        for pattern, score, msg in self.HALLUCINATION_PATTERNS:
            matches = re.findall(pattern, code, re.IGNORECASE)
            if matches:
                count = len(matches)
                total_score += score * count
                issues.append(f"HALLUCINATION: {msg} ({count}x, +{score * count} pts)")
        
        # Check for empty or too short response
        if len(code.strip()) < 50:
            total_score += 10
            issues.append("FAKE: Réponse trop courte (<50 chars)")
        
        # Check for error messages
        if code.startswith("Error:"):
            total_score += 10
            issues.append(f"ERROR: {code[:100]}")
        
        approved = total_score < self.threshold
        
        return approved, total_score, issues
    
    def format_feedback(self, issues: list) -> str:
        """Format issues as feedback for retry"""
        if not issues:
            return ""
        
        feedback = "❌ ADVERSARIAL REJECTION:\n"
        for issue in issues:
            feedback += f"  - {issue}\n"
        feedback += "\nCORRECTIONS REQUISES:\n"
        feedback += "  1. Utiliser les vraies valeurs Figma via MCP solaris_variant()\n"
        feedback += "  2. Pas de valeurs hardcodées\n"
        feedback += "  3. Pas de test.skip, TODO, STUB\n"
        feedback += "  4. Code complet et fonctionnel\n"
        
        return feedback


class WiggumSolaris:
    """
    Wiggum Agent - Exécute les tâches du backlog avec mode FRACTAL
    
    Cycle par tâche:
    1. Évalue si tâche trop large → FRACTAL decompose
    2. Charge contexte via MCP
    3. Génère code via MiniMax
    4. Vérifie via Adversarial
    5. Retry si rejeté (max 10x)
    6. Valide via ./solaris validate
    
    Mode FRACTAL (MIT CSAIL arXiv:2512.24601):
    - Si tâche dépasse les seuils → décompose en sous-tâches
    - Chaque sous-tâche est traitée récursivement
    - Profondeur max: 3 niveaux
    - Évite le code partiel en bornant le scope
    """
    
    def __init__(self):
        self.adversarial = AdversarialAgent()
        self.completed = []
        self.failed = []
        self.subtasks_queue = []  # Queue pour sous-tâches fractales
    
    def should_decompose(self, task: dict) -> bool:
        """
        Vérifie si une tâche dépasse les seuils et doit être décomposée.
        Mode FRACTAL - évite le code partiel.
        """
        if not FRACTAL_ENABLED:
            return False
        
        components = task.get("components", [])
        criteria = task.get("acceptance_criteria", [])
        files = task.get("files", [])
        depth = task.get("fractal_depth", 0)
        
        # Ne pas décomposer au-delà de la profondeur max
        if depth >= FRACTAL_MAX_DEPTH:
            return False
        
        # Vérifier les seuils
        if len(components) > FRACTAL_THRESHOLDS["max_components"]:
            log(f"   🔀 FRACTAL: {len(components)} components > {FRACTAL_THRESHOLDS['max_components']} → décomposition")
            return True
        
        if len(criteria) > FRACTAL_THRESHOLDS["max_criteria"]:
            log(f"   🔀 FRACTAL: {len(criteria)} criteria > {FRACTAL_THRESHOLDS['max_criteria']} → décomposition")
            return True
        
        if len(files) > FRACTAL_THRESHOLDS["max_files"]:
            log(f"   🔀 FRACTAL: {len(files)} files > {FRACTAL_THRESHOLDS['max_files']} → décomposition")
            return True
        
        return False
    
    async def decompose_task(self, task: dict) -> list:
        """
        Décompose une tâche trop large en sous-tâches atomiques.
        Utilise le LLM pour une décomposition intelligente.
        """
        task_id = task.get("id", "UNKNOWN")
        description = task.get("description", "")
        components = task.get("components", [])
        criteria = task.get("acceptance_criteria", [])
        depth = task.get("fractal_depth", 0)
        
        log(f"   🔀 FRACTAL DECOMPOSE {task_id} (depth={depth})")
        
        # Prompt pour décomposition
        decompose_prompt = f"""Tu es un expert en décomposition de tâches.

TÂCHE PARENT: {description}
COMPOSANTS: {', '.join(components)}
CRITÈRES: {chr(10).join(f'- {c}' for c in criteria)}

RÈGLES DE DÉCOMPOSITION:
1. Chaque sous-tâche doit être ATOMIQUE (1-3 composants max)
2. Chaque sous-tâche doit être INDÉPENDANTE et déployable seule
3. Chaque sous-tâche doit avoir des critères d'acceptation MESURABLES
4. Maximum 5 sous-tâches

Retourne un JSON valide avec ce format exact:
{{
  "subtasks": [
    {{
      "id": "{task_id}-1",
      "description": "...",
      "components": ["..."],
      "acceptance_criteria": ["..."],
      "files": ["..."]
    }}
  ]
}}

JSON:"""
        
        response = await self.call_wiggum(decompose_prompt)
        
        # Parser le JSON
        try:
            # Extraire le JSON de la réponse
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                subtasks = data.get("subtasks", [])
                
                # Ajouter la profondeur fractale
                for st in subtasks:
                    st["fractal_depth"] = depth + 1
                    st["parent_task"] = task_id
                
                log(f"   ✅ Décomposé en {len(subtasks)} sous-tâches")
                return subtasks
        except json.JSONDecodeError as e:
            log(f"   ⚠️ Erreur parsing JSON: {e}")
        
        # Fallback: décomposition simple par composant
        subtasks = []
        for i, comp in enumerate(components[:5]):
            subtasks.append({
                "id": f"{task_id}-{i+1}",
                "description": f"Implémenter {comp} pour: {description[:100]}",
                "components": [comp],
                "acceptance_criteria": criteria[:2],
                "fractal_depth": depth + 1,
                "parent_task": task_id
            })
        
        log(f"   ⚠️ Fallback: décomposé en {len(subtasks)} sous-tâches par composant")
        return subtasks
    
    async def call_wiggum(self, prompt: str) -> str:
        """Appel MiniMax M2.1 via opencode CLI (Coding Plan) avec fallback Qwen3 local"""
        import aiohttp
        
        if USE_MINIMAX:
            # Try MiniMax M2.1 via opencode first
            try:
                proc = await asyncio.create_subprocess_exec(
                    "opencode", "run", "-m", MINIMAX_MODEL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=prompt.encode()),
                    timeout=3600,  # 1h timeout
                )
                
                if proc.returncode == 0 and stdout:
                    return stdout.decode()[:20000]
                # Fallback to Qwen3 local if MiniMax fails
                log("   MiniMax failed, falling back to Qwen3 local")
            except asyncio.TimeoutError:
                log("   MiniMax timeout, falling back to Qwen3 local")
            except Exception as e:
                log(f"   MiniMax error ({e}), falling back to Qwen3 local")
        
        # Fallback: Qwen3 local via HTTP (llama-cpp)
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": QWEN3_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.3
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{QWEN3_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=3600)  # 1h for complex prompts
                ) as resp:
                    data = await resp.json()
                    
                    if resp.status == 200:
                        choices = data.get("choices", [])
                        if choices:
                            return choices[0].get("message", {}).get("content", "")[:20000]
                        return str(data)[:20000]
                    else:
                        error = data.get("error", {}).get("message", str(data))
                        return f"Error: Qwen3 returned {resp.status} - {error}"
        except asyncio.TimeoutError:
            return "Error: Wiggum timeout (1h)"
        except aiohttp.ClientConnectorError:
            return "Error: Qwen3 server not running (port 8002)"
        except Exception as e:
            return f"Error: {e}"
    
    async def get_figma_context(self, components: list) -> dict:
        """Charge le contexte Figma via MCP pour les composants"""
        context = {}
        
        # Import MCP tools
        sys.path.insert(0, str(PROJECT_ROOT))
        try:
            from mcp_solaris_server import SolarisMCPServer
            server = SolarisMCPServer()
            
            for comp in components[:3]:  # Limit to 3 components
                try:
                    # MCP methods are async
                    data = await server.get_component(comp, summary_only=True)
                    context[comp] = data
                except Exception as e:
                    context[comp] = {"error": str(e)}
        except ImportError:
            log("   Warning: Could not import MCP server")
        
        return context
    
    async def run_validation(self) -> Tuple[bool, str]:
        """Execute ./solaris validate"""
        try:
            result = subprocess.run(
                ["./solaris", "validate"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            success = result.returncode == 0
            output = result.stdout + result.stderr
            
            return success, output[:2000]
        except subprocess.TimeoutExpired:
            return False, "Validation timeout"
        except Exception as e:
            return False, f"Validation error: {e}"
    
    async def process_task(self, task: dict) -> dict:
        """
        Process a single task with adversarial control and FRACTAL mode
        """
        task_id = task.get("id", "UNKNOWN")
        depth = task.get("fractal_depth", 0)
        
        # FRACTAL: vérifier si tâche trop large
        if self.should_decompose(task):
            subtasks = await self.decompose_task(task)
            if subtasks:
                # Traiter les sous-tâches récursivement
                results = []
                for st in subtasks:
                    result = await self.process_task(st)
                    results.append(result)
                
                # Agréger les résultats
                all_completed = all(r.get("status") == "completed" for r in results)
                if all_completed:
                    log(f"   ✅ FRACTAL {task_id}: toutes les sous-tâches complétées")
                    return {"status": "completed", "task_id": task_id, "subtasks": results}
                else:
                    failed_count = sum(1 for r in results if r.get("status") == "failed")
                    log(f"   ⚠️ FRACTAL {task_id}: {failed_count}/{len(results)} sous-tâches échouées")
                    return {"status": "partial", "task_id": task_id, "subtasks": results}
        
        # Tâche atomique - traitement normal
        task_id = task.get("id", "UNKNOWN")
        description = task.get("description", "")
        components = task.get("components", [])
        criteria = task.get("acceptance_criteria", [])
        
        log(f"📋 Processing {task_id}: {description[:50]}...")
        
        # Build compact prompt (avoid timeout)
        prompt = f"""Expert Design System developer task.

TASK: {description}
COMPONENTS: {', '.join(components[:3])}
ACCEPTANCE CRITERIA:
{chr(10).join(f'- {c}' for c in criteria[:5])}

⚠️ RÈGLES STRICTES - VIOLATION = REJET IMMÉDIAT:

INTERDIT (score SLOP élevé):
- test.skip, it.skip, describe.skip → INTERDIT (10 pts)
- @ts-ignore → INTERDIT (5 pts)
- TODO, FIXME, STUB, HACK → INTERDIT (4 pts)
- ... (code tronqué) → INTERDIT (3 pts)
- NotImplemented, pass vide → INTERDIT (5 pts)

OVERCONFIDENT CLAIMS INTERDITES:
- "ensures", "guarantees", "always" → INTERDIT (3 pts)
- "perfect", "flawless", "100%" → INTERDIT (5 pts)
- "no issues", "no problems", "all good" → INTERDIT (4 pts)
- "fully tested", "fully validated" → INTERDIT (4 pts)

OBLIGATOIRE:
- Valeurs Figma via MCP solaris_variant() - pas de valeurs hardcodées
- Code complet et fonctionnel
- Tests réels sans skip

Generate the fix/implementation:"""
        
        # Retry loop with adversarial control
        for attempt in range(1, MAX_RETRIES + 1):
            log(f"   Attempt {attempt}/{MAX_RETRIES}...")
            
            # Generate code
            response = await self.call_wiggum(prompt)
            
            # Adversarial check
            approved, score, issues = self.adversarial.analyze(response, description)
            
            if approved:
                log(f"   ✅ Adversarial APPROVED (score: {score})")
                break
            else:
                log(f"   ❌ Adversarial REJECTED (score: {score})")
                for issue in issues:
                    log(f"      {issue}")
                
                # Add feedback to prompt for retry
                feedback = self.adversarial.format_feedback(issues)
                prompt = f"{feedback}\n\nPROMPT ORIGINAL:\n{prompt}\n\nRÉPONSE PRÉCÉDENTE (REJETÉE):\n{response[:1000]}"
                
                await asyncio.sleep(RETRY_DELAY)
        else:
            # Max retries reached
            log(f"   ⚠️ Max retries reached for {task_id}")
            self.failed.append({
                "task": task,
                "reason": "max_retries",
                "last_issues": issues
            })
            return {"status": "failed", "task_id": task_id, "reason": "max_retries"}
        
        # Run validation
        log("   🔍 Running ./solaris validate...")
        valid, output = await self.run_validation()
        
        if valid:
            log(f"   ✅ Validation PASSED")
            self.completed.append({
                "task": task,
                "response": response[:5000],
                "completed_at": datetime.now().isoformat()
            })
            return {"status": "completed", "task_id": task_id}
        else:
            log(f"   ⚠️ Validation FAILED")
            self.failed.append({
                "task": task,
                "reason": "validation_failed",
                "output": output
            })
            return {"status": "failed", "task_id": task_id, "reason": "validation_failed"}
    
    def load_backlog(self) -> list:
        """Load tasks from backlog"""
        if not BACKLOG_FILE.exists():
            log("⚠️ No backlog found. Run lrm_brain_solaris.py first.")
            return []
        
        with open(BACKLOG_FILE) as f:
            data = json.load(f)
        
        return data.get("tasks", [])
    
    def save_completed(self):
        """Save completed and failed tasks"""
        data = {
            "completed": self.completed,
            "failed": self.failed,
            "updated_at": datetime.now().isoformat()
        }
        
        with open(COMPLETED_FILE, "w") as f:
            json.dump(data, f, indent=2)
    
    async def run(self, daemon: bool = False):
        """
        Run Wiggum agent
        
        Args:
            daemon: If True, run continuously watching for new tasks
        """
        log("=" * 60)
        log("🔧 WIGGUM SOLARIS - Starting...")
        log("=" * 60)
        
        while True:
            tasks = self.load_backlog()
            
            if not tasks:
                if daemon:
                    log("💤 No tasks. Sleeping 30s...")
                    await asyncio.sleep(30)
                    continue
                else:
                    log("✅ No tasks to process")
                    break
            
            # Filter out already completed tasks
            completed_ids = {t["task"]["id"] for t in self.completed}
            pending = [t for t in tasks if t.get("id") not in completed_ids]
            
            if not pending:
                if daemon:
                    log("💤 All tasks complete. Sleeping 30s...")
                    await asyncio.sleep(30)
                    continue
                else:
                    log("✅ All tasks completed")
                    break
            
            log(f"📋 {len(pending)} tasks pending")
            
            # Process tasks
            for task in pending:
                result = await self.process_task(task)
                self.save_completed()
                
                if result["status"] == "failed":
                    log(f"   Task {result['task_id']} failed, continuing...")
            
            if not daemon:
                break
        
        # Final summary
        log("=" * 60)
        log("📊 WIGGUM SUMMARY")
        log(f"   Completed: {len(self.completed)}")
        log(f"   Failed: {len(self.failed)}")
        log("=" * 60)


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Wiggum Solaris Agent")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    args = parser.parse_args()
    
    wiggum = WiggumSolaris()
    await wiggum.run(daemon=args.daemon)


if __name__ == "__main__":
    asyncio.run(main())
