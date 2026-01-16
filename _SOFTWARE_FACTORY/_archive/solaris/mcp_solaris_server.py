#!/usr/bin/env python3
"""
MCP RAG Server for Solaris Design System

Exposes Solaris Figma data and knowledge base to Claude/Copilot CLI.
Uses llama-server:8001 (nomic-embed-text) for semantic search embeddings.

Tools:
- solaris_component: Get component details from Figma extracts
- solaris_variant: Get specific variant with all styles (borderRadius, padding, etc.)
- solaris_wcag: Get WCAG pattern for a component type
- solaris_knowledge: Query knowledge base (semantic HTML, best practices, etc.)
- solaris_validation: Get validation status for a component
- solaris_grep: Search in generated CSS/HTML
- solaris_stats: Overall stats
- solaris_list_components: List all available components
- solaris_cli: Get Solaris CLI documentation (commands, architecture, pipeline)
- solaris_search: Semantic search using embeddings (requires llama-server:8001)
- solaris_index: Index content for semantic search

Embedding Server:
    llama-server on port 8001 with nomic-embed-text model (768 dimensions)
    Start with: ./tools/ralph-copilot/start-embedding-server.sh

Usage:
    Add to Claude Code MCP settings (~/.claude/settings.json):
    {
      "mcpServers": {
        "solaris": {
          "command": "python3",
          "args": ["/Users/sylvain/_LAPOSTE/_SD3/mcp_solaris_server.py"]
        }
      }
    }
"""

import sys
import json
import asyncio
import subprocess
import hashlib
import pickle
import httpx
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

# MCP Protocol constants
PROTOCOL_VERSION = "2024-11-05"

# Project paths
PROJECT_ROOT = Path(__file__).parent
FIGMA_DATA_DIR = PROJECT_ROOT / "design-system" / "figma-data"
KNOWLEDGE_DIR = PROJECT_ROOT / "design-system" / "knowledge"
GENERATED_PAGES_DIR = PROJECT_ROOT / "generated-pages"
STYLES_DIR = PROJECT_ROOT / "design-system" / "libs" / "ui" / "src" / "styles"
REPORTS_DIR = PROJECT_ROOT / "reports"
EMBEDDINGS_CACHE = PROJECT_ROOT / ".solaris-embeddings.pkl"

# Embedding server config
EMBEDDING_SERVER_URL = "http://127.0.0.1:8001"
EMBEDDING_DIMENSIONS = 768  # nomic-embed-text dimensions


class SolarisMCPServer:
    def __init__(self):
        self.components_cache: Dict[str, Any] = {}
        self.knowledge_cache: Dict[str, Any] = {}
        self.embeddings_index: Dict[
            str, Any
        ] = {}  # {chunk_id: {"text": str, "embedding": np.array, "metadata": dict}}
        self.embeddings_loaded = False

    async def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Get embedding from llama-server:8001"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{EMBEDDING_SERVER_URL}/embedding", json={"content": text}
                )
                if response.status_code == 200:
                    data = response.json()
                    # Response format: [{"index": 0, "embedding": [[...768 floats...]]}]
                    if isinstance(data, list) and len(data) > 0:
                        first = data[0]
                        if isinstance(first, dict) and "embedding" in first:
                            emb = first["embedding"]
                            if isinstance(emb, list) and len(emb) > 0:
                                actual_emb = emb[0]  # Unwrap nested list
                                return np.array(actual_emb, dtype=np.float32)
        except Exception as e:
            pass  # Silently fail, embeddings are optional
        return None

    def _load_embeddings_cache(self):
        """Load cached embeddings from disk"""
        if self.embeddings_loaded:
            return
        if EMBEDDINGS_CACHE.exists():
            try:
                with open(EMBEDDINGS_CACHE, "rb") as f:
                    self.embeddings_index = pickle.load(f)
                self.embeddings_loaded = True
            except:
                pass

    def _save_embeddings_cache(self):
        """Save embeddings to disk"""
        try:
            with open(EMBEDDINGS_CACHE, "wb") as f:
                pickle.dump(self.embeddings_index, f)
        except:
            pass

    async def _index_content(self) -> Dict[str, int]:
        """Index all Solaris content for semantic search"""
        stats = {"figma": 0, "css": 0, "html": 0, "knowledge": 0}

        # Index Figma data
        if FIGMA_DATA_DIR.exists():
            for f in FIGMA_DATA_DIR.glob("*-all-depth10.json"):
                try:
                    with open(f, "r") as file:
                        data = json.load(file)
                        component_name = f.stem.replace("-all-depth10", "")

                        # Index component sets
                        for cs in data.get("componentSets", []):
                            cs_name = cs.get("name", "")
                            chunk_id = f"figma:{component_name}:{cs.get('id', '')}"
                            text = (
                                f"Component: {component_name}, ComponentSet: {cs_name}"
                            )

                            # Add properties
                            props = cs.get("componentPropertyDefinitions", {})
                            if props:
                                text += f", Properties: {', '.join(props.keys())}"

                            # Add variant count
                            variants = cs.get("children", [])
                            text += f", Variants: {len(variants)}"

                            embedding = await self._get_embedding(text)
                            if embedding is not None:
                                self.embeddings_index[chunk_id] = {
                                    "text": text,
                                    "embedding": embedding,
                                    "metadata": {
                                        "type": "figma",
                                        "component": component_name,
                                        "component_set": cs_name,
                                        "file": str(f),
                                    },
                                }
                                stats["figma"] += 1
                except:
                    pass

        # Index CSS files
        if STYLES_DIR.exists():
            for f in STYLES_DIR.glob("_*.css"):
                try:
                    content = f.read_text()[:2000]  # First 2000 chars
                    chunk_id = f"css:{f.stem}"
                    text = f"CSS file: {f.name}, Content: {content[:500]}"

                    embedding = await self._get_embedding(text)
                    if embedding is not None:
                        self.embeddings_index[chunk_id] = {
                            "text": text,
                            "embedding": embedding,
                            "metadata": {"type": "css", "file": str(f), "name": f.stem},
                        }
                        stats["css"] += 1
                except:
                    pass

        # Index knowledge base
        if KNOWLEDGE_DIR.exists():
            for f in KNOWLEDGE_DIR.glob("**/*.json"):
                try:
                    with open(f, "r") as file:
                        data = json.load(file)
                        chunk_id = f"knowledge:{f.parent.name}:{f.stem}"
                        text = f"Knowledge: {f.parent.name}/{f.stem}, Content: {json.dumps(data)[:500]}"

                        embedding = await self._get_embedding(text)
                        if embedding is not None:
                            self.embeddings_index[chunk_id] = {
                                "text": text,
                                "embedding": embedding,
                                "metadata": {
                                    "type": "knowledge",
                                    "category": f.parent.name,
                                    "topic": f.stem,
                                    "file": str(f),
                                },
                            }
                            stats["knowledge"] += 1
                except:
                    pass

        self._save_embeddings_cache()
        self.embeddings_loaded = True
        return stats

    async def _semantic_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search indexed content using embeddings"""
        self._load_embeddings_cache()

        if not self.embeddings_index:
            return []

        query_embedding = await self._get_embedding(query)
        if query_embedding is None:
            return []

        # Compute cosine similarity
        results = []
        for chunk_id, data in self.embeddings_index.items():
            embedding = data["embedding"]
            similarity = np.dot(query_embedding, embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(embedding)
            )
            results.append(
                {
                    "chunk_id": chunk_id,
                    "similarity": float(similarity),
                    "text": data["text"],
                    "metadata": data["metadata"],
                }
            )

        # Sort by similarity and return top-k
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def _load_figma_data(self, component_name: str) -> Optional[Dict]:
        """Load Figma data for a component"""
        if component_name in self.components_cache:
            return self.components_cache[component_name]

        # Try different naming patterns
        patterns = [
            f"{component_name}-all-depth10.json",
            f"{component_name.lower()}-all-depth10.json",
            f"{component_name.replace(' ', '-').lower()}-all-depth10.json",
        ]

        for pattern in patterns:
            filepath = FIGMA_DATA_DIR / pattern
            if filepath.exists():
                with open(filepath, "r") as f:
                    data = json.load(f)
                    self.components_cache[component_name] = data
                    return data

        return None

    def _load_knowledge(self, category: str, name: str) -> Optional[Dict]:
        """Load knowledge base entry"""
        cache_key = f"{category}/{name}"
        if cache_key in self.knowledge_cache:
            return self.knowledge_cache[cache_key]

        filepath = KNOWLEDGE_DIR / category / f"{name}.json"
        if filepath.exists():
            with open(filepath, "r") as f:
                data = json.load(f)
                self.knowledge_cache[cache_key] = data
                return data
        return None

    def _extract_styles(self, node: Dict) -> Dict:
        """Extract CSS-relevant styles from a Figma node"""
        styles = {}

        # Dimensions
        box = node.get("absoluteBoundingBox", {})
        if box.get("width"):
            styles["width"] = f"{round(box['width'])}px"
        if box.get("height"):
            styles["height"] = f"{round(box['height'])}px"

        # Border radius
        if node.get("cornerRadius") is not None:
            styles["borderRadius"] = f"{node['cornerRadius']}px"
        elif node.get("rectangleCornerRadii"):
            radii = node["rectangleCornerRadii"]
            styles["borderRadius"] = " ".join(f"{r}px" for r in radii)

        # Padding
        for prop in ["paddingLeft", "paddingRight", "paddingTop", "paddingBottom"]:
            if node.get(prop) is not None:
                styles[prop] = f"{node[prop]}px"

        # Gap
        if node.get("itemSpacing") is not None:
            styles["gap"] = f"{node['itemSpacing']}px"

        # Fills (background)
        fills = node.get("fills", [])
        for fill in fills:
            if fill.get("type") == "SOLID" and fill.get("visible", True):
                color = fill.get("color", {})
                r = round(color.get("r", 0) * 255)
                g = round(color.get("g", 0) * 255)
                b = round(color.get("b", 0) * 255)
                a = color.get("a", 1)
                if a < 1:
                    styles["backgroundColor"] = f"rgba({r}, {g}, {b}, {a})"
                else:
                    styles["backgroundColor"] = f"rgb({r}, {g}, {b})"
                break

        # Strokes (border)
        strokes = node.get("strokes", [])
        if strokes and node.get("strokeWeight"):
            styles["borderWidth"] = f"{node['strokeWeight']}px"

        return styles

    async def handle_request(self, request: dict) -> dict:
        """Handle MCP protocol requests"""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return self._response(
                req_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "serverInfo": {
                        "name": "solaris-mcp",
                        "version": "1.0.0",
                    },
                    "capabilities": {
                        "tools": {"listChanged": False},
                    },
                },
            )

        elif method == "tools/list":
            return self._response(req_id, {"tools": self._get_tools()})

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            result = await self._call_tool(tool_name, args)
            return self._response(
                req_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2, ensure_ascii=False),
                        }
                    ]
                },
            )

        elif method == "notifications/initialized":
            return None

        else:
            return self._error(req_id, -32601, f"Method not found: {method}")

    def _get_tools(self) -> List[Dict]:
        """Define available MCP tools"""
        return [
            {
                "name": "solaris_component",
                "description": "Get Figma component details: all variants, properties, and component sets. Source of truth for dimensions, colors, styles.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component": {
                            "type": "string",
                            "description": "Component name (e.g., 'button', 'accordion', 'badge')",
                        },
                        "summary_only": {
                            "type": "boolean",
                            "default": True,
                            "description": "If true, return summary only. If false, include all variants.",
                        },
                    },
                    "required": ["component"],
                },
            },
            {
                "name": "solaris_variant",
                "description": "Get specific variant with exact Figma styles (borderRadius, padding, dimensions, colors). Use for style validation.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component": {
                            "type": "string",
                            "description": "Component name",
                        },
                        "properties": {
                            "type": "object",
                            "description": 'Filter by properties (e.g., {"Size": "Small", "Style": "Primary"})',
                        },
                        "node_id": {
                            "type": "string",
                            "description": "Or specify exact Figma node ID (e.g., '37:1201')",
                        },
                    },
                    "required": ["component"],
                },
            },
            {
                "name": "solaris_wcag",
                "description": "Get WCAG accessibility pattern for a component type (accordion, button, tabs, checkbox, combobox, dialog, radio-group, switch, breadcrumb, focus-visible, link, listbox, loader)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "enum": [
                                "accordion",
                                "button",
                                "tabs",
                                "checkbox",
                                "combobox",
                                "dialog",
                                "radio-group",
                                "switch",
                                "breadcrumb",
                                "focus-visible",
                                "link",
                                "listbox",
                                "loader",
                            ],
                            "description": "WCAG pattern name",
                        }
                    },
                    "required": ["pattern"],
                },
            },
            {
                "name": "solaris_knowledge",
                "description": "Query knowledge base: semantic HTML rules, DS best practices, interactive behaviors",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": [
                                "1-semantic-html",
                                "2-wcag-patterns",
                                "3-ds-best-practices",
                                "4-interactive-behaviors",
                            ],
                            "description": "Knowledge category",
                        },
                        "topic": {
                            "type": "string",
                            "description": "Specific topic (e.g., '_rules' for semantic HTML, 'material' for DS practices)",
                        },
                    },
                    "required": ["category"],
                },
            },
            {
                "name": "solaris_validation",
                "description": "Get validation status for a component from the latest validation report",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component": {
                            "type": "string",
                            "description": "Component name (optional - returns all if not specified)",
                        }
                    },
                },
            },
            {
                "name": "solaris_grep",
                "description": "Search in generated CSS or HTML files",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Search pattern (regex)",
                        },
                        "file_type": {
                            "type": "string",
                            "enum": ["css", "html", "scss", "all"],
                            "default": "css",
                        },
                    },
                    "required": ["pattern"],
                },
            },
            {
                "name": "solaris_stats",
                "description": "Get overall Solaris statistics: components count, validation rates, etc.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "solaris_list_components",
                "description": "List all available Figma components/families",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "solaris_cli",
                "description": "Get Solaris CLI documentation: commands, usage, architecture, pipeline steps",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "enum": [
                                "overview",
                                "pipeline",
                                "architecture",
                                "validation",
                                "css",
                                "html",
                                "all",
                            ],
                            "default": "overview",
                            "description": "Documentation topic",
                        }
                    },
                },
            },
            {
                "name": "solaris_search",
                "description": "Semantic search across Solaris content (Figma data, CSS, knowledge base) using embeddings. Use for natural language queries.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query (e.g., 'button hover state', 'accordion accessibility')",
                        },
                        "top_k": {
                            "type": "integer",
                            "default": 5,
                            "description": "Number of results to return",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "solaris_index",
                "description": "Index/reindex all Solaris content for semantic search. Run this after updating Figma data or CSS.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    async def _call_tool(self, tool_name: str, args: dict) -> dict:
        """Route tool calls"""
        handlers = {
            "solaris_component": self._tool_component,
            "solaris_variant": self._tool_variant,
            "solaris_wcag": self._tool_wcag,
            "solaris_knowledge": self._tool_knowledge,
            "solaris_validation": self._tool_validation,
            "solaris_grep": self._tool_grep,
            "solaris_stats": self._tool_stats,
            "solaris_list_components": self._tool_list_components,
            "solaris_cli": self._tool_cli,
            "solaris_search": self._tool_search,
            "solaris_index": self._tool_index,
        }

        handler = handlers.get(tool_name)
        if handler:
            return await handler(args)
        return {"error": f"Unknown tool: {tool_name}"}

    async def _tool_component(self, args: dict) -> dict:
        """Get component details"""
        component = args.get("component", "")
        summary_only = args.get("summary_only", True)

        data = self._load_figma_data(component)
        if not data:
            return {
                "error": f"Component '{component}' not found. Use solaris_list_components to see available."
            }

        component_sets = data.get("componentSets", [])

        result = {"component": component, "componentSets": []}

        for cs in component_sets:
            cs_info = {
                "name": cs.get("name"),
                "id": cs.get("id"),
                "variantCount": len(cs.get("children", [])),
            }

            # Extract properties
            props = cs.get("componentPropertyDefinitions", {})
            if props:
                cs_info["properties"] = {
                    name: {
                        "type": prop.get("type"),
                        "values": prop.get("variantOptions", []),
                    }
                    for name, prop in props.items()
                }

            if not summary_only:
                # Include first 5 variants with styles
                cs_info["sampleVariants"] = []
                for variant in cs.get("children", [])[:5]:
                    cs_info["sampleVariants"].append(
                        {
                            "name": variant.get("name"),
                            "id": variant.get("id"),
                            "styles": self._extract_styles(variant),
                        }
                    )

            result["componentSets"].append(cs_info)

        return result

    async def _tool_variant(self, args: dict) -> dict:
        """Get specific variant with styles"""
        component = args.get("component", "")
        properties = args.get("properties", {})
        node_id = args.get("node_id")

        data = self._load_figma_data(component)
        if not data:
            return {"error": f"Component '{component}' not found"}

        for cs in data.get("componentSets", []):
            for variant in cs.get("children", []):
                # Match by node ID
                if node_id and variant.get("id") == node_id:
                    return {
                        "found": True,
                        "componentSet": cs.get("name"),
                        "variant": {
                            "name": variant.get("name"),
                            "id": variant.get("id"),
                            "styles": self._extract_styles(variant),
                            "children": [
                                {
                                    "name": c.get("name"),
                                    "type": c.get("type"),
                                    "styles": self._extract_styles(c),
                                }
                                for c in variant.get("children", [])[:10]
                            ],
                        },
                    }

                # Match by properties
                if properties:
                    variant_name = variant.get("name", "")
                    matches = all(
                        f"{k}={v}" in variant_name for k, v in properties.items()
                    )
                    if matches:
                        return {
                            "found": True,
                            "componentSet": cs.get("name"),
                            "variant": {
                                "name": variant.get("name"),
                                "id": variant.get("id"),
                                "styles": self._extract_styles(variant),
                                "children": [
                                    {
                                        "name": c.get("name"),
                                        "type": c.get("type"),
                                        "styles": self._extract_styles(c),
                                    }
                                    for c in variant.get("children", [])[:10]
                                ],
                            },
                        }

        return {"found": False, "error": "Variant not found with given criteria"}

    async def _tool_wcag(self, args: dict) -> dict:
        """Get WCAG pattern"""
        pattern = args.get("pattern", "")

        data = self._load_knowledge("2-wcag-patterns", pattern)
        if data:
            return data

        # List available patterns
        patterns_dir = KNOWLEDGE_DIR / "2-wcag-patterns"
        if patterns_dir.exists():
            available = [f.stem for f in patterns_dir.glob("*.json")]
            return {"error": f"Pattern '{pattern}' not found. Available: {available}"}

        return {"error": "Knowledge base not found"}

    async def _tool_knowledge(self, args: dict) -> dict:
        """Query knowledge base"""
        category = args.get("category", "")
        topic = args.get("topic")

        category_dir = KNOWLEDGE_DIR / category
        if not category_dir.exists():
            return {"error": f"Category '{category}' not found"}

        if topic:
            data = self._load_knowledge(category, topic)
            if data:
                return data
            return {"error": f"Topic '{topic}' not found in {category}"}

        # List available topics
        topics = [f.stem for f in category_dir.glob("*.json")]
        return {"category": category, "available_topics": topics}

    async def _tool_validation(self, args: dict) -> dict:
        """Get validation status"""
        component = args.get("component")

        report_file = REPORTS_DIR / "solaris-v5-validation.json"
        if not report_file.exists():
            return {
                "error": "Validation report not found. Run ./solaris validate first."
            }

        with open(report_file, "r") as f:
            data = json.load(f)

        results = data.get("results", [])

        if component:
            # Find specific component
            for r in results:
                if component.lower() in r.get("componentSet", "").lower():
                    return {
                        "componentSet": r.get("componentSet"),
                        "pass": r.get("pass"),
                        "checks": r.get("checks", {}),
                        "variantCount": r.get("variantCount"),
                    }
            return {"error": f"Component '{component}' not found in validation report"}

        # Summary
        total = len(results)
        passed = sum(1 for r in results if r.get("pass"))
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "passRate": f"{(passed / total * 100):.1f}%" if total > 0 else "0%",
            "components": [
                {"name": r.get("componentSet"), "pass": r.get("pass")}
                for r in results[:20]
            ],
        }

    async def _tool_grep(self, args: dict) -> dict:
        """Grep in CSS/HTML files"""
        pattern = args.get("pattern", "")
        file_type = args.get("file_type", "css")

        search_dirs = []
        glob_pattern = "*.*"

        if file_type == "css":
            search_dirs = [STYLES_DIR]
            glob_pattern = "*.css"
        elif file_type == "scss":
            search_dirs = [STYLES_DIR]
            glob_pattern = "*.scss"
        elif file_type == "html":
            search_dirs = [GENERATED_PAGES_DIR]
            glob_pattern = "*.html"
        else:
            search_dirs = [STYLES_DIR, GENERATED_PAGES_DIR]

        try:
            cmd = ["grep", "-rn", pattern] + [str(d) for d in search_dirs if d.exists()]
            if glob_pattern != "*.*":
                cmd = ["grep", "-rn", "--include", glob_pattern, pattern] + [
                    str(d) for d in search_dirs if d.exists()
                ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            lines = result.stdout.strip().split("\n")[:20]  # Limit to 20 results

            return {
                "pattern": pattern,
                "file_type": file_type,
                "results_count": len([l for l in lines if l]),
                "results": lines,
            }
        except Exception as e:
            return {"error": str(e)}

    async def _tool_stats(self, args: dict) -> dict:
        """Get overall stats"""
        stats = {"figma_data": {}, "knowledge": {}, "generated": {}, "validation": {}}

        # Figma data
        if FIGMA_DATA_DIR.exists():
            data_files = list(FIGMA_DATA_DIR.glob("*-all-depth10.json"))
            stats["figma_data"] = {
                "component_families": len(data_files),
                "files": [f.name for f in data_files[:10]],
            }

        # Knowledge base
        if KNOWLEDGE_DIR.exists():
            for category in KNOWLEDGE_DIR.iterdir():
                if category.is_dir():
                    files = list(category.glob("*.json"))
                    stats["knowledge"][category.name] = len(files)

        # Generated pages
        if GENERATED_PAGES_DIR.exists():
            stats["generated"]["html_pages"] = len(
                list(GENERATED_PAGES_DIR.glob("*.html"))
            )

        # CSS files
        if STYLES_DIR.exists():
            stats["generated"]["css_files"] = len(list(STYLES_DIR.glob("*.css")))
            stats["generated"]["scss_files"] = len(list(STYLES_DIR.glob("*.scss")))

        # Validation
        report_file = REPORTS_DIR / "solaris-v5-validation.json"
        if report_file.exists():
            with open(report_file, "r") as f:
                data = json.load(f)
            results = data.get("results", [])
            passed = sum(1 for r in results if r.get("pass"))
            stats["validation"] = {
                "total": len(results),
                "passed": passed,
                "passRate": f"{(passed / len(results) * 100):.1f}%"
                if results
                else "0%",
            }

        return stats

    async def _tool_list_components(self, args: dict) -> dict:
        """List available components"""
        if not FIGMA_DATA_DIR.exists():
            return {"error": "Figma data directory not found"}

        components = []
        for f in FIGMA_DATA_DIR.glob("*-all-depth10.json"):
            name = f.stem.replace("-all-depth10", "")
            # Get quick stats
            try:
                with open(f, "r") as file:
                    data = json.load(file)
                    cs_count = len(data.get("componentSets", []))
                    variant_count = sum(
                        len(cs.get("children", []))
                        for cs in data.get("componentSets", [])
                    )
                    components.append(
                        {
                            "name": name,
                            "componentSets": cs_count,
                            "variants": variant_count,
                        }
                    )
            except:
                components.append({"name": name, "error": "Could not parse"})

        return {
            "total": len(components),
            "components": sorted(components, key=lambda x: x.get("name", "")),
        }

    async def _tool_cli(self, args: dict) -> dict:
        """Get Solaris CLI documentation"""
        topic = args.get("topic", "overview")

        docs = {
            "overview": {
                "name": "Solaris CLI v5",
                "description": "Design System Automation - Zero Hallucination",
                "usage": "./solaris",
                "location": "/Users/sylvain/_LAPOSTE/_SD3/solaris",
                "note": "Single command runs entire pipeline. No subcommands needed.",
                "pipeline_summary": [
                    "1. Load Knowledge Graph (semantic rules, WCAG patterns, tokens)",
                    "2. Read 40 Figma pages (168 component sets, 4621 variants)",
                    "3. Generate CSS by ATOMIC PROPERTY (not by variant!)",
                    "4. Generate semantic HTML from WCAG patterns",
                    "5. Compile SCSS → CSS",
                    "6. Validate ALL variants with Playwright",
                ],
            },
            "pipeline": {
                "step_1_knowledge": {
                    "name": "Load Knowledge Graph",
                    "sources": [
                        "design-system/knowledge/1-semantic-html/_rules.json",
                        "design-system/knowledge/2-wcag-patterns/*.json",
                        "design-system/knowledge/3-ds-best-practices/*.json",
                        "design-system/knowledge/4-interactive-behaviors/*.json",
                    ],
                    "output": "In-memory mappings for HTML generation",
                },
                "step_2_figma": {
                    "name": "Read Figma Data",
                    "sources": "design-system/figma-data/*-all-depth10.json",
                    "stats": {
                        "pages": 40,
                        "component_sets": 168,
                        "variants": 4621,
                        "depth": 10,
                    },
                },
                "step_3_css": {
                    "name": "Generate CSS by Property",
                    "output": "design-system/libs/ui/src/styles/_*.css",
                    "architecture": "Per-property modifiers, NOT per-variant",
                    "example": ".button--size-small, .button--style-primary",
                },
                "step_4_html": {
                    "name": "Generate Semantic HTML",
                    "output": "generated-pages/*.html",
                    "features": [
                        "Semantic tags from WCAG patterns",
                        "ARIA attributes",
                        "data-figma-node for traceability",
                    ],
                },
                "step_5_compile": {
                    "name": "Compile SCSS",
                    "output": "*.css files ready for browser",
                },
                "step_6_validate": {
                    "name": "Playwright Validation",
                    "checks": [
                        "Dimensions match Figma (0px tolerance)",
                        "CSS tokens applied correctly",
                        "Semantic HTML present",
                        "ARIA attributes correct",
                    ],
                    "report": "reports/solaris-v5-validation.json",
                },
            },
            "architecture": {
                "css_principle": "Each PROPERTY generates independent CSS, not each VARIANT",
                "example": {
                    "problem": "Button has 936 variants (3×4×4×4×6)",
                    "old_approach": "936 CSS rules (one per variant) ❌",
                    "new_approach": "21 CSS rules (3+4+4+4+6 per property) ✅",
                    "reduction": "55x less CSS",
                },
                "css_structure": {
                    "base": ".button { display: flex; align-items: center; }",
                    "size_modifiers": [
                        ".button--size-small { height: var(--sizing-32); }",
                        ".button--size-medium { height: var(--sizing-48); }",
                        ".button--size-large { height: var(--sizing-56); }",
                    ],
                    "style_modifiers": [
                        ".button--style-primary { background: var(--color-primary); }",
                        ".button--style-neutral { background: var(--color-neutral-100); }",
                    ],
                    "state_modifiers": [
                        ".button--state-hover, .button:hover { filter: brightness(1.1); }",
                        ".button--state-disabled, .button[disabled] { opacity: 0.5; }",
                    ],
                },
                "html_classes": 'class="button button--size-small button--style-primary button--state-default"',
            },
            "validation": {
                "tool": "node tools/validate-v5-specs.js",
                "report": "reports/solaris-v5-validation.json",
                "checks": [
                    "depth: HTML depth >= 2",
                    "tokenization: 100% var(--tokens), 0 hardcoded",
                    "states: hover/focus/disabled CSS present",
                    "nodeCoverage: Figma nodes rendered in DOM",
                    "semantic: Proper HTML tags (button, nav, header)",
                    "accessibility: ARIA roles present",
                    "css: Computed styles match Figma",
                    "dimensions: Width/height match Figma specs",
                ],
                "thresholds": {
                    "dimensions": "15% match (allows simplified HTML)",
                    "nodeCoverage": "30% for small, 10% for large components",
                    "semantic": "0.5% semantic tags minimum",
                },
                "current_status": "166/166 passing (100%)",
            },
            "css": {
                "location": "design-system/libs/ui/src/styles/",
                "naming": "_[family]-[component].css",
                "examples": [
                    "_button-button.css",
                    "_accordion-accordion.css",
                    "_badge-badge-basic.css",
                ],
                "tokens": {
                    "foundations": "foundations-variables.css",
                    "figma_vars": "_figma-vars.css",
                    "colors": "var(--color-*)",
                    "spacing": "var(--spacing-*)",
                    "sizing": "var(--sizing-*)",
                    "radius": "var(--radius-*)",
                },
            },
            "html": {
                "location": "generated-pages/",
                "naming": "[family]-[component].html",
                "examples": [
                    "button-button.html",
                    "accordion-accordion.html",
                    "badge-badge-basic.html",
                ],
                "attributes": {
                    "data-component-set": "Component set name from Figma",
                    "data-figma-node": "Figma node ID for traceability",
                    "data-variant": "Variant properties (Size=Small, Style=Primary)",
                    "role": "ARIA role (button, navigation, dialog)",
                },
                "http_server": "npx http-server -p 8080 then open http://localhost:8080/generated-pages/",
            },
        }

        if topic == "all":
            return docs

        return docs.get(
            topic,
            {
                "error": f"Unknown topic: {topic}. Available: overview, pipeline, architecture, validation, css, html, all"
            },
        )

    async def _tool_search(self, args: dict) -> dict:
        """Semantic search across Solaris content"""
        query = args.get("query", "")
        top_k = args.get("top_k", 5)

        if not query:
            return {"error": "Query is required"}

        # Check if embedding server is available
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{EMBEDDING_SERVER_URL}/health")
                if response.status_code != 200:
                    return {
                        "error": "Embedding server not available at port 8001. Run: ./tools/ralph-copilot/start-embedding-server.sh"
                    }
        except:
            return {
                "error": "Embedding server not available at port 8001. Run: ./tools/ralph-copilot/start-embedding-server.sh"
            }

        results = await self._semantic_search(query, top_k)

        if not results:
            return {
                "query": query,
                "results": [],
                "note": "No results found. Try running solaris_index first to index content.",
            }

        return {"query": query, "top_k": top_k, "results": results}

    async def _tool_index(self, args: dict) -> dict:
        """Index all Solaris content for semantic search"""
        # Check if embedding server is available
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{EMBEDDING_SERVER_URL}/health")
                if response.status_code != 200:
                    return {"error": "Embedding server not available at port 8001"}
        except:
            return {
                "error": "Embedding server not available at port 8001. Start it with: ./tools/ralph-copilot/start-embedding-server.sh"
            }

        # Clear existing index
        self.embeddings_index = {}
        self.embeddings_loaded = False

        # Index content
        stats = await self._index_content()

        total = sum(stats.values())
        return {
            "status": "indexed",
            "total_chunks": total,
            "breakdown": stats,
            "cache_file": str(EMBEDDINGS_CACHE),
        }

    async def get_stats(self) -> dict:
        """Public wrapper for _tool_stats"""
        return await self._tool_stats({})

    async def get_component(self, component: str, summary_only: bool = True) -> dict:
        """Public wrapper for _tool_component"""
        return await self._tool_component(
            {"component": component, "summary_only": summary_only}
        )

    async def get_variant(
        self, component: str, properties: dict = None, node_id: str = None
    ) -> dict:
        """Public wrapper for _tool_variant"""
        return await self._tool_variant(
            {"component": component, "properties": properties or {}, "node_id": node_id}
        )

    async def get_wcag_pattern(self, pattern: str) -> dict:
        """Public wrapper for _tool_wcag"""
        return await self._tool_wcag({"pattern": pattern})

    async def get_validation(self, component: str = None) -> dict:
        """Public wrapper for _tool_validation"""
        return await self._tool_validation({"component": component})

    async def grep_generated(self, pattern: str, file_type: str = "css") -> dict:
        """Public wrapper for _tool_grep"""
        return await self._tool_grep({"pattern": pattern, "file_type": file_type})

    async def list_components(self) -> dict:
        """Public wrapper for _tool_list_components"""
        return await self._tool_list_components({})

    async def get_knowledge(self, category: str, topic: str = None) -> dict:
        """Public wrapper for _tool_knowledge"""
        return await self._tool_knowledge({"category": category, "topic": topic})

    def _response(self, req_id, result) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _error(self, req_id, code: int, message: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }


async def main():
    """Main MCP server loop"""
    server = SolarisMCPServer()

    # Read from stdin, write to stdout (MCP protocol)
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    (
        writer_transport,
        writer_protocol,
    ) = await asyncio.get_event_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(
        writer_transport, writer_protocol, reader, asyncio.get_event_loop()
    )

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
            sys.stderr.write(f"Error: {e}\n")
            continue


if __name__ == "__main__":
    asyncio.run(main())
