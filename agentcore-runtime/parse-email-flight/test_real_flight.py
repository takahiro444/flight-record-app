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

def test_with_real_flight():
    """Test with a realistic past flight"""
    client = boto3.client('bedrock-agentcore', region_name=REGION)
    
    # Use a more realistic flight in the past
    payload = json.dumps({
        "prompt": "Your United Airlines flight UA1234 on December 15, 2024 from San Francisco (SFO) to Newark (EWR) has been confirmed.",
        "sessionAttributes": {
            "user_sub": "test-agentcore-user",
            "user_email": "agentcore@test.com"
        }
    })
    
    print("🚀 Testing AgentCore Runtime with realistic flight...")
    print(f"Runtime ARN: {RUNTIME_ARN}")
    print(f"Region: {REGION}")
    print("-" * 60)
    print(f"Test Email: UA1234 on December 15, 2024 from SFO to EWR")
    print("-" * 60)
    
    try:
        print("\n📤 Invoking AgentCore Runtime...")
        response = client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            runtimeSessionId='test-session-real-flight-9876543210',
            payload=payload
        )
        
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
            stored = result.get('stored_count', 0)
            failed = result.get('failed_count', 0)
            duplicates = result.get('duplicate_count', 0)
            
            print(f"\n📊 Results:")
            print(f"   ✅ Stored: {stored}")
            print(f"   ⚠️  Failed: {failed}")
            print(f"   🔄 Duplicates: {duplicates}")
            
            if stored > 0:
                print("\n🎉 SUCCESS! Flight was stored!")
                stored_flights = result.get('stored_flights', [])
                for flight in stored_flights:
                    print(f"   Flight: {flight.get('flight_iata')} on {flight.get('date')}")
                    if 'record_id' in flight:
                        print(f"   Record ID: {flight['record_id']}")
                return 0
            elif failed > 0:
                print(f"\n⚠️  Flight validation/storage failed")
                failed_flights = result.get('failed_flights', [])
                for flight in failed_flights:
                    print(f"   Flight: {flight.get('flight_iata')} on {flight.get('date')}")
                    print(f"   Reason: {flight.get('reason', 'Unknown')}")
                return 1
            elif duplicates > 0:
                print(f"\n✅ Flight already exists (duplicate)")
                return 0
            
        return 1
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}")
        print(f"   {str(e)}")
        return 1

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("AgentCore Runtime Test - Real Flight")
    print("=" * 60 + "\n")
    
    exit_code = test_with_real_flight()
    
    print("\n" + "=" * 60)
    if exit_code == 0:
        print("✅ TEST PASSED")
    else:
        print("❌ TEST FAILED")
    print("=" * 60 + "\n")
    
    sys.exit(exit_code)
