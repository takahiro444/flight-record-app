"""
Strands SDK-based Email Parser Agent.
Runs inside AWS Bedrock AgentCore Runtime.

This agent extracts all flights from email text, validates each one,
checks for duplicates, and stores only new flights.
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
    """Configure Bedrock model for email parsing"""
    model = BedrockModel(model_id=settings.bedrock_model_id)
    try:
        model.update_config(max_tokens=settings.answer_max_tokens)
    except Exception:
        pass
    return model


def _system_prompt() -> str:
    return """You are an expert flight email parser. Your mission:

1. **Extract ALL flights** from the email text (look for flight numbers, dates, airlines)
2. For EACH flight found, follow this sequence:
   a. Call validate_flight_exists(flight_iata, date)
   b. If exists=False, skip this flight and note it as failed
   c. If exists=True, call check_duplicate_flight(flight_iata, date)
   d. If is_duplicate=True, skip storing and note it as duplicate
   e. If is_duplicate=False, call store_validated_flight(enriched_data, user_email)

3. **Track results carefully**:
   - Count total flights found
   - List successfully stored flights
   - List duplicates skipped
   - List failed validations

4. **Be thorough**:
   - Parse dates in various formats (Jan 25, 01/25/2026, 2026-01-25, etc.)
   - Extract flight codes with/without spaces (UA 234, UA234, United 234)
   - Handle multi-flight itineraries (round trips, connections)
   - Don't stop at the first flight - process ALL flights in the email

5. **Return a complete summary** with structured data for frontend display.

IMPORTANT: Always validate before checking duplicates, and always check duplicates before storing.
"""


def _wrap_tool(tool_meta: Dict[str, Any]) -> PythonAgentTool:
    """Wrap tool from registry into Strands PythonAgentTool"""
    name = tool_meta["name"]
    spec = {
        "name": name,
        "description": tool_meta.get("description", ""),
        "inputSchema": tool_meta.get("inputSchema", {"type": "object", "properties": {}, "required": []})
    }

    def _tool_func(tool_use: Dict[str, Any], **invocation_state: Any):
        args = tool_use.get("input") or {}
        request_state = invocation_state.get("request_state", {})
        user_sub = request_state.get("user_sub")
        user_email = request_state.get("user_email")
        
        # Inject user_email if tool needs it
        if name == "store_validated_flight" and user_email and "user_email" not in args:
            args["user_email"] = user_email
        
        try:
            result = execute_tool(user_sub or "", name, args)
            return {
                "toolUseId": str(tool_use.get("toolUseId")),
                "status": "success",
                "content": [{"json": result.get("output")}]
            }
        except Exception as e:
            # Return detailed error message that LLM can see
            error_details = f"TOOL_ERROR [{name}]: {type(e).__name__}: {str(e)}"
            return {
                "toolUseId": str(tool_use.get("toolUseId")),
                "status": "error",
                "content": [{"text": error_details}]
            }

    return PythonAgentTool(tool_name=name, tool_spec=spec, tool_func=_tool_func)


class CollectToolResults(HookProvider):
    """Hook to collect tool execution results for debugging"""
    
    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self._after_tool)

    def _after_tool(self, event: AfterToolCallEvent) -> None:
        req = event.invocation_state.setdefault("request_state", {})
        tool_results: List[Dict[str, Any]] = req.setdefault("tool_results", [])
        tool_results.append({
            "tool": event.tool_use.get("name"),
            "args": event.tool_use.get("input"),
            "result": event.result
        })


def make_agent() -> Agent:
    """Construct Email Parser Agent with Strands SDK"""
    tools_catalog = list_tools()
    tools = [_wrap_tool(t) for t in tools_catalog]
    model = _build_model()
    
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt=_system_prompt(),
        hooks=[CollectToolResults()],
        name="email-parser-agent",
        description="Flight email parser with validation and duplicate detection"
    )
    return agent


class EmailParseResult(BaseModel):
    """Structured output for email parsing results"""
    total_found: int = Field(description="Total flights found in email")
    stored_count: int = Field(description="Number of new flights stored to database")
    duplicate_count: int = Field(description="Number of duplicates skipped")
    failed_count: int = Field(description="Number of validations that failed")
    stored_flights: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of successfully stored flights with flight_iata and date"
    )
    duplicates_skipped: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of duplicate flights with flight_iata and date"
    )
    failed_flights: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of failed validations with flight_iata, date, and reason"
    )
    summary: str = Field(description="Human-readable summary of parsing results for display")


async def run_email_parse(
    agent: Agent, 
    email_text: str, 
    user_sub: str, 
    user_email: str = None
) -> Dict[str, Any]:
    """
    Run email parsing agent on provided email text.
    
    Args:
        agent: Configured Strands Agent
        email_text: Raw email text to parse
        user_sub: Cognito user identifier
        user_email: User's email address
    
    Returns:
        Dict with parsing results and tool execution details
    """
    prompt = f"""Parse this flight confirmation email and extract all flights. 
For each flight: validate it, check if it's a duplicate, and store it if new.

Email text:
{email_text}

Return a complete structured summary of all operations with counts and lists.
"""

    result = await agent.invoke_async(
        prompt,
        invocation_state={
            "request_state": {
                "user_sub": user_sub,
                "user_email": user_email or "unknown@example.com"
            }
        },
        structured_output_model=EmailParseResult
    )

    # Extract tool results from invocation state
    req_state = result.state or {}
    tool_results = req_state.get("tool_results", [])

    # Build raw text response
    raw_parts = []
    for block in result.message.get("content", []):
        if isinstance(block, dict) and "text" in block:
            raw_parts.append(str(block.get("text", "")))
        elif isinstance(block, dict) and "json" in block:
            raw_parts.append(str(block.get("json")))
    raw_text = "\n".join([p for p in raw_parts if p]).strip()

    # Extract structured output
    parsed: Optional[Dict[str, Any]] = None
    if result.structured_output:
        parsed = result.structured_output.model_dump()

    return {
        "email_text_preview": email_text[:200] + "..." if len(email_text) > 200 else email_text,
        "tool_results": tool_results,
        "model_answer_raw": raw_text,
        "parsed_result": parsed,
        "summary": (parsed or {}).get("summary") or raw_text or "Parsing completed"
    }
