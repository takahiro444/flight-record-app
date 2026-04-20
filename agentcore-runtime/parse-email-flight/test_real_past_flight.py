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

def test_real_flight():
    """Test with a flight that's more likely to exist"""
    client = boto3.client('bedrock-agentcore', region_name='us-west-2')
    session_id = f'test-{uuid.uuid4()}'
    
    # Use a more generic flight email from December 2024
    payload = json.dumps({
        'prompt': '''
        Your United Airlines flight confirmation for December 20, 2024:
        
        Flight: UA1519
        Date: December 20, 2024
        From: San Francisco (SFO)
        To: Los Angeles (LAX)
        
        Thank you for flying with United!
        ''',
        'sessionAttributes': {
            'user_sub': 'test-real-flight-user',
            'user_email': 'realflight@test.com'
        }
    })
    
    print(f'Testing with real past flight...')
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
            for flight in result.get('stored_flights', []):
                print(f"  ✈️  {flight.get('flight_iata')} on {flight.get('date')}")
                if 'record_id' in flight:
                    print(f"      Record ID: {flight['record_id']}")
            return 0
        elif result.get('failed_count', 0) > 0:
            failed = result.get('failed_flights', [{}])[0]
            print(f"\n⚠️  Failed: {failed.get('reason', 'Unknown')}")
            return 1
    return 1

if __name__ == '__main__':
    exit(test_real_flight())
