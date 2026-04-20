#!/usr/bin/env python3
"""
Minimal test: Just try to connect to database and run a simple query.

Required environment variables:
  AGENTCORE_RUNTIME_ARN - ARN of the AgentCore Runtime
"""
import boto3
import json
import os
import sys
import uuid

RUNTIME_ARN = os.environ.get("AGENTCORE_RUNTIME_ARN")

if not RUNTIME_ARN:
    print("ERROR: AGENTCORE_RUNTIME_ARN environment variable is required", file=sys.stderr)
    sys.exit(2)

def test_db_only():
    client = boto3.client('bedrock-agentcore', region_name='us-west-2')
    session_id = f'test-{uuid.uuid4()}'
    
    # Simple prompt that should just test DB connection
    payload = json.dumps({
        'prompt': 'Check if you can connect to the database and count how many flights user test-user has',
        'sessionAttributes': {
            'user_sub': 'test-user',
            'user_email': 'test@test.com'
        }
    })
    
    print(f'Testing database connectivity...')
    print(f'Session: {session_id}\n')
    
    response = client.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=payload
    )
    
    result = json.loads(response['response'].read())
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    test_db_only()
