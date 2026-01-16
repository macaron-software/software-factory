#!/usr/bin/env python3
"""
LRM BRAIN SOLARIS - Recursive Language Model pour Design System
================================================================
Architecture MIT CSAIL arXiv:2512.24601

BRAIN: Claude Opus 4.5 headless (analyse lourde, vision, LEAN)
WIGGUM: MiniMax via opencode (itérations code)
ADVERSARIAL: Contrôle qualité (0 fake, 0 slop, 0 hallucination)

Usage:
    python3 tools/lrm/lrm_brain_solaris.py

MCP Tools disponibles:
    - solaris_component: Détails composant Figma
    - solaris_variant: Styles exacts d'un variant
    - solaris_wcag: Pattern WCAG accessibility
    - solaris_knowledge: Query knowledge base
    - solaris_validation: Statut validation
    - solaris_grep: Recherche CSS/HTML
    - solaris_stats: Statistiques globales
    - solaris_list_components: Liste composants
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Configuration
PROJECT_ROOT = Path("/Users/sylvain/_LAPOSTE/_SD3")
LOGS_DIR = PROJECT_ROOT / "logs" / "lrm"
TASKS_DIR = PROJECT_ROOT / "tools" / "lrm" / "tasks"
BACKLOG_FILE = PROJECT_ROOT / "tools" / "lrm" / "backlog_solaris.json"

# LLM Config
BRAIN_MODEL = "claude-opus-4-5-20251101"  # Claude Opus 4.5 headless
WIGGUM_MODEL = "opencode/minimax-m2.1-free"  # MiniMax gratuit

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TASKS_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


class SolarisMCPTools:
    """Interface to Solaris MCP tools via Python"""
    
    def __init__(self):
        self.mcp_server = PROJECT_ROOT / "mcp_solaris_server.py"
    
    async def _call_mcp(self, method: str, params: dict) -> dict:
        """Call MCP server directly via Python import"""
        try:
            # Import the MCP server module
            sys.path.insert(0, str(PROJECT_ROOT))
            from mcp_solaris_server import SolarisMCPServer
            
            server = SolarisMCPServer()
            
            # Route to appropriate method - ALL methods are async
            if method == "solaris_stats":
                return await server.get_stats()
            elif method == "solaris_component":
                return await server.get_component(params.get("component"), params.get("summary_only", True))
            elif method == "solaris_variant":
                return await server.get_variant(params.get("component"), params.get("properties"), params.get("node_id"))
            elif method == "solaris_wcag":
                return await server.get_wcag_pattern(params.get("pattern"))
            elif method == "solaris_validation":
                return await server.get_validation(params.get("component"))
            elif method == "solaris_grep":
                return await server.grep_generated(params.get("pattern"), params.get("file_type", "css"))
            elif method == "solaris_list_components":
                return await server.list_components()
            elif method == "solaris_knowledge":
                return await server.get_knowledge(params.get("category"), params.get("topic"))
            else:
                return {"error": f"Unknown method: {method}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def stats(self) -> dict:
        return await self._call_mcp("solaris_stats", {})
    
    async def component(self, name: str, summary_only: bool = True) -> dict:
        return await self._call_mcp("solaris_component", {"component": name, "summary_only": summary_only})
    
    async def variant(self, component: str, properties: dict = None, node_id: str = None) -> dict:
        return await self._call_mcp("solaris_variant", {"component": component, "properties": properties, "node_id": node_id})
    
    async def wcag(self, pattern: str) -> dict:
        return await self._call_mcp("solaris_wcag", {"pattern": pattern})
    
    async def validation(self, component: str = None) -> dict:
        return await self._call_mcp("solaris_validation", {"component": component})
    
    async def grep(self, pattern: str, file_type: str = "css") -> dict:
        return await self._call_mcp("solaris_grep", {"pattern": pattern, "file_type": file_type})
    
    async def list_components(self) -> dict:
        return await self._call_mcp("solaris_list_components", {})
    
    async def knowledge(self, category: str, topic: str = None) -> dict:
        return await self._call_mcp("solaris_knowledge", {"category": category, "topic": topic})


class LRMBrain:
    """
    LRM Brain - Root Language Model
    
    Utilise Claude Opus 4.5 headless pour:
    - Analyse VISION (structure projet, patterns)
    - Analyse LEAN (dépendances, gaps)
    - Génération de tâches pour les Wiggums
    """
    
    def __init__(self):
        self.mcp = SolarisMCPTools()
        self.depth = 0
        self.max_depth = 3
    
    async def call_brain(self, prompt: str, context: dict = None) -> str:
        """
        Appel Claude Opus 4.5 headless (BRAIN)
        """
        full_prompt = prompt
        if context:
            full_prompt = f"CONTEXT:\n{json.dumps(context, indent=2)}\n\nTASK:\n{prompt}"
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "-p",
                "--model", BRAIN_MODEL,
                "--max-turns", "10",  # Increased for complex analysis
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=full_prompt.encode()),
                timeout=300,
            )
            
            if proc.returncode == 0:
                return stdout.decode()[:30000]
            else:
                return f"Error: {stderr.decode()[:500]}"
        except asyncio.TimeoutError:
            return "Error: Brain timeout (5min)"
        except Exception as e:
            return f"Error: {e}"
    
    async def call_wiggum(self, prompt: str) -> str:
        """
        Appel MiniMax via opencode (WIGGUM)
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "opencode",
                "run",
                "-m", WIGGUM_MODEL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=180,
            )
            
            if proc.returncode == 0 and stdout:
                return stdout.decode()[:20000]
            else:
                return f"Error: MiniMax returned {proc.returncode}"
        except asyncio.TimeoutError:
            return "Error: Wiggum timeout (3min)"
        except Exception as e:
            return f"Error: {e}"
    
    async def analyze_vision(self) -> dict:
        """
        VISION Analysis - Structure et état du projet
        """
        log("🔍 VISION: Analyzing project structure...")
        
        # Get stats from MCP
        stats = await self.mcp.stats()
        validation = await self.mcp.validation()
        components = await self.mcp.list_components()
        
        context = {
            "stats": stats,
            "validation_summary": {
                "total": validation.get("total", 0),
                "passed": validation.get("passed", 0),
                "pass_rate": validation.get("passRate", "0%")
            },
            "component_count": len(components.get("components", [])) if isinstance(components, dict) else 0
        }
        
        prompt = """Analyse VISION du Design System Solaris (La Poste).

Données actuelles:
- Stats: {stats}
- Validation: {validation}
- Composants: {components}

Identifie:
1. Points forts du système
2. Gaps critiques (composants manquants, validation <100%)
3. Problèmes d'accessibilité potentiels
4. Opportunités d'amélioration

Réponds en JSON avec:
{{
  "strengths": ["..."],
  "critical_gaps": ["..."],
  "a11y_issues": ["..."],
  "improvements": ["..."]
}}""".format(
            stats=json.dumps(stats, indent=2),
            validation=json.dumps(context["validation_summary"], indent=2),
            components=len(components.get("components", [])) if isinstance(components, dict) else 0
        )
        
        response = await self.call_brain(prompt)
        log(f"   VISION response: {len(response)} chars")
        
        return {"raw": response, "context": context}
    
    async def analyze_lean(self, vision_result: dict) -> dict:
        """
        LEAN Analysis - Dépendances et priorités
        """
        log("📊 LEAN: Analyzing dependencies and priorities...")
        
        # Get WCAG patterns for a11y analysis
        wcag_accordion = await self.mcp.wcag("accordion")
        wcag_button = await self.mcp.wcag("button")
        
        prompt = """Analyse LEAN du Design System Solaris.

Résultat VISION précédent:
{vision}

Patterns WCAG disponibles:
- Accordion: {wcag_accordion}
- Button: {wcag_button}

Génère un backlog priorisé de tâches. Pour chaque tâche:
1. ID unique (SOLAR-001, SOLAR-002, ...)
2. Type: fix | feature | refactor | test
3. Priority: 1-10 (10 = critique)
4. Description claire
5. Composants impactés
6. Critères d'acceptation

Réponds en JSON:
{{
  "tasks": [
    {{
      "id": "SOLAR-001",
      "type": "fix",
      "priority": 10,
      "description": "...",
      "components": ["button", "accordion"],
      "acceptance_criteria": ["..."]
    }}
  ]
}}""".format(
            vision=vision_result.get("raw", ""),
            wcag_accordion=json.dumps(wcag_accordion, indent=2)[:1000],
            wcag_button=json.dumps(wcag_button, indent=2)[:1000]
        )
        
        response = await self.call_brain(prompt)
        log(f"   LEAN response: {len(response)} chars")
        
        return {"raw": response}
    
    async def generate_backlog(self, lean_result: dict) -> list:
        """
        Génère le backlog final pour les Wiggums
        """
        log("📝 Generating backlog...")
        
        # Parse LEAN response to extract tasks
        raw = lean_result.get("raw", "")
        
        # Try to extract JSON from response
        tasks = []
        try:
            # Find JSON in response
            import re
            json_match = re.search(r'\{[\s\S]*"tasks"[\s\S]*\}', raw)
            if json_match:
                data = json.loads(json_match.group())
                tasks = data.get("tasks", [])
        except json.JSONDecodeError:
            log("   Warning: Could not parse JSON, using fallback")
            # Fallback: create a default task
            tasks = [{
                "id": "SOLAR-001",
                "type": "audit",
                "priority": 10,
                "description": "Full validation audit",
                "components": ["all"],
                "acceptance_criteria": ["100% validation pass"]
            }]
        
        # Save backlog
        backlog = {
            "generated_at": datetime.now().isoformat(),
            "brain_model": BRAIN_MODEL,
            "tasks": tasks
        }
        
        with open(BACKLOG_FILE, "w") as f:
            json.dump(backlog, f, indent=2)
        
        log(f"   Backlog saved: {len(tasks)} tasks")
        return tasks
    
    async def run(self) -> dict:
        """
        Run full LRM Brain pipeline
        """
        log("=" * 60)
        log("🧠 LRM BRAIN SOLARIS - Starting...")
        log("=" * 60)
        
        start = datetime.now()
        
        # Step 1: VISION
        vision = await self.analyze_vision()
        
        # Step 2: LEAN
        lean = await self.analyze_lean(vision)
        
        # Step 3: Generate backlog
        tasks = await self.generate_backlog(lean)
        
        elapsed = (datetime.now() - start).total_seconds()
        
        log("=" * 60)
        log(f"✅ LRM BRAIN complete in {elapsed:.1f}s")
        log(f"   Generated {len(tasks)} tasks")
        log(f"   Backlog: {BACKLOG_FILE}")
        log("=" * 60)
        
        return {
            "vision": vision,
            "lean": lean,
            "tasks": tasks,
            "elapsed": elapsed
        }


async def main():
    brain = LRMBrain()
    result = await brain.run()
    
    # Print summary
    print("\n" + "=" * 60)
    print("BACKLOG SOLARIS")
    print("=" * 60)
    for task in result.get("tasks", []):
        print(f"  [{task.get('id')}] {task.get('type').upper():8} P{task.get('priority'):02d} - {task.get('description')[:50]}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
