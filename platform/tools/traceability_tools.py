"""Traceability Tools — Agent tools for migration traceability.

Tools:
- legacy_scan: scan workspace for legacy items, create inventory with UUIDs
- traceability_link: create link between traceable items
- traceability_coverage: coverage analysis (% covered, orphans)
- traceability_validate: judge tool — pass/fail + gap list
"""
# Ref: feat-annotate

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)

# File extensions to scan per legacy technology
_SCAN_EXTENSIONS = {
    "java": {".java"},
    "sql": {".sql", ".ddl"},
    "xml": {".xml", ".xsd", ".wsdl"},
    "properties": {".properties", ".yml", ".yaml", ".json"},
    "python": {".py"},
    "javascript": {".js", ".ts", ".jsx", ".tsx"},
    "csharp": {".cs"},
    "php": {".php"},
}

# Regex patterns for extracting legacy items from code
_JAVA_PATTERNS = {
    "class": re.compile(r"(?:public\s+|abstract\s+|final\s+)*class\s+(\w+)"),
    "method": re.compile(r"(?:public|private|protected)\s+\w+(?:<[^>]+>)?\s+(\w+)\s*\("),
    "endpoint": re.compile(r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)'),
    "entity": re.compile(r"@Entity|@Table\s*\(\s*name\s*=\s*\"(\w+)\""),
    "service": re.compile(r"@Service|@Component|@Repository"),
    "controller": re.compile(r"@Controller|@RestController"),
}

_SQL_PATTERNS = {
    "table": re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?(\w+)[`\"]?", re.IGNORECASE),
    "column": re.compile(r"^\s+[`\"]?(\w+)[`\"]?\s+(VARCHAR|INT|TEXT|BOOLEAN|DATE|TIMESTAMP|DECIMAL|FLOAT|BIGINT|SERIAL|UUID)", re.IGNORECASE | re.MULTILINE),
    "fk": re.compile(r"FOREIGN\s+KEY\s*\([`\"]?(\w+)[`\"]?\)\s*REFERENCES\s+[`\"]?(\w+)[`\"]?", re.IGNORECASE),
    "pk": re.compile(r"PRIMARY\s+KEY\s*\(([^)]+)\)", re.IGNORECASE),
    "index": re.compile(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?(\w+)[`\"]?", re.IGNORECASE),
    "trigger": re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+[`\"]?(\w+)[`\"]?", re.IGNORECASE),
    "view": re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+[`\"]?(\w+)[`\"]?", re.IGNORECASE),
    "procedure": re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:PROCEDURE|FUNCTION)\s+[`\"]?(\w+)[`\"]?", re.IGNORECASE),
}

_XML_PATTERNS = {
    "workflow": re.compile(r'<workflow[^>]*name\s*=\s*"([^"]+)"', re.IGNORECASE),
    "trigger": re.compile(r'<trigger[^>]*name\s*=\s*"([^"]+)"', re.IGNORECASE),
    "rule": re.compile(r'<rule[^>]*name\s*=\s*"([^"]+)"', re.IGNORECASE),
    "config": re.compile(r'<bean[^>]*id\s*=\s*"([^"]+)"', re.IGNORECASE),
}


class LegacyScanTool(BaseTool):
    name = "legacy_scan"
    description = (
        "Scan project workspace for legacy items (tables, columns, FK, PK, triggers, "
        "rules, workflows, Java classes, methods, endpoints). Creates UUID inventory. "
        "Args: path (workspace path), project_id (project identifier), "
        "file_types (optional: java,sql,xml,properties — default: auto-detect)"
    )
    category = "traceability"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..traceability.migration_store import create_legacy_item

        path = params.get("path", "")
        project_id = params.get("project_id", "")
        file_types = params.get("file_types", "")

        if not path or not project_id:
            return "Error: path and project_id required"

        workspace = Path(path)
        if not workspace.exists():
            return f"Error: path {path} not found"

        # Determine which file types to scan
        if file_types:
            scan_types = set(file_types.split(","))
        else:
            scan_types = set()
            for f in workspace.rglob("*"):
                if f.is_file():
                    for ftype, exts in _SCAN_EXTENSIONS.items():
                        if f.suffix.lower() in exts:
                            scan_types.add(ftype)

        items_created = []
        files_scanned = 0

        for f in sorted(workspace.rglob("*")):
            if not f.is_file() or f.suffix.lower() == ".pyc":
                continue
            if any(p in str(f) for p in ["node_modules", "__pycache__", ".git", "dist", "build"]):
                continue

            suffix = f.suffix.lower()
            rel_path = str(f.relative_to(workspace))

            try:
                content = f.read_text(errors="replace")
            except Exception:
                continue

            files_scanned += 1

            # SQL files
            if suffix in {".sql", ".ddl"} and ("sql" in scan_types or not file_types):
                items_created.extend(
                    _scan_sql(content, project_id, rel_path)
                )

            # Java files
            elif suffix == ".java" and ("java" in scan_types or not file_types):
                items_created.extend(
                    _scan_java(content, project_id, rel_path)
                )

            # XML files
            elif suffix in {".xml", ".xsd"} and ("xml" in scan_types or not file_types):
                items_created.extend(
                    _scan_xml(content, project_id, rel_path)
                )

            # TypeScript/JavaScript files
            elif suffix in {".ts", ".tsx", ".js", ".jsx"} and ("javascript" in scan_types or not file_types):
                items_created.extend(
                    _scan_typescript(content, project_id, rel_path)
                )

        summary = {}
        for item in items_created:
            summary[item["type"]] = summary.get(item["type"], 0) + 1

        return json.dumps({
            "files_scanned": files_scanned,
            "items_created": len(items_created),
            "by_type": summary,
            "items": items_created[:50],  # first 50 for display
            "message": f"Scanned {files_scanned} files, created {len(items_created)} legacy items with UUIDs",
        }, ensure_ascii=False)


class TraceabilityLinkTool(BaseTool):
    name = "traceability_link"
    description = (
        "Create a traceability link between two items. "
        "Args: source_id, source_type (legacy_item|feature|story|code|test|persona), "
        "target_id, target_type, link_type (migrates_from|implements|tests|covers|maps_to|replaces|depends_on)"
    )
    category = "traceability"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..traceability.migration_store import create_link

        required = ["source_id", "source_type", "target_id", "target_type", "link_type"]
        missing = [k for k in required if not params.get(k)]
        if missing:
            return f"Error: missing required params: {', '.join(missing)}"

        link_id = create_link(
            source_id=params["source_id"],
            source_type=params["source_type"],
            target_id=params["target_id"],
            target_type=params["target_type"],
            link_type=params["link_type"],
            coverage_pct=int(params.get("coverage_pct", 0)),
            notes=params.get("notes", ""),
        )
        return json.dumps({
            "link_id": link_id,
            "message": f"Link created: {params['source_id']} --[{params['link_type']}]--> {params['target_id']}",
        })


class TraceabilityCoverageTool(BaseTool):
    name = "traceability_coverage"
    description = (
        "Run traceability coverage analysis for a project. Returns % covered per type "
        "and lists orphan items (legacy items with no story, stories with no test). "
        "Args: project_id"
    )
    category = "traceability"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..traceability.migration_store import (
            count_legacy_items,
            coverage_report,
            orphan_report,
        )

        project_id = params.get("project_id", "")
        if not project_id:
            return "Error: project_id required"

        counts = count_legacy_items(project_id)
        coverage = coverage_report(project_id)
        orphans = orphan_report(project_id)

        return json.dumps({
            "inventory": counts,
            "coverage": coverage,
            "orphans": {
                "legacy_no_story": orphans["legacy_orphan_count"],
                "stories_no_test": orphans["story_no_test_count"],
                "stories_no_code": orphans["story_no_code_count"],
                "details": {
                    "legacy_orphans": orphans["legacy_no_story"][:20],
                    "untested_stories": orphans["stories_no_test"][:20],
                    "unimplemented_stories": orphans["stories_no_code"][:20],
                },
            },
        }, ensure_ascii=False, default=str)


class TraceabilityValidateTool(BaseTool):
    name = "traceability_validate"
    description = (
        "Judge tool: validates 100% traceability for a migration project. "
        "Returns PASS/FAIL with detailed gap list. "
        "Args: project_id, strict (bool, default true — require 100% coverage)"
    )
    category = "traceability"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..traceability.migration_store import (
            coverage_report,
            orphan_report,
            traceability_matrix,
        )

        project_id = params.get("project_id", "")
        if not project_id:
            return "Error: project_id required"
        strict = params.get("strict", True)

        coverage = coverage_report(project_id)
        orphans = orphan_report(project_id)
        matrix = traceability_matrix(project_id)

        overall = coverage.get("_overall", {})
        overall_pct = overall.get("pct", 0)
        threshold = 100 if strict else 80

        # Count fully traced items
        fully_traced = sum(1 for m in matrix if m["fully_traced"])
        total_items = len(matrix)
        trace_pct = round(100 * fully_traced / total_items) if total_items > 0 else 0

        gaps = []
        for m in matrix:
            if not m["fully_traced"]:
                missing = []
                if not m["stories"]:
                    missing.append("no story/feature link")
                if not m["code"]:
                    missing.append("no code link")
                if not m["tests"]:
                    missing.append("no test link")
                gaps.append({
                    "legacy_id": m["legacy_id"],
                    "type": m["type"],
                    "name": m["name"],
                    "missing": missing,
                })

        passed = overall_pct >= threshold and trace_pct >= threshold
        verdict = "PASS" if passed else "FAIL"

        return json.dumps({
            "verdict": verdict,
            "coverage_pct": overall_pct,
            "full_trace_pct": trace_pct,
            "threshold": threshold,
            "total_legacy_items": total_items,
            "fully_traced": fully_traced,
            "orphan_summary": {
                "legacy_no_story": orphans["legacy_orphan_count"],
                "stories_no_test": orphans["story_no_test_count"],
                "stories_no_code": orphans["story_no_code_count"],
            },
            "gaps": gaps[:30],  # first 30 gaps
            "message": (
                f"{verdict}: {trace_pct}% fully traced ({fully_traced}/{total_items}), "
                f"coverage {overall_pct}% (threshold: {threshold}%)"
            ),
        }, ensure_ascii=False, default=str)


# ── Scanning helpers ──

def _scan_sql(content: str, project_id: str, rel_path: str) -> list[dict]:
    from ..traceability.migration_store import create_legacy_item

    items = []
    current_table = None

    for ptype, regex in _SQL_PATTERNS.items():
        for match in regex.finditer(content):
            line = content[:match.start()].count("\n") + 1
            name = match.group(1) if match.lastindex else match.group(0)

            if ptype == "table":
                current_table = name

            if ptype == "fk":
                col_name = match.group(1)
                ref_table = match.group(2)
                name = f"{col_name} → {ref_table}"

            if ptype == "pk":
                name = match.group(1).strip()

            meta = {"source_pattern": ptype}
            if ptype in ("column", "fk", "pk") and current_table:
                meta["table"] = current_table

            parent = ""
            if ptype in ("column", "fk", "pk", "index") and current_table:
                parent = current_table

            item_id = create_legacy_item(
                project_id=project_id,
                item_type=ptype,
                name=name.strip(),
                parent_id=parent,
                description=f"Extracted from {rel_path}:{line}",
                metadata=meta,
                source_file=rel_path,
                source_line=line,
            )
            items.append({"id": item_id, "type": ptype, "name": name.strip()})

    return items


def _scan_java(content: str, project_id: str, rel_path: str) -> list[dict]:
    from ..traceability.migration_store import create_legacy_item

    items = []
    current_class = None

    # Detect type from annotations
    is_entity = bool(re.search(r"@Entity|@Table", content))
    is_service = bool(re.search(r"@Service|@Component|@Repository", content))
    is_controller = bool(re.search(r"@Controller|@RestController", content))

    for match in _JAVA_PATTERNS["class"].finditer(content):
        name = match.group(1)
        current_class = name
        line = content[:match.start()].count("\n") + 1
        itype = "entity" if is_entity else "service" if is_service else "controller" if is_controller else "class"

        item_id = create_legacy_item(
            project_id=project_id,
            item_type=itype,
            name=name,
            description=f"Java {itype} from {rel_path}:{line}",
            metadata={"annotations": _extract_annotations(content, match.start())},
            source_file=rel_path,
            source_line=line,
        )
        items.append({"id": item_id, "type": itype, "name": name})

    for match in _JAVA_PATTERNS["method"].finditer(content):
        name = match.group(1)
        if name in ("if", "for", "while", "switch", "catch"):
            continue
        line = content[:match.start()].count("\n") + 1
        item_id = create_legacy_item(
            project_id=project_id,
            item_type="method",
            name=name,
            parent_id=current_class or "",
            description=f"Method in {current_class or 'unknown'} from {rel_path}:{line}",
            source_file=rel_path,
            source_line=line,
        )
        items.append({"id": item_id, "type": "method", "name": name})

    for match in _JAVA_PATTERNS["endpoint"].finditer(content):
        path = match.group(1)
        line = content[:match.start()].count("\n") + 1
        item_id = create_legacy_item(
            project_id=project_id,
            item_type="endpoint",
            name=path,
            parent_id=current_class or "",
            description=f"REST endpoint from {rel_path}:{line}",
            metadata={"http_method": _extract_http_method(content, match.start())},
            source_file=rel_path,
            source_line=line,
        )
        items.append({"id": item_id, "type": "endpoint", "name": path})

    return items


def _scan_xml(content: str, project_id: str, rel_path: str) -> list[dict]:
    from ..traceability.migration_store import create_legacy_item

    items = []
    for ptype, regex in _XML_PATTERNS.items():
        for match in regex.finditer(content):
            name = match.group(1)
            line = content[:match.start()].count("\n") + 1
            item_id = create_legacy_item(
                project_id=project_id,
                item_type=ptype,
                name=name,
                description=f"XML {ptype} from {rel_path}:{line}",
                source_file=rel_path,
                source_line=line,
            )
            items.append({"id": item_id, "type": ptype, "name": name})
    return items


def _scan_typescript(content: str, project_id: str, rel_path: str) -> list[dict]:
    from ..traceability.migration_store import create_legacy_item

    items = []
    # Components, classes, interfaces
    for match in re.finditer(r"(?:export\s+)?(?:class|interface|type)\s+(\w+)", content):
        name = match.group(1)
        line = content[:match.start()].count("\n") + 1
        itype = "class" if "class" in content[match.start():match.start()+30] else "dto"
        item_id = create_legacy_item(
            project_id=project_id,
            item_type=itype,
            name=name,
            description=f"TypeScript {itype} from {rel_path}:{line}",
            source_file=rel_path,
            source_line=line,
        )
        items.append({"id": item_id, "type": itype, "name": name})

    # Functions/methods
    for match in re.finditer(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)", content):
        name = match.group(1)
        line = content[:match.start()].count("\n") + 1
        item_id = create_legacy_item(
            project_id=project_id,
            item_type="function",
            name=name,
            description=f"Function from {rel_path}:{line}",
            source_file=rel_path,
            source_line=line,
        )
        items.append({"id": item_id, "type": "function", "name": name})

    return items


def _extract_annotations(content: str, class_pos: int) -> list[str]:
    """Extract Java annotations before a class declaration."""
    preceding = content[max(0, class_pos - 500):class_pos]
    return re.findall(r"@(\w+)", preceding)


def _extract_http_method(content: str, mapping_pos: int) -> str:
    """Extract HTTP method from mapping annotation."""
    preceding = content[max(0, mapping_pos - 50):mapping_pos + 50]
    for method in ("Get", "Post", "Put", "Delete", "Patch"):
        if f"@{method}Mapping" in preceding:
            return method.upper()
    return "GET"


def register_traceability_tools(registry):
    """Register all traceability tools."""
    registry.register(LegacyScanTool())
    registry.register(TraceabilityLinkTool())
    registry.register(TraceabilityCoverageTool())
    registry.register(TraceabilityValidateTool())
