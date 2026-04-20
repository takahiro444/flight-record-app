import boto3
import json
import os
import sys

# Runtime configuration (set AGENTCORE_RUNTIME_ARN env var before running)
RUNTIME_ARN = os.environ.get("AGENTCORE_RUNTIME_ARN")
REGION = os.environ.get("AWS_REGION", "us-west-2")

if not RUNTIME_ARN:
    print("ERROR: AGENTCORE_RUNTIME_ARN environment variable is required", file=sys.stderr)
    sys.exit(2)

def test_agent():
    """Test the AgentCore Runtime with a sample email"""
    client = boto3.client('bedrock-agentcore', region_name=REGION)
    
    # Test payload with a sample flight email
    payload = json.dumps({
        "prompt": "Your flight UA234 on January 25, 2026 from San Francisco to New York",
        "sessionAttributes": {
            "user_sub": "test-user-psycopg2",
            "user_email": "psycopg2test@example.com"
        }
    })
    
    print("🚀 Testing AgentCore Runtime...")
    print(f"Runtime ARN: {RUNTIME_ARN}")
    print(f"Region: {REGION}")
    print("-" * 60)
    print(f"Test Email: UA234 on January 25, 2026 from SFO to NYC")
    print("-" * 60)
    
    try:
        print("\n📤 Invoking AgentCore Runtime...")
        response = client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            runtimeSessionId='test-session-88deb165-00a1-4d34-98fe-c7a6e6cf9364',  # Min 33 chars
            payload=payload
        )
        
        # Read response
        print("📥 Reading response...")
        response_body = response['response'].read()
        result = json.loads(response_body)
        
        print("\n" + "=" * 60)
        print("✅ AGENT RESPONSE RECEIVED")
        print("=" * 60)
        print(json.dumps(result, indent=2))
        print("=" * 60)
        
        # Analyze results
        if result.get('status') == 'success':
            print("\n🎉 SUCCESS!")
            print(f"   Total flights found: {result.get('total_found', 0)}")
            print(f"   Stored: {result.get('stored_count', 0)}")
            print(f"   Duplicates: {result.get('duplicate_count', 0)}")
            print(f"   Failed: {result.get('failed_count', 0)}")
            
            stored = result.get('stored_flights', [])
            if stored:
                print("\n   Stored flights:")
                for flight in stored:
                    print(f"   - {flight.get('iata_code')} on {flight.get('flight_date')} (ID: {flight.get('record_id')})")
            
            return 0
        elif result.get('status') == 'error':
            print(f"\n⚠️  Agent returned error: {result.get('error', 'Unknown error')}")
            return 1
        else:
            print(f"\n⚠️  Unexpected response status: {result.get('status', 'unknown')}")
            return 1
        
    except client.exceptions.ResourceNotFoundException:
        print(f"\n❌ ERROR: Runtime not found")
        print(f"   ARN: {RUNTIME_ARN}")
        print(f"   Make sure the runtime exists and is in READY state")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}")
        print(f"   {str(e)}")
        
        # Provide helpful debugging info
        if "AccessDenied" in str(e):
            print("\n💡 Tip: Check IAM permissions for bedrock-agentcore:InvokeAgentRuntime")
        elif "VPC" in str(e):
            print("\n💡 Tip: Check VPC configuration and security groups")
        elif "timeout" in str(e).lower():
            print("\n💡 Tip: Runtime may be taking too long. Check CloudWatch logs")
        
        return 1

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("AgentCore Runtime Test - Email Parser Agent")
    print("=" * 60 + "\n")
    
    exit_code = test_agent()
    
    print("\n" + "=" * 60)
    if exit_code == 0:
        print("✅ TEST COMPLETED SUCCESSFULLY")
    else:
        print("❌ TEST FAILED - See errors above")
    print("=" * 60 + "\n")
    
    sys.exit(exit_code)
