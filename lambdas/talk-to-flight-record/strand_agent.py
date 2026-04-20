"""Strands SDK-based Agent for flight-record backend.

This module defines a Strands Agent that wraps existing DB tools and integrates
with Bedrock for planning/execution. It exposes a helper to construct the agent
and utilities to run it and format results for the existing API envelope.
"""

import asyncio
from typing import Any, Dict, List, Optional

from strands.agent import Agent
from strands.models import BedrockModel
from strands.tools import PythonAgentTool
from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import AfterToolCallEvent
from pydantic import BaseModel, Field

from config import settings
from tools import list_tools, execute_tool


def _build_model() -> BedrockModel:
    """Configure Bedrock model for the agent using settings.

    Returns:
        BedrockModel: Configured Bedrock model instance.
    """
    # Minimal config: model_id from settings; SDK supports additional config via update_config.
    model = BedrockModel(model_id=settings.bedrock_model_id)
    # Apply sensible defaults from settings to keep outputs concise
    try:
        model.update_config(max_tokens=settings.answer_max_tokens)
    except Exception:
        # Some SDK versions may not support update_config; continue with defaults
        pass
    return model


def _system_prompt() -> str:
    return (
        "You are a flight record insights assistant. "
        "Use ONLY the available tools to retrieve user-scoped data. "
        "Respond concisely and include a JSON object with keys 'answer' and 'numbers'."
    )


def _wrap_tool(tool_meta: Dict[str, Any]) -> PythonAgentTool:
    """Create a Strands PythonAgentTool from existing tool registry entry.

    Args:
        tool_meta: Dict containing 'name', 'description', and 'inputSchema'.

    Returns:
        PythonAgentTool instance that executes the existing runner via execute_tool.
    """
    name = tool_meta["name"]
    spec = {
        "name": name,
        "description": tool_meta.get("description", ""),
        "inputSchema": tool_meta.get("inputSchema", {"type": "object", "properties": {}, "required": []}),
    }

    def _tool_func(tool_use: Dict[str, Any], **invocation_state: Any):
        # Extract args and user_sub from invocation_state.request_state
        args = tool_use.get("input") or {}
        request_state = invocation_state.get("request_state", {})
        user_sub = request_state.get("user_sub")
        try:
            result = execute_tool(user_sub or "", name, args)
            return {
                "toolUseId": str(tool_use.get("toolUseId")),
                "status": "success",
                # Keep content minimal and machine-parseable; planner can add text if needed
                "content": [
                    {"json": result.get("output")},
                ],
            }
        except Exception as e:
            return {
                "toolUseId": str(tool_use.get("toolUseId")),
                "status": "error",
                "content": [
                    {"text": f"Error executing {name}: {e}"},
                ],
            }

    return PythonAgentTool(tool_name=name, tool_spec=spec, tool_func=_tool_func)


class CollectToolResults(HookProvider):
    """Hook provider to collect tool results and plan steps during agent run."""

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self._after_tool)

    def _after_tool(self, event: AfterToolCallEvent) -> None:
        # Attach tool result and the tool call to request_state for later retrieval
        req = event.invocation_state.setdefault("request_state", {})
        tool_results: List[Dict[str, Any]] = req.setdefault("tool_results", [])
        # Store a simplified result including tool name and raw ToolResult
        tool_results.append({
            "tool": event.tool_use.get("name"),
            "args": event.tool_use.get("input"),
            "result": event.result,
        })
        plan_steps: List[Dict[str, Any]] = req.setdefault("plan_steps", [])
        plan_steps.append({"tool": event.tool_use.get("name"), "args": event.tool_use.get("input")})


def make_agent() -> Agent:
    """Construct and return a Strands Agent ready to serve flight-record queries."""
    tools_catalog = list_tools()
    tools = [_wrap_tool(t) for t in tools_catalog]
    model = _build_model()
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt=_system_prompt(),
        hooks=[CollectToolResults()],
        name="flight-record-agent",
        description="Flight record insights agent using Strands SDK",
    )
    return agent


class AnswerOut(BaseModel):
    """Structured output schema for the agent's final answer."""
    answer: str = Field(description="Concise natural language answer")
    numbers: Dict[str, float] = Field(default_factory=dict, description="Aggregated numeric metrics")


async def run_agent_question(agent: Agent, question: str, user_sub: str) -> Dict[str, Any]:
    """Run the agent with a question and return a response envelope.

    Args:
        agent: Constructed Strands Agent.
        question: User's natural language prompt.
        user_sub: Cognito subject for scoping tools.

    Returns:
        Dict with keys: question, plan, tool_results, model_answer_raw, parsed_answer (optional None).
    """
    # Pass user_sub via request_state so tool funcs can access it
    # Request structured output; SDK will enforce formatting
    result = await agent.invoke_async(
        question,
        invocation_state={"request_state": {"user_sub": user_sub}},
        structured_output_model=AnswerOut,
    )

    # Build raw answer text (include text blocks; fall back to json blocks stringified)
    raw_parts = []
    for block in result.message.get("content", []):
        if isinstance(block, dict) and "text" in block:
            raw_parts.append(str(block.get("text", "")))
        elif isinstance(block, dict) and "json" in block:
            raw_parts.append(str(block.get("json")))
    raw_text = "\n".join([p for p in raw_parts if p]).strip()

    # Collect tool_results and plan_steps from request_state
    req_state = result.state or {}
    tool_results = req_state.get("tool_results", [])
    plan_steps = req_state.get("plan_steps", [])

    parsed: Optional[Dict[str, Any]] = None
    if result.structured_output:
        parsed = result.structured_output.model_dump()

    # Prefer structured answer; fall back to raw text
    answer_text = (parsed or {}).get("answer") or raw_text or "No answer produced; see tool_results"
    numbers = (parsed or {}).get("numbers") or {}

    return {
        "question": question,
        "plan": {"steps": plan_steps},
        "tool_results": tool_results,
        "model_answer_raw": raw_text,
        "parsed_answer": parsed,
        "answer": answer_text,
        "numbers": numbers,
    }
