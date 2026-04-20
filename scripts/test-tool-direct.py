#!/usr/bin/env python3
"""
Test AgentCore Runtime tool execution directly with explicit error reporting.

Required environment variables:
  AGENTCORE_RUNTIME_ARN - ARN of the AgentCore Runtime
  AWS_REGION            - optional, defaults to us-west-2
  TEST_USER_SUB         - optional Cognito sub for the test invocation
  TEST_USER_EMAIL       - optional email for the test invocation
"""
import boto3
import json
import os
import sys

RUNTIME_ARN = os.environ.get("AGENTCORE_RUNTIME_ARN")
REGION = os.environ.get("AWS_REGION", "us-west-2")
USER_SUB = os.environ.get("TEST_USER_SUB", "test-user-sub")
USER_EMAIL = os.environ.get("TEST_USER_EMAIL", "test@example.com")

if not RUNTIME_ARN:
    print("ERROR: AGENTCORE_RUNTIME_ARN environment variable is required", file=sys.stderr)
    sys.exit(2)

# Simple test to validate one flight
TEST_PROMPT = """
Please validate flight AS521 on 2026-01-06.

Call the validate_flight_exists tool with these parameters:
- flight_iata: AS521
- date: 2026-01-06

If the tool returns an error, include the COMPLETE error message in your response, 
including any details about error types, URLs, or environment variables.
"""

def test_tool_directly():
    client = boto3.client('bedrock-agentcore', region_name=REGION)
    
    session_id = "test-direct-tool-call-12345678901"  # 33 chars exactly
    payload = json.dumps({
        "prompt": TEST_PROMPT,
        "sessionAttributes": {
            "user_sub": USER_SUB,
            "user_email": USER_EMAIL
        }
    })
    
    print(f"Testing tool execution directly...")
    print(f"Runtime: {RUNTIME_ARN}")
    print(f"Session: {session_id}")
    print("\n" + "="*80 + "\n")
    
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=payload
        )
        
        response_body = response['response'].read()
        result = json.loads(response_body)
        
        print("RESPONSE:")
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_tool_directly()
