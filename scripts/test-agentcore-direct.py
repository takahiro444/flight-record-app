#!/usr/bin/env python3
"""
Test AgentCore Runtime directly to debug email parser issues.

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

# Test email with one flight
TEST_EMAIL = """
Subject: Your Alaska Airlines Confirmation

Alaska Airlines Flight AS521
Monday, January 6, 2026
Seattle (SEA) → San Diego (SAN)
Departure: 7:15 AM PST
"""

def test_runtime():
    """Invoke AgentCore Runtime and print results"""
    client = boto3.client('bedrock-agentcore', region_name=REGION)
    
    session_id = "test-session-12345-67890-abcdef-12345"  # Min 33 chars
    payload = json.dumps({
        "prompt": TEST_EMAIL,
        "sessionAttributes": {
            "user_sub": USER_SUB,
            "user_email": USER_EMAIL
        }
    })
    
    print(f"Invoking AgentCore Runtime: {RUNTIME_ARN}")
    print(f"Session ID: {session_id}")
    print(f"User: {USER_EMAIL}")
    print(f"Email text: {TEST_EMAIL[:100]}...")
    print("\n" + "="*80 + "\n")
    
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=payload
        )
        
        # Parse response
        response_body = response['response'].read()
        result = json.loads(response_body)
        
        print("✅ SUCCESS!")
        print(json.dumps(result, indent=2))
        
        # Show tool_results if available (for debugging)
        if 'tool_results' in result and result['tool_results']:
            print("\n" + "="*80)
            print("TOOL RESULTS:")
            for tool_result in result['tool_results']:
                print(f"  Tool: {tool_result.get('name', 'unknown')}")
                print(f"  Status: {tool_result.get('status', 'unknown')}")
                if tool_result.get('content'):
                    print(f"  Content: {tool_result.get('content')}")
        
        # Show summary
        if 'summary' in result:
            print("\n" + "="*80)
            print("SUMMARY:")
            print(result['summary'])
        
        return result
        
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}")
        print(f"Message: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = test_runtime()
    sys.exit(0 if result else 1)
