"""Tool registry for the Strands SDK agent.

This module defines a simple, explicit registry mapping tool names to:
- description: Human-readable purpose
- inputSchema: JSON Schema describing the tool's expected inputs
- runner(user_sub, args): Callable implementing the tool logic, returning any serializable result

How the agent uses these:
- Our Strands agent wraps each entry via `PythonAgentTool` (see `strand_agent._wrap_tool`).
- No decorators like `@Tool` are required; we provide the `tool_spec` (name, description, inputSchema)
  and a Python function to execute. The SDK handles planning and tool invocation.

Adding a new tool:
1) Implement or import a runner function with signature `(user_sub: str, args: Dict[str, Any]) -> Any`.
2) Add a new entry to `_TOOL_REGISTRY` with `name`, `description`, `inputSchema`, and `runner`.
3) The agent will automatically pick it up via `list_tools()`; no changes needed in `strand_agent.py`.

Example skeleton:
    def total_mileage(user_sub: str, year: int) -> Dict[str, Any]:
        # ... your logic here ...
        return {"year": year, "total_miles": 12345}

    _TOOL_REGISTRY["total_mileage"] = {
        "description": "Total mileage for a given year.",
        "inputSchema": {
            "type": "object",
            "properties": {"year": {"type": "integer", "minimum": 2000}},
            "required": ["year"],
        },
        "runner": lambda user_sub, args: total_mileage(user_sub, int(args["year"]))
    }

Notes:
- Keep `inputSchema` strict and numeric fields typed to avoid LLM miscasting.
- For tools that don't need inputs, use an empty schema: `{ "type": "object", "properties": {}, "required": [] }`.
"""

from typing import Dict, Any, Callable, List
from db import mileage_range, monthly_summary, longest_flights, stats_overview, recent_flights, list_flight_record_columns, get_db_settings
from config import settings

class ToolError(Exception):
    pass

# Each tool entry: name -> {"description": str, "schema": {...}, "runner": callable}

_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "query_mileage_range": {
        "description": "Aggregate mileage and flight count for date range [start_date, end_date).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                "end_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            },
            "required": ["start_date", "end_date"],
        },
        "runner": lambda user_sub, args: mileage_range(user_sub, args["start_date"], args["end_date"]),
    },
    "monthly_mileage_summary": {
        "description": "Monthly mileage & flight counts for a given year.",
        "inputSchema": {
            "type": "object",
            "properties": {"year": {"type": "integer", "minimum": 2000}},
            "required": ["year"],
        },
        "runner": lambda user_sub, args: monthly_summary(user_sub, int(args["year"])),
    },
    "longest_flights": {
        "description": "Top flights by mileage, optional date bounds.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                "start_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                "end_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            },
            "required": [],
        },
        "runner": lambda user_sub, args: longest_flights(
            user_sub,
            int(args.get("limit", 5)),
            args.get("start_date"),
            args.get("end_date"),
        ),
    },
    "stats_overview": {
        "description": "High-level stats: first/last flight dates, totals, averages.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "runner": lambda user_sub, args: stats_overview(user_sub),
    },
    "recent_flights": {
        "description": "Most recent flights (ingestion schema) for the user.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": [],
        },
        "runner": lambda user_sub, args: recent_flights(user_sub, int(args.get("limit", 10))),
    },
    "diagnose_table_columns": {
        "description": "List columns in flight_record to diagnose schema mismatches.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "runner": lambda user_sub, args: list_flight_record_columns(),
    },
    "diagnose_db_settings": {
        "description": "Show key PostgreSQL settings and connection details.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "runner": lambda user_sub, args: get_db_settings(),
    },
}


def list_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": name,
            "description": meta["description"],
            "inputSchema": meta["inputSchema"],
        }
        for name, meta in _TOOL_REGISTRY.items()
    ]


def get_tool(name: str) -> Dict[str, Any]:
    if name not in _TOOL_REGISTRY:
        raise ToolError(f"Unknown tool: {name}")
    return _TOOL_REGISTRY[name]


def execute_tool(user_sub: str, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    tool = get_tool(name)
    runner = tool["runner"]
    result = runner(user_sub, args)
    return {"tool": name, "output": result}
