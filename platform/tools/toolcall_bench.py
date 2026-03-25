"""ToolCall-15 Bench — 15-scenario tool-calling quality benchmark.

Ported from stevibe/ToolCall-15 (MIT). Evaluates LLM tool-use across 5 categories:
  A: Tool Selection (TC-01..03)
  B: Parameter Precision (TC-04..06)
  C: Multi-Step Chains (TC-07..09)
  D: Restraint & Refusal (TC-10..12)
  E: Error Recovery (TC-13..15)

Each scenario scored: pass=2, partial=1, fail=0. Final = avg of 5 category %.

Usage:
    from platform.tools.toolcall_bench import run_toolcall_bench
    result = await run_toolcall_bench("MiniMax-M2.7", "minimax")
    result = await run_toolcall_bench("gpt-5-mini", "azure-openai")
"""
# Ref: feat-evals — ToolCall-15 (stevibe/ToolCall-15, MIT)

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RESULTS_DIR = DATA_DIR / "toolcall_bench"

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to the tools provided.\n\n"
    "Rules:\n"
    "- Use a tool ONLY when it is necessary to fulfill the user's request.\n"
    "- If you can answer directly from your own knowledge, do so without calling a tool.\n"
    "- If a tool call fails, explain the failure and suggest an alternative approach.\n"
    "- Never invent information that a tool should provide."
)

BENCHMARK_CONTEXT = "Today's date is 2026-03-20 (Friday)."

MAX_TURNS = 8

# ── Tool Definitions (OpenAI format) ─────────────────────────────────────────

UNIVERSAL_TOOLS: list[dict] = [
    {"type": "function", "function": {"name": "web_search", "description": "Search the web for current information", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "get_weather", "description": "Get current weather for a specific location", "parameters": {"type": "object", "properties": {"location": {"type": "string"}, "units": {"type": "string", "enum": ["celsius", "fahrenheit"]}}, "required": ["location"]}}},
    {"type": "function", "function": {"name": "calculator", "description": "Perform mathematical calculations", "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}},
    {"type": "function", "function": {"name": "send_email", "description": "Send an email to a recipient", "parameters": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}, "attachments": {"type": "array", "items": {"type": "string"}}}, "required": ["to", "subject", "body"]}}},
    {"type": "function", "function": {"name": "search_files", "description": "Search for files by name or content", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "file_type": {"type": "string", "enum": ["pdf", "docx", "xlsx", "any"]}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read the contents of a specific file", "parameters": {"type": "object", "properties": {"file_id": {"type": "string"}}, "required": ["file_id"]}}},
    {"type": "function", "function": {"name": "create_calendar_event", "description": "Create a new calendar event", "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "date": {"type": "string"}, "time": {"type": "string"}, "duration_minutes": {"type": "integer"}, "attendees": {"type": "array", "items": {"type": "string"}}}, "required": ["title", "date", "time"]}}},
    {"type": "function", "function": {"name": "get_contacts", "description": "Look up contacts by name or group", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "translate_text", "description": "Translate text from one language to another", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "source_language": {"type": "string"}, "target_language": {"type": "string"}}, "required": ["text", "source_language", "target_language"]}}},
    {"type": "function", "function": {"name": "get_stock_price", "description": "Get the current stock price for a ticker symbol", "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}}},
    {"type": "function", "function": {"name": "set_reminder", "description": "Set a reminder for a future time", "parameters": {"type": "object", "properties": {"message": {"type": "string"}, "datetime": {"type": "string"}}, "required": ["message", "datetime"]}}},
    {"type": "function", "function": {"name": "run_code", "description": "Execute a code snippet and return the output", "parameters": {"type": "object", "properties": {"language": {"type": "string", "enum": ["python", "javascript"]}, "code": {"type": "string"}}, "required": ["language", "code"]}}},
]

# ── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
    raw_arguments: str
    turn: int


@dataclass
class ScenarioState:
    tool_calls: list[ToolCall] = field(default_factory=list)
    assistant_messages: list[str] = field(default_factory=list)
    final_answer: str = ""
    meta: dict = field(default_factory=dict)


@dataclass
class Evaluation:
    status: str  # pass | partial | fail
    points: int  # 2 | 1 | 0
    summary: str


@dataclass
class ScenarioResult:
    scenario_id: str
    title: str
    category: str
    status: str
    points: int
    summary: str
    tool_calls_made: list[str] = field(default_factory=list)
    trace: str = ""
    latency_ms: int = 0
    error: str = ""


@dataclass
class CategoryScore:
    category: str
    label: str
    earned: int
    max_points: int = 6
    percent: int = 0


@dataclass
class ToolCallBenchResult:
    model: str
    provider: str
    scenario_results: list[ScenarioResult] = field(default_factory=list)
    category_scores: list[CategoryScore] = field(default_factory=list)
    final_score: int = 0
    total_points: int = 0
    max_points: int = 30
    rating: str = ""
    duration_s: float = 0
    ran_at: str = ""
    error: str = ""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _norm(s: Any) -> str:
    return str(s or "").strip().lower()


def _includes(val: Any, expected: str) -> bool:
    return expected.lower() in _norm(val)


def _has_call(state: ScenarioState, name: str, pred=None) -> bool:
    return any(
        c.name == name and (pred is None or pred(c))
        for c in state.tool_calls
    )


def _calls_by(state: ScenarioState, name: str) -> list[ToolCall]:
    return [c for c in state.tool_calls if c.name == name]


def _first(state: ScenarioState, name: str) -> ToolCall | None:
    for c in state.tool_calls:
        if c.name == name:
            return c
    return None


def _only_tool(state: ScenarioState, name: str) -> bool:
    return bool(state.tool_calls) and all(c.name == name for c in state.tool_calls)


def _answer_has_number(answer: str, val: str) -> bool:
    return val.replace(",", "").lower() in answer.replace(",", "").lower()


def _contains_refusal(answer: str) -> bool:
    low = answer.lower()
    return any(w in low for w in ("cannot", "can't", "do not have", "don't have", "not able"))


def _asks_clarification(answer: str) -> bool:
    low = answer.lower()
    return any(w in low for w in ("which", "clarify", "could you"))


def _as_str_list(val: Any) -> list[str]:
    if isinstance(val, list):
        return [str(x) for x in val]
    return []


def _safe_eval_math(expr: str) -> float | None:
    sanitized = expr.replace(",", "").strip()
    if not re.match(r'^[\d\s()+\-*/.%]+$', sanitized):
        return None
    try:
        result = eval(sanitized, {"__builtins__": {}}, {})  # noqa: S307
        return float(result) if isinstance(result, (int, float)) else None
    except Exception:
        return None


def _generic_fallback(call: ToolCall) -> dict:
    if call.name == "calculator":
        r = _safe_eval_math(str(call.arguments.get("expression", "")))
        return {"result": r} if r is not None else {"error": "Invalid expression."}
    if call.name == "web_search":
        return {"results": [{"snippet": f"Search results for {call.arguments.get('query', '')}"}]}
    return {"error": f"Tool {call.name} is not relevant for this scenario."}


# ── Scenario Definitions ─────────────────────────────────────────────────────

CATEGORY_LABELS = {
    "A": "Tool Selection",
    "B": "Parameter Precision",
    "C": "Multi-Step Chains",
    "D": "Restraint & Refusal",
    "E": "Error Recovery",
}


class Scenario:
    __slots__ = ("id", "title", "category", "user_message", "description")

    def __init__(self, id: str, title: str, category: str, user_message: str, description: str):
        self.id = id
        self.title = title
        self.category = category
        self.user_message = user_message
        self.description = description

    def handle_tool_call(self, state: ScenarioState, call: ToolCall) -> dict:
        return _generic_fallback(call)

    def evaluate(self, state: ScenarioState) -> Evaluation:
        return Evaluation("fail", 0, "Not implemented")


class TC01(Scenario):
    def __init__(self):
        super().__init__("TC-01", "Direct Specialist Match", "A", "What's the weather like in Berlin right now?", "Use get_weather instead of web_search.")

    def handle_tool_call(self, state, call):
        if call.name == "get_weather":
            return {"location": "Berlin", "temperature": 8, "units": "celsius", "condition": "Overcast", "humidity": 72}
        if call.name == "web_search":
            return {"results": [{"snippet": "Berlin weather right now: 8C and overcast."}]}
        return _generic_fallback(call)

    def evaluate(self, state):
        used_weather = _has_call(state, "get_weather", lambda c: _includes(c.arguments.get("location"), "berlin"))
        used_web = _has_call(state, "web_search")
        if used_weather and not used_web and len(state.tool_calls) == 1:
            return Evaluation("pass", 2, "Used get_weather with Berlin only.")
        if not used_weather and used_web and _only_tool(state, "web_search"):
            return Evaluation("partial", 1, "Functional via web_search, missed specialist tool.")
        return Evaluation("fail", 0, "Did not cleanly route to get_weather.")


class TC02(Scenario):
    def __init__(self):
        super().__init__("TC-02", "Distractor Resistance", "A", "What is the current price of AAPL stock?", "Use get_stock_price without extra tools.")

    def handle_tool_call(self, state, call):
        if call.name == "get_stock_price":
            return {"ticker": "AAPL", "price": 187.42, "currency": "USD", "change": "+1.23", "change_percent": "+0.66%"}
        if call.name == "web_search":
            return {"results": [{"snippet": "AAPL is trading around $187.42."}]}
        return _generic_fallback(call)

    def evaluate(self, state):
        stock = _has_call(state, "get_stock_price", lambda c: _norm(c.arguments.get("ticker")) == "aapl")
        web = _has_call(state, "web_search")
        if stock and not web and len(state.tool_calls) == 1:
            return Evaluation("pass", 2, "Used only get_stock_price for AAPL.")
        if stock and web:
            return Evaluation("partial", 1, "Right tool but added unnecessary web_search.")
        return Evaluation("fail", 0, "Did not isolate to get_stock_price.")


class TC03(Scenario):
    def __init__(self):
        super().__init__("TC-03", "Implicit Tool Need", "A", "I need to let Sarah know the meeting moved to 3pm.", "Infer get_contacts then send_email.")

    def handle_tool_call(self, state, call):
        if call.name == "get_contacts":
            return {"results": [{"name": "Sarah Chen", "email": "sarah.chen@company.com"}]}
        if call.name == "send_email":
            return {"status": "sent", "message_id": "msg_8821"}
        return _generic_fallback(call)

    def evaluate(self, state):
        contact = _first(state, "get_contacts")
        email = _first(state, "send_email")
        if (contact and email and contact.turn < email.turn
                and _includes(contact.arguments.get("query"), "sarah")
                and _norm(email.arguments.get("to")) == "sarah.chen@company.com"):
            return Evaluation("pass", 2, "Looked up Sarah before sending email.")
        if not contact and not email and re.search(r'email', state.final_answer, re.I) and '?' in state.final_answer:
            return Evaluation("partial", 1, "Asked for email instead of inferring chain.")
        return Evaluation("fail", 0, "Did not complete contact-to-email chain.")


class TC04(Scenario):
    def __init__(self):
        super().__init__("TC-04", "Unit Handling", "B", "What's the temperature in Tokyo in Fahrenheit?", "Pass units parameter correctly.")

    def handle_tool_call(self, state, call):
        if call.name == "get_weather":
            units = _norm(call.arguments.get("units")) or "celsius"
            if units == "fahrenheit":
                return {"location": "Tokyo", "temperature": 64, "units": "fahrenheit", "condition": "Clear"}
            return {"location": "Tokyo", "temperature": 18, "units": "celsius", "condition": "Clear"}
        return _generic_fallback(call)

    def evaluate(self, state):
        w = _first(state, "get_weather")
        if w and _includes(w.arguments.get("location"), "tokyo") and _norm(w.arguments.get("units")) == "fahrenheit":
            return Evaluation("pass", 2, "Requested Tokyo weather in Fahrenheit.")
        if w and _includes(w.arguments.get("location"), "tokyo") and (_answer_has_number(state.final_answer, "64") or "fahrenheit" in state.final_answer.lower()):
            return Evaluation("partial", 1, "Omitted units param, converted manually.")
        return Evaluation("fail", 0, "Did not preserve Fahrenheit instruction.")


class TC05(Scenario):
    def __init__(self):
        super().__init__("TC-05", "Date and Time Parsing", "B", "Schedule a team standup for next Monday at 9:30am, 30 minutes, with Alex and Jamie.", "Parse relative date and structured params.")

    def handle_tool_call(self, state, call):
        if call.name == "get_contacts":
            return {"results": [{"name": "Alex Stone", "email": "alex.stone@company.com"}, {"name": "Jamie Liu", "email": "jamie.liu@company.com"}]}
        if call.name == "create_calendar_event":
            return {"event_id": "evt_4412", "status": "created", "title": str(call.arguments.get("title", "Team Standup")), "date": str(call.arguments.get("date", ""))}
        return _generic_fallback(call)

    def evaluate(self, state):
        ev = _first(state, "create_calendar_event")
        if not ev:
            return Evaluation("fail", 0, "Did not create calendar event.")
        attendees = _as_str_list(ev.arguments.get("attendees", []))
        has_dur = ev.arguments.get("duration_minutes") == 30 or str(ev.arguments.get("duration_minutes")) == "30"
        has_att = any(_includes(a, "alex") for a in attendees) and any(_includes(a, "jamie") for a in attendees)
        ok_date = str(ev.arguments.get("date")) == "2026-03-23"
        ok_time = str(ev.arguments.get("time")) == "09:30"
        if ok_date and ok_time and has_dur and has_att:
            return Evaluation("pass", 2, "Parsed next Monday with all details.")
        if ok_date and ok_time:
            return Evaluation("partial", 1, "Date/time correct, missed some structure.")
        return Evaluation("fail", 0, "Relative date or time parsing incorrect.")


class TC06(Scenario):
    def __init__(self):
        super().__init__("TC-06", "Multi-Value Extraction", "B", "Translate 'Where is the nearest hospital?' from English to both Spanish and Japanese.", "Split into two translate_text calls.")

    def handle_tool_call(self, state, call):
        if call.name == "translate_text":
            tgt = _norm(call.arguments.get("target_language"))
            if tgt == "spanish":
                return {"translated": "\u00bfD\u00f3nde est\u00e1 el hospital m\u00e1s cercano?"}
            if tgt == "japanese":
                return {"translated": "\u6700\u5bc4\u308a\u306e\u75c5\u9662\u306f\u3069\u3053\u3067\u3059\u304b\uff1f"}
            return {"error": f"Unsupported target language {tgt}."}
        return _generic_fallback(call)

    def evaluate(self, state):
        calls = _calls_by(state, "translate_text")
        has_es = any(_norm(c.arguments.get("target_language")) == "spanish" for c in calls)
        has_ja = any(_norm(c.arguments.get("target_language")) == "japanese" for c in calls)
        bundled = any(re.search(r'spanish.*japanese|japanese.*spanish', str(c.arguments.get("target_language", "")), re.I) for c in calls)
        if len(calls) >= 2 and has_es and has_ja and not bundled:
            return Evaluation("pass", 2, "Issued separate calls for both languages.")
        return Evaluation("fail", 0, "Did not split into two valid translate calls.")


class TC07(Scenario):
    def __init__(self):
        super().__init__("TC-07", "Search-Read-Act", "C", "Find the Q3 budget report and email the total to my manager.", "Thread search, read, contacts, email.")

    def handle_tool_call(self, state, call):
        if call.name == "search_files":
            return {"results": [{"file_id": "file_091", "name": "Q3_Budget_Report_2025.xlsx"}]}
        if call.name == "read_file":
            return {"content": "Department budgets: Engineering $2.1M, Marketing $800K, Sales $1.5M. Total: $4.4M"}
        if call.name == "get_contacts":
            return {"results": [{"name": "Jordan Park", "email": "jordan.park@company.com", "role": "manager"}]}
        if call.name == "send_email":
            return {"status": "sent"}
        return _generic_fallback(call)

    def evaluate(self, state):
        steps = 0
        if _has_call(state, "search_files", lambda c: _includes(c.arguments.get("query"), "q3") or _includes(c.arguments.get("query"), "budget")):
            steps += 1
        if _has_call(state, "read_file", lambda c: _norm(c.arguments.get("file_id")) == "file_091"):
            steps += 1
        if _has_call(state, "get_contacts", lambda c: _includes(c.arguments.get("query"), "manager")):
            steps += 1
        if _has_call(state, "send_email", lambda c: _norm(c.arguments.get("to")) == "jordan.park@company.com" and (_includes(c.arguments.get("body"), "4.4") or _includes(c.arguments.get("subject"), "4.4"))):
            steps += 1
        if steps == 4:
            return Evaluation("pass", 2, "Completed full four-step chain with correct data.")
        if steps >= 3:
            return Evaluation("partial", 1, "Completed most of chain, missed one step.")
        return Evaluation("fail", 0, "Did not carry data across chain correctly.")


class TC08(Scenario):
    def __init__(self):
        super().__init__("TC-08", "Conditional Branching", "C", "Check the weather in Paris. If it's raining, remind me to bring an umbrella tomorrow at 8am.", "Branch off weather result.")

    def handle_tool_call(self, state, call):
        if call.name == "get_weather":
            return {"location": "Paris", "temperature": 11, "condition": "Light rain", "humidity": 89}
        if call.name == "set_reminder":
            return {"reminder_id": "rem_553", "status": "set"}
        return _generic_fallback(call)

    def evaluate(self, state):
        w = _first(state, "get_weather")
        r = _first(state, "set_reminder")
        if (w and r and w.turn < r.turn
                and _includes(r.arguments.get("message"), "umbrella")
                and str(r.arguments.get("datetime", "")).startswith("2026-03-21T08:00")):
            return Evaluation("pass", 2, "Checked weather first, then set rain reminder.")
        if w and not r and _asks_clarification(state.final_answer):
            return Evaluation("partial", 1, "Read weather correctly but stopped short.")
        return Evaluation("fail", 0, "Did not respect weather-first conditional flow.")


class TC09(Scenario):
    def __init__(self):
        super().__init__("TC-09", "Parallel Independence", "C", "What's the weather in London and the stock price of MSFT?", "Handle two independent requests.")

    def handle_tool_call(self, state, call):
        if call.name == "get_weather":
            return {"location": "London", "temperature": 12, "condition": "Cloudy"}
        if call.name == "get_stock_price":
            return {"ticker": "MSFT", "price": 412.78, "currency": "USD"}
        if call.name == "web_search":
            return {"results": [{"snippet": "London is cloudy at 12C and MSFT is around $412.78."}]}
        return _generic_fallback(call)

    def evaluate(self, state):
        w = _has_call(state, "get_weather", lambda c: _includes(c.arguments.get("location"), "london"))
        s = _has_call(state, "get_stock_price", lambda c: _norm(c.arguments.get("ticker")) == "msft")
        if w and s:
            t1 = [c for c in state.tool_calls if c.turn == 1]
            parallel = any(c.name == "get_weather" for c in t1) and any(c.name == "get_stock_price" for c in t1)
            return Evaluation("pass", 2, f"Handled both tasks.{' (parallel)' if parallel else ''}")
        if _has_call(state, "web_search"):
            return Evaluation("partial", 1, "Covered request via web_search fallback.")
        return Evaluation("fail", 0, "Missed one side of two-part request.")


class TC10(Scenario):
    def __init__(self):
        super().__init__("TC-10", "Trivial Knowledge", "D", "What year did World War II end?", "Avoid tools for basic knowledge.")

    def evaluate(self, state):
        if not state.tool_calls and _answer_has_number(state.final_answer, "1945"):
            return Evaluation("pass", 2, "Answered directly without tool use.")
        return Evaluation("fail", 0, "Used tools or missed basic fact.")


class TC11(Scenario):
    def __init__(self):
        super().__init__("TC-11", "Simple Math", "D", "What is 15% of 200?", "Avoid calculator for easy arithmetic.")

    def evaluate(self, state):
        correct = _answer_has_number(state.final_answer, "30")
        if not state.tool_calls and correct:
            return Evaluation("pass", 2, "Did the math directly.")
        if _has_call(state, "calculator") and correct and not _has_call(state, "web_search"):
            return Evaluation("partial", 1, "Used calculator correctly but unnecessarily.")
        return Evaluation("fail", 0, "Failed easy-arithmetic restraint test.")


class TC12(Scenario):
    def __init__(self):
        super().__init__("TC-12", "Impossible Request", "D", "Delete all my emails from last month.", "Refuse when no suitable tool exists.")

    def evaluate(self, state):
        if (not state.tool_calls and _contains_refusal(state.final_answer)
                and (re.search(r'delete', state.final_answer, re.I) or re.search(r'available tool', state.final_answer, re.I))):
            return Evaluation("pass", 2, "Refused cleanly — no delete tool exists.")
        return Evaluation("fail", 0, "Did not refuse unsupported request correctly.")


class TC13(Scenario):
    def __init__(self):
        super().__init__("TC-13", "Empty Results", "E", "Find the Johnson proposal document.", "Retry or clarify after empty results.")

    def handle_tool_call(self, state, call):
        if call.name == "search_files":
            q = _norm(call.arguments.get("query"))
            attempts = state.meta.get("search_attempts", 0) + 1
            state.meta["search_attempts"] = attempts
            if "johnson proposal" in q and attempts == 1:
                return {"results": []}
            if "johnson" in q:
                return {"results": [{"file_id": "file_117", "name": "Johnson_Project_Proposal_v2.docx"}]}
        return _generic_fallback(call)

    def evaluate(self, state):
        searches = _calls_by(state, "search_files")
        if len(searches) >= 2:
            return Evaluation("pass", 2, "Retried after empty result and recovered.")
        if len(searches) == 1 and _asks_clarification(state.final_answer):
            return Evaluation("pass", 2, "Asked for clarification after empty result.")
        return Evaluation("fail", 0, "Did not adapt after empty search.")


class TC14(Scenario):
    def __init__(self):
        super().__init__("TC-14", "Malformed Response", "E", "What's Apple's stock price?", "Surface tool errors instead of hallucinating.")

    def handle_tool_call(self, state, call):
        if call.name == "get_stock_price":
            return {"error": "Service temporarily unavailable. Rate limit exceeded."}
        if call.name == "web_search":
            return {"results": [{"snippet": "Apple (AAPL) is trading around $187.42."}]}
        return _generic_fallback(call)

    def evaluate(self, state):
        stock_calls = _calls_by(state, "get_stock_price")
        used_web = _has_call(state, "web_search")
        ack = bool(re.search(r'temporarily unavailable|rate limit|service|error', state.final_answer, re.I))
        if stock_calls and ack:
            return Evaluation("pass", 2, "Acknowledged stock tool failure gracefully.")
        if stock_calls and used_web:
            return Evaluation("partial", 1, "Recovered with web_search but didn't surface error.")
        return Evaluation("fail", 0, "Did not handle tool error with integrity.")


class TC15(Scenario):
    def __init__(self):
        super().__init__("TC-15", "Conflicting Information", "E", "Search for the population of Iceland and calculate what 2% of it would be.", "Carry exact searched value into calculator.")

    def handle_tool_call(self, state, call):
        if call.name == "web_search":
            return {"results": [{"snippet": "Iceland has a population of approximately 372,520 as of 2025."}]}
        if call.name == "calculator":
            r = _safe_eval_math(str(call.arguments.get("expression", "")))
            return {"result": r} if r is not None else {"error": "Invalid expression."}
        return _generic_fallback(call)

    def evaluate(self, state):
        search = _first(state, "web_search")
        calc = _first(state, "calculator")
        if (search and calc
                and _includes(search.arguments.get("query"), "population")
                and "372520" in str(calc.arguments.get("expression", "")).replace(",", "")):
            return Evaluation("pass", 2, "Used searched population value in calculator.")
        if not calc and search and _answer_has_number(state.final_answer, "7450"):
            return Evaluation("partial", 1, "Computed right answer mentally after search.")
        return Evaluation("fail", 0, "Did not preserve exact searched value across calls.")


SCENARIOS: list[Scenario] = [TC01(), TC02(), TC03(), TC04(), TC05(), TC06(), TC07(), TC08(), TC09(), TC10(), TC11(), TC12(), TC13(), TC14(), TC15()]


# ── Orchestrator ─────────────────────────────────────────────────────────────

async def _run_scenario(scenario: Scenario, model: str, provider: str, tool_choice: str = "auto") -> ScenarioResult:
    """Run one scenario against the LLM with multi-turn tool loop."""
    from ..llm.client import get_llm_client, LLMMessage

    client = get_llm_client()
    state = ScenarioState()
    trace_lines: list[str] = []

    messages: list[LLMMessage] = [
        LLMMessage(role="system", content=SYSTEM_PROMPT),
        LLMMessage(role="user", content=f"[Context: {BENCHMARK_CONTEXT}]\n\n{scenario.user_message}"),
    ]

    t0 = time.monotonic()
    try:
        for turn in range(1, MAX_TURNS + 1):
            # Restraint scenarios (D) should always use "auto" to test if model avoids tools
            effective_choice = "auto" if scenario.category == "D" else tool_choice
            # Use temperature=0.01 (not 0) to bust LLM cache which doesn't key on tool_choice
            bench_temp = 0.01 if tool_choice != "auto" else 0
            resp = await client.chat(
                messages=messages,
                model=model,
                provider=provider,
                temperature=bench_temp,
                tools=UNIVERSAL_TOOLS,
                tool_choice=effective_choice,
            )

            content = resp.content or ""
            state.assistant_messages.append(content)
            trace_lines.append(f"turn_{turn}: {content[:200] or '[tool_calls]'}")

            # Build assistant message for history
            assistant_msg = LLMMessage(role="assistant", content=content)
            if resp.tool_calls:
                assistant_msg.tool_calls = resp.tool_calls
            messages.append(assistant_msg)

            if not resp.tool_calls:
                state.final_answer = content
                break

            # Process tool calls (LLMToolCall dataclass: .id, .function_name, .arguments)
            for tc in resp.tool_calls:
                tc_id = tc.id if hasattr(tc, "id") else tc.get("id", f"call_{turn}")
                name = tc.function_name if hasattr(tc, "function_name") else tc.get("function", {}).get("name", "")
                args = tc.arguments if hasattr(tc, "arguments") else {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        args = {}

                record = ToolCall(id=tc_id, name=name, arguments=args, raw_arguments=str(raw_args), turn=turn)
                state.tool_calls.append(record)
                trace_lines.append(f"  tool: {name}({json.dumps(args, ensure_ascii=False)[:200]})")

                # Execute mock
                result = scenario.handle_tool_call(state, record)
                trace_lines.append(f"  result: {json.dumps(result, ensure_ascii=False)[:200]}")

                messages.append(LLMMessage(
                    role="tool",
                    content=json.dumps(result, ensure_ascii=False),
                    tool_call_id=tc_id,
                ))

        if not state.final_answer and state.assistant_messages:
            state.final_answer = state.assistant_messages[-1]

    except Exception as e:
        logger.warning("ToolCall-15 scenario %s error: %s", scenario.id, e)
        return ScenarioResult(
            scenario_id=scenario.id, title=scenario.title, category=scenario.category,
            status="fail", points=0, summary=str(e), error=str(e),
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    elapsed = int((time.monotonic() - t0) * 1000)
    ev = scenario.evaluate(state)
    return ScenarioResult(
        scenario_id=scenario.id, title=scenario.title, category=scenario.category,
        status=ev.status, points=ev.points, summary=ev.summary,
        tool_calls_made=[c.name for c in state.tool_calls],
        trace="\n".join(trace_lines), latency_ms=elapsed,
    )


def _score(results: list[ScenarioResult]) -> tuple[list[CategoryScore], int, str]:
    cat_scores = []
    for cat, label in CATEGORY_LABELS.items():
        earned = sum(r.points for r in results if r.category == cat)
        pct = round((earned / 6) * 100)
        cat_scores.append(CategoryScore(category=cat, label=label, earned=earned, percent=pct))
    final = round(sum(cs.percent for cs in cat_scores) / len(cat_scores))
    if final >= 90:
        rating = "Excellent"
    elif final >= 75:
        rating = "Good"
    elif final >= 60:
        rating = "Adequate"
    elif final >= 40:
        rating = "Weak"
    else:
        rating = "Poor"
    return cat_scores, final, rating


async def run_toolcall_bench(
    model: str,
    provider: str,
    scenario_ids: list[str] | None = None,
    tool_choice: str = "auto",
) -> ToolCallBenchResult:
    """Run ToolCall-15 benchmark against a specific model/provider.

    tool_choice: "auto" (default, strict ToolCall-15 spec) or "required" (force tool use).
    Category D (Restraint) always uses "auto" regardless of this setting.
    """
    import datetime

    scenarios = SCENARIOS
    if scenario_ids:
        id_set = set(scenario_ids)
        scenarios = [s for s in SCENARIOS if s.id in id_set]

    t0 = time.monotonic()
    results: list[ScenarioResult] = []

    for scenario in scenarios:
        logger.info("ToolCall-15: running %s (%s) on %s/%s (tool_choice=%s)", scenario.id, scenario.title, provider, model, tool_choice)
        r = await _run_scenario(scenario, model, provider, tool_choice=tool_choice)
        results.append(r)
        logger.info("  → %s (%d pts): %s", r.status, r.points, r.summary)

    cat_scores, final, rating = _score(results)
    total_pts = sum(r.points for r in results)

    bench = ToolCallBenchResult(
        model=model, provider=provider,
        scenario_results=results, category_scores=cat_scores,
        final_score=final, total_points=total_pts, max_points=len(scenarios) * 2,
        rating=rating, duration_s=round(time.monotonic() - t0, 1),
        ran_at=datetime.datetime.now(datetime.UTC).isoformat(),
    )

    # Persist result
    _save_result(bench)
    return bench


async def run_all_providers() -> list[ToolCallBenchResult]:
    """Run ToolCall-15 against all configured providers."""
    from ..llm.client import PROVIDERS
    from ..agents.store import DEFAULT_PROVIDER, DEFAULT_MODEL

    results = []
    # Primary provider
    r = await run_toolcall_bench(DEFAULT_MODEL, DEFAULT_PROVIDER)
    results.append(r)

    # Other providers with valid keys
    import os
    for pid, cfg in PROVIDERS.items():
        if pid == DEFAULT_PROVIDER:
            continue
        key_env = cfg.get("key_env")
        if key_env and not os.environ.get(key_env):
            continue
        model = cfg.get("default", "")
        if not model:
            continue
        try:
            r = await run_toolcall_bench(model, pid)
            results.append(r)
        except Exception as e:
            logger.warning("ToolCall-15 skip %s: %s", pid, e)

    return results


def _save_result(bench: ToolCallBenchResult) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    key = f"{bench.provider}_{bench.model}".replace("/", "_").replace(" ", "_")
    path = RESULTS_DIR / f"{key}.json"
    import dataclasses
    path.write_text(json.dumps(dataclasses.asdict(bench), indent=2, default=str, ensure_ascii=False))
    logger.info("ToolCall-15 result saved: %s (score=%d%% %s)", path.name, bench.final_score, bench.rating)


def load_results() -> list[dict]:
    """Load all stored ToolCall-15 results."""
    if not RESULTS_DIR.exists():
        return []
    results = []
    for f in sorted(RESULTS_DIR.glob("*.json")):
        try:
            results.append(json.loads(f.read_text()))
        except Exception:
            pass
    return results
