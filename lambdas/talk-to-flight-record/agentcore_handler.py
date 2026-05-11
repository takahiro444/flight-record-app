"""
Lambda entry point for Bedrock AgentCore Action Group.

The Bedrock Agent will invoke this function with an event containing:
- operation (operationId from the action group schema)
- parameters (list of name/value items)
- requestBody (optional JSON payload)
- sessionAttributes / promptSessionAttributes (carry user_sub)

This handler routes operationId -> tools.py runners and returns the result
in the AgentCore response envelope.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Tuple

from tools import execute_tool

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class ActionGroupError(Exception):
    pass


def _extract_user_sub(event: Dict[str, Any], args: Dict[str, Any]) -> str | None:
    """Pull user_sub from session/prompt attributes only.

    The proxy populates sessionAttributes.user_sub from the verified Cognito JWT
    claim before invoking the agent. LLM-supplied tool args are untrusted (the
    model could be prompt-injected) and must never be a source of identity.
    """
    session = event.get("sessionAttributes", {}) or {}
    prompt = event.get("promptSessionAttributes", {}) or {}
    return session.get("user_sub") or prompt.get("user_sub")


def _gather_args(event: Dict[str, Any]) -> Tuple[str | None, Dict[str, Any]]:
    # Parameters can arrive as a list: [{"name": "year", "value": "2025"}, ...]
    # OR in new format: requestBody.content.application/json.properties
    params = event.get("parameters") or []
    args: Dict[str, Any] = {}
    
    # Handle old format parameters
    for item in params:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name:
            continue
        # Bedrock may provide one of several value keys
        val = (
            item.get("value")
            or item.get("stringValue")
            or item.get("booleanValue")
            or item.get("numberValue")
        )
        args[name] = val

    # requestBody content may carry JSON string or already-parsed dict
    body = event.get("requestBody") or {}
    try:
        app_json = body.get("content", {}).get("application/json")
        if app_json:
            # New format: properties is a list
            properties = app_json.get("properties")
            if isinstance(properties, list):
                for prop in properties:
                    if isinstance(prop, dict):
                        name = prop.get("name")
                        val = prop.get("value")
                        if name:
                            args[name] = val
            else:
                # Old format: value is JSON string or dict
                body_val = app_json.get("value")
                if isinstance(body_val, str):
                    try:
                        args.update(json.loads(body_val))
                    except Exception:
                        pass
                elif isinstance(body_val, dict):
                    args.update(body_val)
    except Exception:
        pass

    user_sub = _extract_user_sub(event, args)
    return user_sub, args


def _build_response(event: Dict[str, Any], body: Dict[str, Any], session: Dict[str, Any], prompt_session: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup", ""),
            "apiPath": event.get("apiPath", ""),
            "httpMethod": event.get("httpMethod", "POST"),
            "httpStatusCode": 200,
            "responseBody": {
                "application/json": {
                    "body": json.dumps(body)
                }
            }
        },
        "sessionAttributes": session,
        "promptSessionAttributes": prompt_session,
    }


def lambda_handler(event, context):  # type: ignore[override]
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Fail fast on missing operation
    # Support both old (operationId) and new (apiPath) formats
    operation = event.get("operation") or event.get("operationId")
    if not operation:
        # New format uses apiPath like "/stats_overview"
        api_path = event.get("apiPath", "")
        operation = api_path.lstrip("/") if api_path else None
    
    if not operation:
        logger.error(f"Missing operationId in event")
        return _build_response(
            event,
            {"error": "missing operationId", "event": str(event)[:2000]},
            event.get("sessionAttributes", {}) or {},
            event.get("promptSessionAttributes", {}) or {},
        )

    user_sub, args = _gather_args(event)
    logger.info(f"Operation: {operation}, user_sub: {user_sub}, args: {args}")
    
    session_attrs = event.get("sessionAttributes", {}) or {}
    prompt_session_attrs = event.get("promptSessionAttributes", {}) or {}

    if not user_sub:
        logger.error("user_sub is required but not found")
        return _build_response(
            event,
            {"error": "user_sub is required", "hint": "pass via sessionAttributes or request body"},
            session_attrs,
            prompt_session_attrs,
        )

    try:
        result = execute_tool(user_sub, operation, args)
        logger.info(f"Tool execution successful: {result}")
        body = {"operation": operation, "args": args, "result": result}
        return _build_response(event, body, session_attrs, prompt_session_attrs)
    except Exception as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        return _build_response(
            event,
            {"operation": operation, "args": args, "error": str(e)},
            session_attrs,
            prompt_session_attrs,
        )
