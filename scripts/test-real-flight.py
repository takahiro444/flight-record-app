#!/usr/bin/env python3
"""
Test with a date that should have real data (March 2025).

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

# Test with a date that has real data (within 365 days and actually occurred)
TEST_PROMPT = """
Please validate flight UA1234 on 2025-03-01.

Call the validate_flight_exists tool with these parameters:
- flight_iata: UA1234
- date: 2025-03-01

Report the complete result including all fields.
"""

def test_real_flight():
    client = boto3.client('bedrock-agentcore', region_name=REGION)
    
    session_id = "test-real-flight-1234567890123456"  # Exactly 36 chars
    payload = json.dumps({
        "prompt": TEST_PROMPT,
        "sessionAttributes": {
            "user_sub": USER_SUB,
            "user_email": USER_EMAIL
        }
    })
    
    print(f"Testing with real flight data (UA1234 on 2025-03-01)...")
    print(f"Runtime: {RUNTIME_ARN}")
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
    test_real_flight()
