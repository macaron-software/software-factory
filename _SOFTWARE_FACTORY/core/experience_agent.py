#!/usr/bin/env python3
"""
Experience Learning Agent - Meta-Brain for Factory Self-Improvement
====================================================================
Based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models"

Analyses global factory experience to:
1. Detect failure patterns (repeated rejects, stuck tasks)
2. Identify gaps in coverage (KISS violations, missing tests)
3. Propose factory improvements (better fractal depth, new patterns)
4. Learn from successes (what works → replicate)

Uses Claude Opus 4.5 for deep reasoning.

Architecture:
    ErrorCapture → TaskStore ← ExperienceAgent → Factory Improvements
                         ↓
                    Adversarial Gate (learns new patterns)

Usage:
    from core.experience_agent import ExperienceAgent
    agent = ExperienceAgent()
    insights = await agent.analyze()
    await agent.apply_improvements(insights)
"""

import json
import sqlite3
import asyncio
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import zlib


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [XP-AGENT] [{level}] {msg}", flush=True)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class InsightType(str, Enum):
    """Types of insights from experience analysis"""
    # Failure patterns
    REPEATED_REJECTION = "repeated_rejection"      # Same adversarial rule hits
    STUCK_TASKS = "stuck_tasks"                    # Tasks in progress too long
    TDD_FAILURES = "tdd_failures"                  # Repeated TDD cycle failures
    DEPLOY_FAILURES = "deploy_failures"            # Production rollbacks
    
    # Coverage gaps
    MISSING_E2E = "missing_e2e"                    # Features without E2E tests
    KISS_VIOLATION = "kiss_violation"              # Over-complex solutions
    FRACTAL_SHALLOW = "fractal_shallow"            # Should decompose more
    FRACTAL_TOO_DEEP = "fractal_too_deep"          # Over-decomposed
    
    # Security/Quality
    SECURITY_PATTERN = "security_pattern"          # New security issue detected
    SLOP_PATTERN = "slop_pattern"                  # AI-generated bad patterns
    
    # Positive patterns
    SUCCESS_PATTERN = "success_pattern"            # What works well


@dataclass
class Insight:
    """An insight from experience analysis"""
    type: InsightType
    severity: str  # "critical", "high", "medium", "low"
    title: str
    description: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    recommendation: str = ""
    affected_projects: List[str] = field(default_factory=list)
    auto_fixable: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "affected_projects": self.affected_projects,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class Improvement:
    """A concrete improvement to apply"""
    target: str  # "adversarial", "fractal", "brain", "wiggum"
    action: str  # "add_pattern", "adjust_threshold", "update_config"
    payload: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    applied: bool = False


# ============================================================================
# EXPERIENCE AGENT
# ============================================================================

class ExperienceAgent:
    """
    Meta-Brain that learns from factory experience.
    
    Runs periodically (cron) or on-demand to:
    1. Query TaskStore for patterns
    2. Analyze with Claude Opus 4.5
    3. Generate improvements
    4. Apply auto-fixable improvements
    5. Create tasks for manual improvements
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path(__file__).parent.parent / "data" / "factory.db"
        self.insights: List[Insight] = []
        self.improvements: List[Improvement] = []
        
    def _get_db(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    # ========================================================================
    # DATA COLLECTION
    # ========================================================================
    
    def collect_failure_stats(self, days: int = 7) -> Dict[str, Any]:
        """Collect failure statistics from last N days"""
        conn = self._get_db()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        stats = {}
        
        # Tasks by status
        cur = conn.execute("""
            SELECT project_id, status, COUNT(*) as count
            FROM tasks
            WHERE created_at > ?
            GROUP BY project_id, status
        """, (cutoff,))
        stats["status_counts"] = [dict(r) for r in cur.fetchall()]
        
        # Stuck tasks (in_progress for > 2 hours)
        stuck_cutoff = (datetime.now() - timedelta(hours=2)).isoformat()
        cur = conn.execute("""
            SELECT id, project_id, domain, description, status, updated_at
            FROM tasks
            WHERE status IN ('tdd_in_progress', 'locked')
            AND updated_at < ?
        """, (stuck_cutoff,))
        stats["stuck_tasks"] = [dict(r) for r in cur.fetchall()]
        
        # High retry tasks (> 3 attempts)
        cur = conn.execute("""
            SELECT id, project_id, domain, description, tdd_attempts, adversarial_attempts, last_error
            FROM tasks
            WHERE tdd_attempts > 3 OR adversarial_attempts > 3
        """)
        stats["high_retry_tasks"] = [dict(r) for r in cur.fetchall()]
        
        # Adversarial rejection patterns
        cur = conn.execute("""
            SELECT task_id, verdict, issues_gz
            FROM attempts
            WHERE stage = 'adversarial' AND verdict = 'rejected'
            AND created_at > ?
            LIMIT 100
        """, (cutoff,))
        
        rejection_reasons = {}
        for row in cur.fetchall():
            if row['issues_gz']:
                try:
                    issues = json.loads(zlib.decompress(row['issues_gz']).decode())
                    for issue in issues:
                        rule = issue.get('rule', 'unknown')
                        rejection_reasons[rule] = rejection_reasons.get(rule, 0) + 1
                except Exception:
                    pass
        stats["rejection_patterns"] = rejection_reasons
        
        # Deploy failures
        cur = conn.execute("""
            SELECT task_id, env, status, created_at
            FROM deployments
            WHERE status IN ('failed', 'rollback')
            AND created_at > ?
        """, (cutoff,))
        stats["deploy_failures"] = [dict(r) for r in cur.fetchall()]
        
        # Decomposed tasks (fractal depth)
        cur = conn.execute("""
            SELECT project_id, depth, COUNT(*) as count
            FROM tasks
            WHERE depth > 0
            GROUP BY project_id, depth
            ORDER BY depth
        """)
        stats["fractal_depth"] = [dict(r) for r in cur.fetchall()]
        
        # Success rate by domain
        cur = conn.execute("""
            SELECT project_id, domain,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                   COUNT(*) as total
            FROM tasks
            WHERE created_at > ?
            GROUP BY project_id, domain
        """, (cutoff,))
        stats["domain_success"] = [dict(r) for r in cur.fetchall()]
        
        conn.close()
        return stats
    
    def collect_adversarial_patterns(self) -> List[Dict]:
        """Get current adversarial patterns from config"""
        from core.adversarial import CORE_REJECT_PATTERNS, CORE_WARNING_PATTERNS, SECURITY_PATTERNS
        
        patterns = []
        for pattern, (rule, points, msg) in CORE_REJECT_PATTERNS.items():
            patterns.append({"pattern": pattern, "rule": rule, "points": points, "type": "reject"})
        for pattern, (rule, points, msg, max_occ) in CORE_WARNING_PATTERNS.items():
            patterns.append({"pattern": pattern, "rule": rule, "points": points, "type": "warning", "max": max_occ})
        for pattern, (rule, points, msg) in SECURITY_PATTERNS.items():
            patterns.append({"pattern": pattern, "rule": rule, "points": points, "type": "security"})
            
        return patterns
    
    def collect_recent_errors(self, limit: int = 50) -> List[Dict]:
        """Collect recent error messages from failed tasks"""
        conn = self._get_db()
        cur = conn.execute("""
            SELECT id, project_id, domain, description, last_error, tdd_attempts
            FROM tasks
            WHERE last_error IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limit,))
        errors = [dict(r) for r in cur.fetchall()]
        conn.close()
        return errors
    
    # ========================================================================
    # ANALYSIS
    # ========================================================================
    
    async def analyze(self, use_llm: bool = True) -> List[Insight]:
        """
        Analyze factory experience and generate insights.
        
        Args:
            use_llm: If True, use Claude Opus for deep analysis
        """
        log("Starting experience analysis...")
        self.insights = []
        
        # Collect data
        stats = self.collect_failure_stats(days=7)
        errors = self.collect_recent_errors(limit=50)
        patterns = self.collect_adversarial_patterns()
        
        log(f"Collected: {len(stats['stuck_tasks'])} stuck, {len(stats['high_retry_tasks'])} high-retry, {len(errors)} errors")
        
        # Fast analysis (rule-based)
        self._analyze_stuck_tasks(stats)
        self._analyze_rejection_patterns(stats)
        self._analyze_fractal_depth(stats)
        self._analyze_domain_success(stats)
        
        # Deep analysis (LLM)
        if use_llm and (stats['high_retry_tasks'] or errors):
            await self._analyze_with_llm(stats, errors, patterns)
        
        log(f"Generated {len(self.insights)} insights")
        return self.insights
    
    def _analyze_stuck_tasks(self, stats: Dict):
        """Detect stuck tasks"""
        stuck = stats.get('stuck_tasks', [])
        if len(stuck) >= 3:
            self.insights.append(Insight(
                type=InsightType.STUCK_TASKS,
                severity="high",
                title=f"{len(stuck)} tasks stuck in progress",
                description="Tasks have been in tdd_in_progress or locked state for > 2 hours. "
                           "This indicates workers may be dead or tasks are too complex.",
                evidence=stuck[:5],
                recommendation="1. Check daemon status\n2. Reset stuck tasks to pending\n3. Consider fractal decomposition",
                affected_projects=list(set(t['project_id'] for t in stuck)),
                auto_fixable=True,
            ))
    
    def _analyze_rejection_patterns(self, stats: Dict):
        """Detect repeated adversarial rejections"""
        patterns = stats.get('rejection_patterns', {})
        for rule, count in patterns.items():
            if count >= 10:
                self.insights.append(Insight(
                    type=InsightType.REPEATED_REJECTION,
                    severity="medium",
                    title=f"Repeated rejection: {rule} ({count} times)",
                    description=f"The adversarial rule '{rule}' is rejecting code frequently. "
                               "Either the LLM keeps making the same mistake, or the rule is too strict.",
                    evidence=[{"rule": rule, "count": count}],
                    recommendation=f"1. Add explicit guidance to Brain prompts about {rule}\n"
                                  f"2. Consider adjusting rule threshold if too strict",
                    auto_fixable=False,
                ))
    
    def _analyze_fractal_depth(self, stats: Dict):
        """Detect fractal depth issues"""
        depths = stats.get('fractal_depth', [])
        
        # Too shallow: many tasks at depth 0 with high retries
        high_retry = stats.get('high_retry_tasks', [])
        shallow_retries = [t for t in high_retry if t.get('tdd_attempts', 0) > 5]
        
        if len(shallow_retries) >= 3:
            self.insights.append(Insight(
                type=InsightType.FRACTAL_SHALLOW,
                severity="medium",
                title="Tasks may need deeper fractal decomposition",
                description=f"{len(shallow_retries)} tasks have > 5 TDD attempts without success. "
                           "These might be too complex and need fractal decomposition.",
                evidence=shallow_retries[:3],
                recommendation="1. Lower fractal.max_files threshold\n"
                              "2. Lower fractal.max_loc threshold\n"
                              "3. Enable automatic decomposition after N failures",
                auto_fixable=False,
            ))
        
        # Too deep: many tasks at depth 3
        deep_tasks = [d for d in depths if d.get('depth', 0) >= 3]
        if deep_tasks:
            total_deep = sum(d.get('count', 0) for d in deep_tasks)
            if total_deep >= 20:
                self.insights.append(Insight(
                    type=InsightType.FRACTAL_TOO_DEEP,
                    severity="low",
                    title="Excessive fractal decomposition",
                    description=f"{total_deep} tasks at depth >= 3. Over-decomposition may indicate "
                               "tasks are being split too aggressively.",
                    evidence=deep_tasks,
                    recommendation="Increase fractal.max_files or max_loc thresholds",
                    auto_fixable=False,
                ))
    
    def _analyze_domain_success(self, stats: Dict):
        """Analyze success rates by domain"""
        domains = stats.get('domain_success', [])
        
        for domain in domains:
            completed = domain.get('completed', 0)
            failed = domain.get('failed', 0)
            total = domain.get('total', 1)
            
            if total >= 10 and failed > completed:
                success_rate = completed / total * 100
                self.insights.append(Insight(
                    type=InsightType.TDD_FAILURES,
                    severity="high",
                    title=f"Low success rate in {domain['project_id']}/{domain['domain']}",
                    description=f"Success rate: {success_rate:.1f}% ({completed}/{total}). "
                               f"This domain has more failures than successes.",
                    evidence=[domain],
                    recommendation=f"1. Review Brain prompts for {domain['domain']} domain\n"
                                  "2. Check domain-specific build/test commands\n"
                                  "3. Consider adding domain-specific adversarial patterns",
                    affected_projects=[domain['project_id']],
                    auto_fixable=False,
                ))
    
    async def _analyze_with_llm(self, stats: Dict, errors: List[Dict], patterns: List[Dict]):
        """Deep analysis using Claude Opus 4.5"""
        log("Running deep LLM analysis with Claude Opus 4.5...")
        
        # Prepare context
        context = {
            "stuck_tasks": stats.get('stuck_tasks', [])[:10],
            "high_retry_tasks": stats.get('high_retry_tasks', [])[:10],
            "rejection_patterns": stats.get('rejection_patterns', {}),
            "recent_errors": errors[:20],
            "current_adversarial_patterns": len(patterns),
            "domain_success": stats.get('domain_success', []),
        }
        
        prompt = f"""You are the Experience Learning Agent for a Software Factory.

Analyze this factory telemetry and identify:
1. FAILURE PATTERNS: What keeps failing and why?
2. MISSING PATTERNS: What adversarial rules should be added?
3. KISS VIOLATIONS: Are solutions over-engineered?
4. GAPS: What's missing (E2E tests, security checks, etc.)?
5. SUCCESS PATTERNS: What's working well?

TELEMETRY:
```json
{json.dumps(context, indent=2, default=str)[:6000]}
```

RESPOND IN STRICT JSON:
{{
  "insights": [
    {{
      "type": "repeated_rejection|stuck_tasks|kiss_violation|missing_e2e|security_pattern|slop_pattern|success_pattern",
      "severity": "critical|high|medium|low",
      "title": "short title",
      "description": "detailed description",
      "recommendation": "concrete action to take",
      "auto_fixable": true/false
    }}
  ],
  "new_adversarial_patterns": [
    {{
      "pattern": "regex pattern",
      "rule": "rule_name",
      "points": 1-5,
      "type": "reject|warning",
      "reason": "why add this pattern"
    }}
  ],
  "config_adjustments": [
    {{
      "target": "fractal|adversarial|brain",
      "key": "config key",
      "current_issue": "what's wrong",
      "suggested_value": "new value"
    }}
  ]
}}
"""

        try:
            # Use claude CLI
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "-p",
                "--model", "claude-opus-4-20250514",
                "--max-turns", "1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=120,
            )
            
            output = stdout.decode()
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{[\s\S]*"insights"[\s\S]*\}', output)
            if json_match:
                result = json.loads(json_match.group())
                
                # Add LLM insights
                for ins in result.get('insights', []):
                    try:
                        insight_type = InsightType(ins.get('type', 'stuck_tasks'))
                    except ValueError:
                        insight_type = InsightType.STUCK_TASKS
                        
                    self.insights.append(Insight(
                        type=insight_type,
                        severity=ins.get('severity', 'medium'),
                        title=ins.get('title', 'LLM Insight'),
                        description=ins.get('description', ''),
                        recommendation=ins.get('recommendation', ''),
                        auto_fixable=ins.get('auto_fixable', False),
                    ))
                
                # Store new patterns for later application
                for pattern in result.get('new_adversarial_patterns', []):
                    self.improvements.append(Improvement(
                        target="adversarial",
                        action="add_pattern",
                        payload=pattern,
                        reason=pattern.get('reason', ''),
                    ))
                
                # Store config adjustments
                for adj in result.get('config_adjustments', []):
                    self.improvements.append(Improvement(
                        target=adj.get('target', 'brain'),
                        action="adjust_config",
                        payload=adj,
                        reason=adj.get('current_issue', ''),
                    ))
                
                log(f"LLM found {len(result.get('insights', []))} insights, "
                    f"{len(result.get('new_adversarial_patterns', []))} new patterns")
            else:
                log("Could not parse LLM JSON response", "WARN")
                
        except asyncio.TimeoutError:
            log("LLM analysis timeout (120s)", "WARN")
        except Exception as e:
            log(f"LLM analysis error: {e}", "ERROR")
    
    # ========================================================================
    # PERSISTENCE - Learning Memory
    # ========================================================================
    
    def persist_insights(self) -> int:
        """Save insights to learnings table for long-term memory"""
        conn = self._get_db()
        count = 0
        
        for insight in self.insights:
            # Check if similar insight already exists (dedup)
            cur = conn.execute("""
                SELECT id FROM learnings 
                WHERE insight_type = ? AND title = ? AND created_at > datetime('now', '-7 days')
            """, (insight.type.value, insight.title))
            
            if cur.fetchone():
                continue  # Skip duplicate
            
            conn.execute("""
                INSERT INTO learnings (insight_type, severity, title, description, recommendation, affected_projects)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                insight.type.value,
                insight.severity,
                insight.title,
                insight.description,
                insight.recommendation,
                json.dumps(insight.affected_projects),
            ))
            count += 1
        
        conn.commit()
        conn.close()
        log(f"Persisted {count} new insights to learnings table")
        return count
    
    def persist_patterns(self) -> int:
        """Save new adversarial patterns to pattern_evolutions table"""
        conn = self._get_db()
        count = 0
        
        for imp in self.improvements:
            if imp.target != "adversarial" or imp.action != "add_pattern":
                continue
            
            payload = imp.payload
            pattern = payload.get('pattern', '')
            
            if not pattern:
                continue
            
            # Check if pattern already exists
            cur = conn.execute("SELECT id FROM pattern_evolutions WHERE pattern = ?", (pattern,))
            if cur.fetchone():
                continue
            
            conn.execute("""
                INSERT INTO pattern_evolutions (pattern, rule, points, pattern_type, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (
                pattern,
                payload.get('rule', 'xp_learned'),
                payload.get('points', 2),
                payload.get('type', 'warning'),
                imp.reason,
            ))
            count += 1
            log(f"Learned new pattern: {payload.get('rule', 'unknown')}")
        
        conn.commit()
        conn.close()
        return count
    
    def get_learned_patterns(self) -> List[Dict]:
        """Get active learned patterns for adversarial gate"""
        conn = self._get_db()
        cur = conn.execute("""
            SELECT pattern, rule, points, pattern_type, reason, hit_count, effectiveness
            FROM pattern_evolutions
            WHERE active = 1
            ORDER BY created_at DESC
        """)
        patterns = [dict(r) for r in cur.fetchall()]
        conn.close()
        return patterns
    
    def measure_impact(self, days: int = 7) -> Dict[str, Any]:
        """Measure ROI of applied improvements"""
        conn = self._get_db()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Success rate before/after improvements
        cur = conn.execute("""
            SELECT 
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                COUNT(*) as total
            FROM tasks
            WHERE created_at > ?
        """, (cutoff,))
        row = cur.fetchone()
        
        recent_stats = {
            "completed": row['completed'] or 0,
            "failed": row['failed'] or 0,
            "total": row['total'] or 1,
            "success_rate": (row['completed'] or 0) / max(row['total'] or 1, 1) * 100,
        }
        
        # Pattern effectiveness
        cur = conn.execute("""
            SELECT rule, hit_count, effectiveness
            FROM pattern_evolutions
            WHERE hit_count > 0
            ORDER BY hit_count DESC
            LIMIT 10
        """)
        pattern_stats = [dict(r) for r in cur.fetchall()]
        
        # Applied vs pending improvements
        cur = conn.execute("""
            SELECT 
                SUM(CASE WHEN applied = 1 THEN 1 ELSE 0 END) as applied,
                SUM(CASE WHEN applied = 0 THEN 1 ELSE 0 END) as pending
            FROM learnings
        """)
        row = cur.fetchone()
        learning_stats = {
            "applied": row['applied'] or 0,
            "pending": row['pending'] or 0,
        }
        
        conn.close()
        
        return {
            "recent_performance": recent_stats,
            "pattern_effectiveness": pattern_stats,
            "learning_progress": learning_stats,
        }
    
    # ========================================================================
    # IMPROVEMENTS
    # ========================================================================
    
    async def apply_auto_fixes(self) -> int:
        """Apply auto-fixable improvements"""
        applied = 0
        
        for insight in self.insights:
            if not insight.auto_fixable:
                continue
            
            if insight.type == InsightType.STUCK_TASKS:
                applied += await self._fix_stuck_tasks(insight)
        
        log(f"Applied {applied} auto-fixes")
        return applied
    
    async def _fix_stuck_tasks(self, insight: Insight) -> int:
        """Reset stuck tasks to pending"""
        conn = self._get_db()
        count = 0
        
        for task in insight.evidence:
            task_id = task.get('id')
            if task_id:
                conn.execute("""
                    UPDATE tasks
                    SET status = 'pending',
                        locked_by = NULL,
                        lock_expires_at = NULL,
                        updated_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), task_id))
                count += 1
                log(f"Reset stuck task: {task_id}")
        
        conn.commit()
        conn.close()
        return count
    
    def generate_report(self) -> str:
        """Generate markdown report of insights"""
        lines = ["# Experience Learning Agent Report", ""]
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        by_severity = {}
        for i in self.insights:
            by_severity[i.severity] = by_severity.get(i.severity, 0) + 1
        
        lines.append("## Summary")
        lines.append(f"- **Total insights**: {len(self.insights)}")
        for sev in ["critical", "high", "medium", "low"]:
            if sev in by_severity:
                lines.append(f"- **{sev.upper()}**: {by_severity[sev]}")
        lines.append("")
        
        # Insights by severity
        for sev in ["critical", "high", "medium", "low"]:
            insights = [i for i in self.insights if i.severity == sev]
            if insights:
                lines.append(f"## {sev.upper()} Insights")
                lines.append("")
                for insight in insights:
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}[sev]
                    lines.append(f"### {icon} {insight.title}")
                    lines.append(f"**Type**: {insight.type.value}")
                    lines.append(f"**Auto-fixable**: {'Yes' if insight.auto_fixable else 'No'}")
                    lines.append("")
                    lines.append(insight.description)
                    lines.append("")
                    if insight.recommendation:
                        lines.append("**Recommendation**:")
                        lines.append(insight.recommendation)
                        lines.append("")
                    if insight.affected_projects:
                        lines.append(f"**Affected projects**: {', '.join(insight.affected_projects)}")
                        lines.append("")
        
        # Improvements
        if self.improvements:
            lines.append("## Suggested Improvements")
            lines.append("")
            for imp in self.improvements:
                lines.append(f"- **{imp.target}**: {imp.action}")
                lines.append(f"  Reason: {imp.reason}")
                if imp.payload:
                    lines.append(f"  Payload: `{json.dumps(imp.payload)[:100]}`")
                lines.append("")
        
        return "\n".join(lines)
    
    def create_improvement_tasks(self) -> List[Dict]:
        """Create tasks for manual improvements"""
        tasks = []
        
        for insight in self.insights:
            if insight.auto_fixable:
                continue
            if insight.severity not in ["critical", "high"]:
                continue
            
            task = {
                "type": "improvement",
                "domain": "factory",
                "description": f"[XP-AGENT] {insight.title}",
                "context": {
                    "insight_type": insight.type.value,
                    "description": insight.description,
                    "recommendation": insight.recommendation,
                    "evidence": insight.evidence,
                },
                "priority": 100 if insight.severity == "critical" else 80,
            }
            tasks.append(task)
        
        return tasks


# ============================================================================
# CLI
# ============================================================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Experience Learning Agent")
    parser.add_argument("--analyze", action="store_true", help="Run analysis")
    parser.add_argument("--apply", action="store_true", help="Apply auto-fixes")
    parser.add_argument("--report", action="store_true", help="Generate report")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM analysis")
    parser.add_argument("--days", type=int, default=7, help="Days of history to analyze")
    
    args = parser.parse_args()
    
    agent = ExperienceAgent()
    
    if args.analyze or args.report:
        insights = await agent.analyze(use_llm=not args.no_llm)
        
        if args.apply:
            await agent.apply_auto_fixes()
        
        if args.report:
            report = agent.generate_report()
            print(report)
        else:
            print(f"\n✅ Found {len(insights)} insights")
            for i in insights[:10]:
                icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}[i.severity]
                print(f"  {icon} [{i.type.value}] {i.title}")
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
