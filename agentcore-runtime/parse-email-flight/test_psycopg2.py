#!/usr/bin/env python3
import boto3
import json
import os
import sys
import uuid

# Set AGENTCORE_RUNTIME_ARN env var before running
RUNTIME_ARN = os.environ.get("AGENTCORE_RUNTIME_ARN")

if not RUNTIME_ARN:
    print("ERROR: AGENTCORE_RUNTIME_ARN environment variable is required", file=sys.stderr)
    sys.exit(2)

def test():
    client = boto3.client('bedrock-agentcore', region_name='us-west-2')
    session_id = f'test-{uuid.uuid4()}'
    
    payload = json.dumps({
        'prompt': 'Your flight UA234 on January 25, 2026 from San Francisco to New York',
        'sessionAttributes': {
            'user_sub': 'test-psycopg2-user',
            'user_email': 'psycopg2@test.com'
        }
    })
    
    print(f'Testing psycopg2 runtime...')
    print(f'Session: {session_id}\n')
    
    response = client.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=payload
    )
    
    result = json.loads(response['response'].read())
    print(json.dumps(result, indent=2))
    
    if result.get('status') == 'success':
        print(f"\n📊 Total: {result.get('total_found')}, Stored: {result.get('stored_count')}, Failed: {result.get('failed_count')}")
        
        if result.get('stored_count', 0) > 0:
            print('\n🎉 SUCCESS! Flight was stored to database!')
            return 0
        elif result.get('failed_count', 0) > 0:
            failed = result.get('failed_flights', [{}])[0]
            print(f"\n⚠️  Failed: {failed.get('reason', 'Unknown')}")
            return 1
    return 1

if __name__ == '__main__':
    exit(test())
