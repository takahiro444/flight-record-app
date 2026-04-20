#!/usr/bin/env python3
"""
Local test runner for the Strand SDK-based agent.

Usage:
  - Ensure AWS credentials and region are set for Bedrock access.
  - Provide DB_DIRECT_* env vars if you want to skip Secrets Manager and use a local tunnel.
  - Set USER_SUB to the Cognito subject for scoping queries.

Env vars:
  AWS_REGION: Region with Bedrock model access (e.g., us-west-2)
  BEDROCK_MODEL_ID: Optional override for the model id (else uses config.py)

  # Direct DB connection (optional for local testing)
  DB_DIRECT_HOST: localhost (if tunneling) or RDS endpoint
  DB_DIRECT_PORT: 5432
  DB_DIRECT_NAME or DB_NAME
  DB_DIRECT_USER or DB_USER
  DB_DIRECT_PASSWORD or DB_PASSWORD

  USER_SUB: Required. The Cognito subject tied to flight data rows.

Example:
  USER_SUB=abc-123 \
  DB_DIRECT_HOST=127.0.0.1 DB_DIRECT_PORT=5432 \
  DB_DIRECT_NAME=mydb DB_DIRECT_USER=myuser DB_DIRECT_PASSWORD=mypass \
  AWS_REGION=us-west-2 BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0 \
  python scripts/test-strands-agent-local.py
"""

import asyncio
import os
import sys

# Ensure we can import the backend modules
BACKEND_PATH = os.path.join(os.path.dirname(__file__), "..", "lambdas", "talk-to-flight-record-mcp-backend")
sys.path.insert(0, os.path.abspath(BACKEND_PATH))

from strand_agent import make_agent, run_agent_question  # type: ignore


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


async def main() -> None:
    user_sub = _require_env("USER_SUB")
    question = os.environ.get(
        "QUESTION",
        "Give me a brief stats overview and monthly mileage for 2024.",
    )

    agent = make_agent()
    print("Agent tools:", agent.tool_names)

    result = await run_agent_question(agent, question, user_sub)

    print("\nParsed answer:")
    print(result.get("parsed_answer"))

    print("\nPlan steps:")
    print(result.get("plan"))

    print("\nTool results (truncated):")
    # Avoid dumping huge payloads
    tool_results = result.get("tool_results", [])
    for tr in tool_results[:5]:
        print({
            "tool": tr.get("tool"),
            "args": tr.get("args"),
            "result_keys": list((tr.get("result") or {}).keys()),
        })

    print("\nModel raw answer:\n")
    print(result.get("model_answer_raw"))


if __name__ == "__main__":
    asyncio.run(main())
