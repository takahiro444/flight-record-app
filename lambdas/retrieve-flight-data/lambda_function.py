import json
import os
import psycopg2
import requests
from datetime import datetime

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
    api_key = os.environ['RAPIDAPI_KEY']
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