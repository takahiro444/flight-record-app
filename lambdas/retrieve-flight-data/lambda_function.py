import json
import os
import boto3
import psycopg2
import requests
from datetime import datetime


# Lazy-initialized Secrets Manager client + cached key value.
_secrets_client = None
_cached_rapidapi_key = None


def _get_rapidapi_key():
    """
    Fetch the RapidAPI key.
    Prefers RAPIDAPI_SECRET_ARN (Secrets Manager) and falls back to
    RAPIDAPI_KEY env var for local dev / transition.
    """
    global _secrets_client, _cached_rapidapi_key
    if _cached_rapidapi_key:
        return _cached_rapidapi_key

    secret_arn = os.environ.get('RAPIDAPI_SECRET_ARN')
    if secret_arn:
        if _secrets_client is None:
            _secrets_client = boto3.client(
                'secretsmanager',
                region_name=os.environ.get('AWS_REGION', 'us-west-2'),
            )
        try:
            resp = _secrets_client.get_secret_value(SecretId=secret_arn)
            secret_str = resp.get('SecretString', '')
            try:
                parsed = json.loads(secret_str)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if isinstance(parsed, dict):
                _cached_rapidapi_key = (
                    parsed.get('api_key')
                    or parsed.get('RAPIDAPI_KEY')
                    or parsed.get('rapidapi_key')
                )
            else:
                _cached_rapidapi_key = secret_str
            if _cached_rapidapi_key:
                return _cached_rapidapi_key
        except Exception as e:
            print(f"[RAPIDAPI] Secrets Manager fetch failed, falling back to env: {type(e).__name__}: {e}")

    env_val = os.environ.get('RAPIDAPI_KEY')
    if env_val:
        _cached_rapidapi_key = env_val
        return env_val

    raise KeyError("RAPIDAPI_SECRET_ARN not configured and RAPIDAPI_KEY env var missing")

def lambda_handler(event, context):

    # Support both direct mapping (keys at top-level) and proxy integration (JSON in body)
    raw_body = event.get('body')
    body_json = {}
    if isinstance(raw_body, str):
        try:
            body_json = json.loads(raw_body)
        except json.JSONDecodeError:
            body_json = {}
    elif isinstance(raw_body, dict):
        body_json = raw_body

    flight_iata = body_json.get('flight_iata') or event.get('flight_iata')
    date = body_json.get('date') or event.get('date')

    # Extract Cognito authorizer claims if present
    claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
    user_sub = claims.get('sub')
    user_email = claims.get('email')

    # Debug logging of claims presence (will assist after proxy switch)
    print({
        'debug': 'claim snapshot',
        'has_claims': bool(claims),
        'user_sub': user_sub,
        'user_email': user_email
    })

    # Enforce presence of user identity; without claims insertion would create orphan row
    if not user_sub or not user_email:
        print("Missing Cognito claims (sub/email). Rejecting insert to avoid orphaned record.")
        return {
            'statusCode': 401,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': 'Missing user claims; ensure request is authenticated and POST integration is Lambda proxy',
                'received_claims_keys': list(claims.keys())
            })
        }

    if not flight_iata or not date:
        return{
            'statusCode': 400,
            'body': json.dumps('Missing flight_iata or date in the event input')
        }

    ### API request to retrieve flight details from rapidapi.com
    api_key = _get_rapidapi_key()
    url = f"https://aerodatabox.p.rapidapi.com/flights/number/{flight_iata}/{date}?dateLocalRole=Departure"
    
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "aerodatabox.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers)
    flight_data = response.json()

    # For debugging only
    print(flight_data)

    # Check if 'departures' key exists
    if not flight_data:
        return {
            'statusCode': 404,
            'body': json.dumps('No flight data found for this flight_iata and date.')
        }

    # Use the first flight entry
    flight_info = flight_data[0]

    # Extract needed fields carefully
    flight_date = date
    flight_iata = flight_iata # flight_info.get('flightNumber')
    airline_name = flight_info.get('airline', {}).get('name')
    airline_iata = flight_info.get('airline', {}).get('iata')
    departure_airport = flight_info.get('departure', {}).get('airport', {}).get('name')
    departure_iata = flight_info.get('departure', {}).get('airport', {}).get('iata')
    arrival_airport = flight_info.get('arrival', {}).get('airport', {}).get('name')
    arrival_iata = flight_info.get('arrival', {}).get('airport', {}).get('iata')
    departure_time = flight_info.get('departure', {}).get('scheduledTime', {}).get('utc')
    arrival_time = flight_info.get('arrival', {}).get('scheduledTime', {}).get('utc')
    
    # Parse the ISO 8601 timestamp strings to datetime objects
    departure_dt = datetime.strptime(departure_time, "%Y-%m-%d %H:%MZ")
    arrival_dt = datetime.strptime(arrival_time, "%Y-%m-%d %H:%MZ")

    # Calculate the duration in minutes
    flight_duration = int((arrival_dt - departure_dt).total_seconds() / 60)


    ### Calling another API from aerodatabox.p.rapidapi.com 
    ### to retrieve the flight mileage based on departure airport iata and arrival airport iata
    url = f"https://aerodatabox.p.rapidapi.com/airports/iata/{departure_iata}/distance-time/{arrival_iata}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        distance_data = response.json()
        flight_mileage = distance_data.get("greatCircleDistance", {}).get("mile")
    else:
        print(f"Error fetching distance: {response.status_code} - {response.text}")
        return None


    
    # Connect to PostgreSQL database (credentials from Lambda environment variables)
    conn = psycopg2.connect(
        host=os.environ['DB_HOST'],
        database=os.environ.get('DB_NAME', 'postgres'),
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        port=int(os.environ.get('DB_PORT', 5432))
    )
    cursor = conn.cursor()

    insert_query = """
    INSERT INTO flight_record (
        date, flight_iata, airline_name, airline_iata, departure_airport, departure_iata,
        arrival_airport, arrival_iata, departure_time, arrival_time, flight_duration, flight_mileage,
        user_sub, user_email
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(
        insert_query,
        (
            flight_date,
            flight_iata,
            airline_name,
            airline_iata,
            departure_airport,
            departure_iata,
            arrival_airport,
            arrival_iata,
            departure_time,
            arrival_time,
            flight_duration,
            flight_mileage,
            user_sub,
            user_email,
        ),
    )

    print({
        'debug': 'insert complete',
        'flight_iata': flight_iata,
        'date': flight_date,
        'user_sub': user_sub,
        'user_email': user_email,
        'flight_duration_min': flight_duration,
        'flight_mileage_miles': flight_mileage
    })

    conn.commit()
    cursor.close()
    conn.close()

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'message': 'Flight data stored successfully',
            'user_sub': user_sub,
            'user_email': user_email
        })
    }