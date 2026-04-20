import json
import os
import sys
from typing import Any, Dict
import asyncio

# Ensure vendored dependencies in /package are importable when running in Lambda
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR = os.path.join(CURRENT_DIR, "package")
if PACKAGE_DIR not in sys.path:
    sys.path.append(PACKAGE_DIR)

from strand_agent import make_agent, run_agent_question

# Helper to extract user_sub from Cognito authorizer claims (REST or HTTP API Gateway proxy event)

def _extract_user_sub(event: Dict[str, Any]) -> str:
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
    return claims.get("sub")


def _json_response(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            # Basic CORS for browser calls
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization,Content-Type,x-api-key",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    raw = event.get("body")
    if raw and isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _route(event: Dict[str, Any]) -> str:
    # Support both REST and HTTP API shapes and strip stage prefixes (e.g., /prod)
    path = event.get("rawPath") or event.get("path") or ""
    # Remove stage prefix if present
    parts = path.split("/", 2)
    if len(parts) >= 2 and parts[1] in {"prod", "dev", "stage", "beta"}:
        path = "/" + parts[2] if len(parts) > 2 else "/"
    return path


def lambda_handler(event, context):
    path = _route(event)
    method = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod")
    body = _parse_body(event)

    # Simple identity endpoint to help clients retrieve Cognito subject/email
    if path == "/whoami" and method in ("GET", "POST"):
        claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
        sub = claims.get("sub")
        email = claims.get("email") or claims.get("cognito:username")
        if not sub:
            return _json_response(401, {"error": "missing user claims"})
        return _json_response(200, {"sub": sub, "email": email})

    # CORS preflight support
    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization,Content-Type,x-api-key",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            },
            "body": "",
        }

    # Endpoints:
    # - /whoami: identity helper for clients
    # - /strand/chat: Strands SDK agent entrypoint
    # - OPTIONS: CORS preflight

    # New SDK-based chat endpoint using Strands Agent
    if path in ("/strand/chat", "/talk-to-flight-record", "/") and method == "POST":
        user_sub = _extract_user_sub(event)
        if not user_sub:
            return _json_response(401, {"error": "missing user claims"})
        question = body.get("question", "").strip()
        if not question:
            return _json_response(400, {"error": "question required"})
        try:
            agent = make_agent()
            result_envelope = asyncio.run(run_agent_question(agent, question, user_sub))
            # Structured output already provided by the agent; passthrough
            return _json_response(200, {
                "question": result_envelope.get("question"),
                "plan": result_envelope.get("plan"),
                "tool_results": result_envelope.get("tool_results"),
                "model_answer_raw": result_envelope.get("model_answer_raw"),
                "parsed_answer": result_envelope.get("parsed_answer"),
                # Plain fields for UI convenience
                "answer": result_envelope.get("answer"),
                "numbers": result_envelope.get("numbers"),
            })
        except Exception as e:
            return _json_response(500, {"error": "strand agent failed", "detail": str(e)})

    # No legacy endpoints; use /strand/chat with SDK capabilities instead

    # Fallback 404
    return _json_response(404, {"error": f"No route for {method} {path}"})
