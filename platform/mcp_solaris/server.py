#!/usr/bin/env python3
"""
Solaris Design System — MCP Server (stdio JSON-RPC)
====================================================
Managed by MCPManager as a subprocess.  Exposes Figma components,
WCAG patterns, knowledge base, and validation reports.

Data locations (resolved at startup):
  SOLARIS_FIGMA_DIR  — 41 Figma JSON exports (*-all-depth10.json)
  SOLARIS_KNOWLEDGE_DIR — bundled knowledge base (shipped with platform)
  SOLARIS_REPORTS_DIR — validation reports (optional)
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROTOCOL_VERSION = "2024-11-05"

# ── Data paths ───────────────────────────────────────────────────
# Knowledge ships with the package; Figma data is external.
_pkg = Path(__file__).parent
KNOWLEDGE_DIR = Path(os.environ.get(
    "SOLARIS_KNOWLEDGE_DIR",
    str(_pkg / "knowledge"),
))
FIGMA_DATA_DIR = Path(os.environ.get(
    "SOLARIS_FIGMA_DIR",
    "/app/data/solaris/figma-data",
))
GENERATED_PAGES_DIR = Path(os.environ.get(
    "SOLARIS_PAGES_DIR",
    "/app/data/solaris/generated-pages",
))
STYLES_DIR = Path(os.environ.get(
    "SOLARIS_STYLES_DIR",
    "/app/data/solaris/styles",
))
REPORTS_DIR = Path(os.environ.get(
    "SOLARIS_REPORTS_DIR",
    "/app/data/solaris/reports",
))


class SolarisMCPServer:
    def __init__(self):
        self.components_cache: Dict[str, Any] = {}
        self.knowledge_cache: Dict[str, Any] = {}

    # ── Figma helpers ────────────────────────────────────────────

    def _load_figma_data(self, component_name: str) -> Optional[Dict]:
        if component_name in self.components_cache:
            return self.components_cache[component_name]
        for pattern in [
            f"{component_name}-all-depth10.json",
            f"{component_name.lower()}-all-depth10.json",
            f"{component_name.replace(' ', '-').lower()}-all-depth10.json",
        ]:
            fp = FIGMA_DATA_DIR / pattern
            if fp.exists():
                with open(fp) as f:
                    data = json.load(f)
                self.components_cache[component_name] = data
                return data
        return None

    def _load_knowledge(self, category: str, name: str) -> Optional[Dict]:
        key = f"{category}/{name}"
        if key in self.knowledge_cache:
            return self.knowledge_cache[key]
        fp = KNOWLEDGE_DIR / category / f"{name}.json"
        if fp.exists():
            with open(fp) as f:
                data = json.load(f)
            self.knowledge_cache[key] = data
            return data
        return None

    @staticmethod
    def _extract_styles(node: dict) -> dict:
        styles: dict = {}
        bbox = node.get("absoluteBoundingBox", {})
        if bbox:
            if "width" in bbox:
                styles["width"] = f"{bbox['width']}px"
            if "height" in bbox:
                styles["height"] = f"{bbox['height']}px"
        for corner in ["topLeftRadius", "topRightRadius", "bottomLeftRadius", "bottomRightRadius"]:
            if corner in node:
                styles.setdefault("borderRadius", f"{node[corner]}px")
        if "cornerRadius" in node:
            styles["borderRadius"] = f"{node['cornerRadius']}px"
        for side in ["paddingTop", "paddingRight", "paddingBottom", "paddingLeft"]:
            if side in node:
                styles[side] = f"{node[side]}px"
        if node.get("layoutMode"):
            styles["display"] = "flex"
            styles["flexDirection"] = "column" if node["layoutMode"] == "VERTICAL" else "row"
        if node.get("itemSpacing"):
            styles["gap"] = f"{node['itemSpacing']}px"
        for fill in node.get("fills", []):
            if fill.get("type") == "SOLID" and fill.get("visible", True):
                c = fill.get("color", {})
                r, g, b = round(c.get("r", 0) * 255), round(c.get("g", 0) * 255), round(c.get("b", 0) * 255)
                a = c.get("a", 1)
                styles["backgroundColor"] = f"rgba({r},{g},{b},{a})" if a < 1 else f"rgb({r},{g},{b})"
                break
        strokes = node.get("strokes", [])
        if strokes and node.get("strokeWeight"):
            styles["borderWidth"] = f"{node['strokeWeight']}px"
        return styles

    # ── MCP protocol ─────────────────────────────────────────────

    def _response(self, req_id, result):
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _error(self, req_id, code, msg):
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": msg}}

    async def handle_request(self, request: dict) -> Optional[dict]:
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return self._response(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": {"name": "solaris-mcp", "version": "2.0.0"},
                "capabilities": {"tools": {"listChanged": False}},
            })
        if method == "notifications/initialized":
            return None
        if method == "tools/list":
            return self._response(req_id, {"tools": self._get_tools()})
        if method == "tools/call":
            result = await self._call_tool(params.get("name"), params.get("arguments", {}))
            return self._response(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}],
            })
        return self._error(req_id, -32601, f"Method not found: {method}")

    # ── Tool definitions ─────────────────────────────────────────

    def _get_tools(self) -> List[Dict]:
        return [
            {"name": "solaris_component",
             "description": "Get Figma component details: all variants, properties, and component sets. Source of truth for dimensions, colors, styles.",
             "inputSchema": {"type": "object", "properties": {
                 "component": {"type": "string", "description": "Component name (e.g. 'button', 'accordion')"},
                 "summary_only": {"type": "boolean", "default": True}}, "required": ["component"]}},
            {"name": "solaris_variant",
             "description": "Get specific variant with exact Figma styles (borderRadius, padding, dimensions, colors).",
             "inputSchema": {"type": "object", "properties": {
                 "component": {"type": "string"},
                 "properties": {"type": "object", "description": "Filter by variant properties"},
                 "node_id": {"type": "string"}}, "required": ["component"]}},
            {"name": "solaris_wcag",
             "description": "Get WCAG accessibility pattern for a component type.",
             "inputSchema": {"type": "object", "properties": {
                 "pattern": {"type": "string", "enum": [
                     "accordion", "button", "tabs", "checkbox", "combobox", "dialog",
                     "radio-group", "switch", "breadcrumb", "focus-visible", "link", "listbox", "loader"]}},
                 "required": ["pattern"]}},
            {"name": "solaris_knowledge",
             "description": "Query knowledge base: semantic HTML rules, DS best practices, interactive behaviors.",
             "inputSchema": {"type": "object", "properties": {
                 "category": {"type": "string", "enum": [
                     "1-semantic-html", "2-wcag-patterns", "3-ds-best-practices",
                     "4-interactive-behaviors", "5-figma-to-css", "6-component-patterns", "7-token-mappings"]},
                 "topic": {"type": "string"}}, "required": ["category"]}},
            {"name": "solaris_validation",
             "description": "Get validation status for a component from the latest validation report.",
             "inputSchema": {"type": "object", "properties": {
                 "component": {"type": "string"}}}},
            {"name": "solaris_grep",
             "description": "Search in generated CSS or HTML files.",
             "inputSchema": {"type": "object", "properties": {
                 "pattern": {"type": "string"},
                 "file_type": {"type": "string", "enum": ["css", "html", "scss", "all"], "default": "css"}},
                 "required": ["pattern"]}},
            {"name": "solaris_list_components",
             "description": "List all available Figma components/families.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "solaris_stats",
             "description": "Get overall Solaris statistics: components count, validation rates, etc.",
             "inputSchema": {"type": "object", "properties": {}}},
        ]

    # ── Tool implementations ─────────────────────────────────────

    async def _call_tool(self, tool_name: str, args: dict) -> dict:
        handlers = {
            "solaris_component": self._tool_component,
            "solaris_variant": self._tool_variant,
            "solaris_wcag": self._tool_wcag,
            "solaris_knowledge": self._tool_knowledge,
            "solaris_validation": self._tool_validation,
            "solaris_grep": self._tool_grep,
            "solaris_stats": self._tool_stats,
            "solaris_list_components": self._tool_list_components,
        }
        handler = handlers.get(tool_name)
        if handler:
            return await handler(args)
        return {"error": f"Unknown tool: {tool_name}"}

    async def _tool_component(self, args: dict) -> dict:
        component = args.get("component", "")
        summary_only = args.get("summary_only", True)
        data = self._load_figma_data(component)
        if not data:
            return {"error": f"Component '{component}' not found. Use solaris_list_components to see available."}
        result: dict = {"component": component, "componentSets": []}
        for cs in data.get("componentSets", []):
            info: dict = {
                "name": cs.get("name"),
                "id": cs.get("id"),
                "variantCount": len(cs.get("children", [])),
            }
            props = cs.get("componentPropertyDefinitions", {})
            if props:
                info["properties"] = {
                    n: {"type": p.get("type"), "values": p.get("variantOptions", [])}
                    for n, p in props.items()
                }
            if not summary_only:
                info["sampleVariants"] = [
                    {"name": v.get("name"), "id": v.get("id"), "styles": self._extract_styles(v)}
                    for v in cs.get("children", [])[:5]
                ]
            result["componentSets"].append(info)
        return result

    async def _tool_variant(self, args: dict) -> dict:
        component = args.get("component", "")
        properties = args.get("properties", {})
        node_id = args.get("node_id")
        data = self._load_figma_data(component)
        if not data:
            return {"error": f"Component '{component}' not found"}
        for cs in data.get("componentSets", []):
            for variant in cs.get("children", []):
                if node_id and variant.get("id") == node_id:
                    return {"found": True, "componentSet": cs.get("name"),
                            "variant": {"name": variant.get("name"), "id": variant.get("id"),
                                        "styles": self._extract_styles(variant)}}
                if properties:
                    vname = variant.get("name", "")
                    match = all(f"{k}={v}" in vname for k, v in properties.items())
                    if match:
                        return {"found": True, "componentSet": cs.get("name"),
                                "variant": {"name": vname, "id": variant.get("id"),
                                            "styles": self._extract_styles(variant)}}
        return {"found": False, "filters": {"component": component, "properties": properties, "node_id": node_id}}

    async def _tool_wcag(self, args: dict) -> dict:
        pattern = args.get("pattern", "")
        data = self._load_knowledge("2-wcag-patterns", pattern)
        if data:
            return data
        patterns_dir = KNOWLEDGE_DIR / "2-wcag-patterns"
        if patterns_dir.exists():
            available = [f.stem for f in patterns_dir.glob("*.json")]
            return {"error": f"Pattern '{pattern}' not found. Available: {available}"}
        return {"error": "Knowledge base not found"}

    async def _tool_knowledge(self, args: dict) -> dict:
        category = args.get("category", "")
        topic = args.get("topic")
        cat_dir = KNOWLEDGE_DIR / category
        if not cat_dir.exists():
            available = [d.name for d in KNOWLEDGE_DIR.iterdir() if d.is_dir()] if KNOWLEDGE_DIR.exists() else []
            return {"error": f"Category '{category}' not found. Available: {available}"}
        if topic:
            data = self._load_knowledge(category, topic)
            return data if data else {"error": f"Topic '{topic}' not found in {category}"}
        topics = [f.stem for f in cat_dir.glob("*.json")]
        return {"category": category, "available_topics": topics}

    async def _tool_validation(self, args: dict) -> dict:
        component = args.get("component")
        report = REPORTS_DIR / "solaris-v5-validation.json"
        if not report.exists():
            return {"error": "Validation report not found"}
        with open(report) as f:
            data = json.load(f)
        results = data.get("results", [])
        if component:
            for r in results:
                if component.lower() in r.get("componentSet", "").lower():
                    return {"componentSet": r.get("componentSet"), "pass": r.get("pass"),
                            "checks": r.get("checks", {}), "variantCount": r.get("variantCount")}
            return {"error": f"Component '{component}' not found in validation report"}
        total = len(results)
        passed = sum(1 for r in results if r.get("pass"))
        return {"total": total, "passed": passed, "failed": total - passed,
                "passRate": f"{(passed / total * 100):.1f}%" if total else "0%",
                "components": [{"name": r.get("componentSet"), "pass": r.get("pass")} for r in results[:20]]}

    async def _tool_grep(self, args: dict) -> dict:
        pattern = args.get("pattern", "")
        file_type = args.get("file_type", "css")
        dirs_map = {"css": ([STYLES_DIR], "*.css"), "scss": ([STYLES_DIR], "*.scss"),
                     "html": ([GENERATED_PAGES_DIR], "*.html")}
        search_dirs, glob_pat = dirs_map.get(file_type, ([STYLES_DIR, GENERATED_PAGES_DIR], "*.*"))
        existing = [str(d) for d in search_dirs if d.exists()]
        if not existing:
            return {"pattern": pattern, "results_count": 0, "results": [], "note": "No data directories found"}
        try:
            cmd = ["grep", "-rn", "--include", glob_pat, pattern] + existing
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            lines = [l for l in result.stdout.strip().split("\n") if l][:20]
            return {"pattern": pattern, "file_type": file_type, "results_count": len(lines), "results": lines}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_stats(self, args: dict) -> dict:
        stats: Dict[str, Any] = {"figma_data": {}, "knowledge": {}, "generated": {}, "validation": {}}
        if FIGMA_DATA_DIR.exists():
            files = list(FIGMA_DATA_DIR.glob("*-all-depth10.json"))
            stats["figma_data"] = {"component_families": len(files),
                                   "files": [f.name for f in files[:10]]}
        if KNOWLEDGE_DIR.exists():
            for cat in KNOWLEDGE_DIR.iterdir():
                if cat.is_dir():
                    stats["knowledge"][cat.name] = len(list(cat.glob("*.json")))
        if GENERATED_PAGES_DIR.exists():
            stats["generated"]["html_pages"] = len(list(GENERATED_PAGES_DIR.glob("*.html")))
        if STYLES_DIR.exists():
            stats["generated"]["css_files"] = len(list(STYLES_DIR.glob("*.css")))
        report = REPORTS_DIR / "solaris-v5-validation.json"
        if report.exists():
            with open(report) as f:
                data = json.load(f)
            results = data.get("results", [])
            passed = sum(1 for r in results if r.get("pass"))
            stats["validation"] = {"total": len(results), "passed": passed,
                                   "passRate": f"{(passed / len(results) * 100):.1f}%" if results else "0%"}
        return stats

    async def _tool_list_components(self, args: dict) -> dict:
        if not FIGMA_DATA_DIR.exists():
            return {"error": f"Figma data not found at {FIGMA_DATA_DIR}",
                    "hint": "Set SOLARIS_FIGMA_DIR or copy figma-data to the expected location"}
        components = []
        for f in sorted(FIGMA_DATA_DIR.glob("*-all-depth10.json")):
            name = f.stem.replace("-all-depth10", "")
            try:
                with open(f) as fh:
                    data = json.load(fh)
                cs = data.get("componentSets", [])
                components.append({"name": name, "componentSets": len(cs),
                                   "variants": sum(len(c.get("children", [])) for c in cs)})
            except Exception:
                components.append({"name": name, "error": "parse error"})
        return {"total": len(components), "components": components}


# ── stdio main loop ──────────────────────────────────────────────

async def main():
    server = SolarisMCPServer()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
    transport, _ = await asyncio.get_event_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout)
    writer = asyncio.StreamWriter(transport, protocol, reader, asyncio.get_event_loop())

    while True:
        try:
            line = await reader.readline()
            if not line:
                break
            request = json.loads(line.decode().strip())
            response = await server.handle_request(request)
            if response:
                writer.write((json.dumps(response) + "\n").encode())
                await writer.drain()
        except json.JSONDecodeError:
            continue
        except Exception as e:
            sys.stderr.write(f"solaris-mcp error: {e}\n")
            continue


if __name__ == "__main__":
    asyncio.run(main())
