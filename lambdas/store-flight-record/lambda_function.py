"""
Lambda function to store validated flight records to RDS.
This Lambda runs in VPC with access to private RDS instance.
Called by AgentCore Runtime as part of the email parsing workflow.
"""

import json
import os
import boto3
import pg8000
from datetime import datetime

def get_db_connection():
    """Get database connection using Secrets Manager."""
    secret_arn = os.environ.get('DB_SECRET_ARN')
    
    if secret_arn:
        # Production: Use Secrets Manager
        secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
        secret_response = secrets_client.get_secret_value(SecretId=secret_arn)
        secret = json.loads(secret_response['SecretString'])
        
        return pg8000.connect(
            host=secret['host'],
            port=secret.get('port', 5432),
            database=secret['dbname'],
            user=secret['username'],
            password=secret['password'],
            timeout=30
        )
    else:
        # Fallback: Direct credentials (for testing)
        return pg8000.connect(
            host=os.environ['DB_HOST'],
            port=int(os.environ.get('DB_PORT', 5432)),
            database=os.environ.get('DB_NAME', 'postgres'),
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASSWORD'],
            timeout=30
        )

def lambda_handler(event, context):
    """
    Store a validated flight record to database.
    
    Expected event:
    {
        "user_sub": "cognito-sub",
        "user_email": "user@example.com",
        "enriched_data": {
            "exists": true,
            "flight_iata": "UA234",
            "date": "2025-02-15",
            "airline_name": "United Airlines",
            "airline_iata": "UA",
            "departure_airport": "San Francisco International Airport",
            "departure_iata": "SFO",
            "arrival_airport": "Los Angeles International Airport",
            "arrival_iata": "LAX",
            "departure_time": "2025-02-15 10:00Z",
            "arrival_time": "2025-02-15 11:30Z",
            "flight_duration": 90,
            "flight_mileage": 337
        }
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "success": true,
            "record_id": 123,
            "message": "Flight stored successfully"
        }
    }
    """
    
    print(f"[STORE-LAMBDA] Received event: {json.dumps(event)}")
    
    try:
        # Extract parameters
        user_sub = event.get('user_sub')
        user_email = event.get('user_email', 'unknown@example.com')
        enriched_data = event.get('enriched_data', {})
        
        if not user_sub:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': 'Missing required parameter: user_sub'
                })
            }
        
        if not enriched_data.get('exists'):
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': 'Cannot store flight that does not exist'
                })
            }
        
        # Connect to database
        print(f"[STORE-LAMBDA] Connecting to database...")
        conn = get_db_connection()
        cursor = conn.cursor()
        print(f"[STORE-LAMBDA] Database connection established")
        
        # Insert flight record (pg8000 uses %s placeholders)
        insert_query = """
            INSERT INTO flight_record (
                date, flight_iata, airline_name, airline_iata,
                departure_airport, departure_iata, arrival_airport, arrival_iata,
                departure_time, arrival_time, flight_duration, flight_mileage,
                user_sub, user_email
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        print(f"[STORE-LAMBDA] Executing INSERT for {enriched_data.get('flight_iata')} on {enriched_data.get('date')}")
        
        cursor.execute(insert_query, (
            enriched_data['date'],
            enriched_data['flight_iata'],
            enriched_data.get('airline_name'),
            enriched_data.get('airline_iata'),
            enriched_data.get('departure_airport'),
            enriched_data.get('departure_iata'),
            enriched_data.get('arrival_airport'),
            enriched_data.get('arrival_iata'),
            enriched_data.get('departure_time'),
            enriched_data.get('arrival_time'),
            enriched_data.get('flight_duration'),
            enriched_data.get('flight_mileage'),
            user_sub,
            user_email
        ))
        
        conn.commit()
        record_id = cursor.rowcount  # Number of rows inserted
        cursor.close()
        conn.close()
        
        print(f"[STORE-LAMBDA] Successfully stored record with ID: {record_id}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'record_id': record_id,
                'flight_iata': enriched_data['flight_iata'],
                'date': enriched_data['date'],
                'message': 'Flight stored successfully'
            })
        }
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"[STORE-LAMBDA] ERROR: {error_msg}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': error_msg[:500]  # Truncate long errors
            })
        }
