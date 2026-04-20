#!/usr/bin/env python3
"""Test the proxy-email-parser-agent Lambda function"""
import boto3
import json
import time

FUNCTION_NAME = "proxy-email-parser-agent"
REGION = "us-west-2"

def test_email_parsing():
    """Test email parsing with AgentCore Runtime"""
    client = boto3.client('lambda', region_name=REGION)
    
    # Test email
    email_text = """
Your United Airlines Flight Confirmation

Flight: UA234
Date: January 25, 2026
From: San Francisco (SFO)
To: New York (JFK)
Departure: 8:00 AM
Confirmation: ABC123
    """
    
    # Invoke Lambda to submit email
    payload = {
        "httpMethod": "POST",
        "path": "/parse-email-and-store",
        "body": json.dumps({
            "email_text": email_text,
            "user_sub": "test-user-lambda-001",
            "user_email": "test@example.com"
        })
    }
    
    print("📤 Submitting email to Lambda...")
    response = client.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    
    result = json.loads(response['Payload'].read())
    print(json.dumps(result, indent=2))
    
    if result.get('statusCode') != 200:
        print("❌ Submission failed")
        return
    
    body = json.loads(result['body'])
    job_id = body.get('jobId')
    
    if not job_id:
        print("❌ No jobId returned")
        return
    
    print(f"\n✅ Job created: {job_id}")
    print("⏳ Polling for results...")
    
    # Poll for status
    max_attempts = 30
    for attempt in range(1, max_attempts + 1):
        time.sleep(3)
        
        status_payload = {
            "httpMethod": "GET",
            "path": f"/parse-email-and-store/status/{job_id}"
        }
        
        response = client.invoke(
            FunctionName=FUNCTION_NAME,
            InvocationType='RequestResponse',
            Payload=json.dumps(status_payload)
        )
        
        result = json.loads(response['Payload'].read())
        body = json.loads(result['body'])
        status = body.get('status')
        
        print(f"   Poll {attempt}/{max_attempts}: {status}")
        
        if status == "COMPLETED":
            print("\n" + "="*60)
            print("🎉 SUCCESS!")
            print("="*60)
            print(json.dumps(body, indent=2))
            print("\n📊 Summary:")
            print(f"   Found: {body.get('total_found')}")
            print(f"   Stored: {body.get('stored_count')}")
            print(f"   Duplicates: {body.get('duplicate_count')}")
            print(f"   Failed: {body.get('failed_count')}")
            if body.get('stored_flights'):
                print("\n   Stored flights:")
                for flight in body['stored_flights']:
                    print(f"   - {flight.get('flight_iata')} on {flight.get('date')}")
            return
        
        elif status == "ERROR":
            print(f"\n❌ Job failed: {body.get('error')}")
            return
    
    print(f"\n⏰ Timeout after {max_attempts} attempts")

if __name__ == "__main__":
    test_email_parsing()
