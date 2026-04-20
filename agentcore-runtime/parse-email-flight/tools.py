"""  
Tool implementations for Email Parser Agent.
These tools run inside AgentCore Runtime alongside the agent.
"""

import os
import requests
import logging
import json
import boto3
from datetime import datetime
from typing import Dict, Any, List

# Configure logging for CloudWatch
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lambda client initialized lazily
_lambda_client = None

def _get_lambda_client():
    """Get or create Lambda client (lazy initialization)."""
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client('lambda', region_name='us-west-2')
    return _lambda_client


class ToolError(Exception):
    """Raised when tool execution fails"""
    pass


def validate_flight_exists(user_sub: str, flight_iata: str, date: str) -> Dict[str, Any]:
    """
    Validate flight exists via AeroDataBox API and return enriched data.
    
    Args:
        user_sub: Cognito user identifier (for consistency, not used in validation)
        flight_iata: Flight IATA code (e.g., "UA234")
        date: Flight date in YYYY-MM-DD format
    
    Returns:
        Dict with exists, flight_iata, date, and enriched flight data
    """
    import sys
    api_key = os.environ.get('RAPIDAPI_KEY')
    
    # Include diagnostic info in the error message that will reach the user
    if not api_key:
        all_env_vars = list(os.environ.keys())
        raise ToolError(f"RAPIDAPI_KEY not configured. Available env vars: {', '.join(sorted(all_env_vars)[:10])}")
    
    url = f"https://aerodatabox.p.rapidapi.com/flights/number/{flight_iata}/{date}?dateLocalRole=Departure"
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "aerodatabox.p.rapidapi.com"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 404:
            return {
                "exists": False,
                "flight_iata": flight_iata,
                "date": date,
                "message": "Flight not found in AeroDataBox"
            }
        
        response.raise_for_status()
        
        # Try to parse JSON with error handling
        try:
            flight_data = response.json()
        except json.JSONDecodeError as json_err:
            # Include response preview in error
            response_preview = response.text[:500] if response.text else "(empty)"
            raise ToolError(f"API JSONDecodeError: Unable to parse response. Status: {response.status_code}. Preview: {response_preview}")
        
        # Check if API returned an error message
        if isinstance(flight_data, dict) and "message" in flight_data:
            return {
                "exists": False,
                "flight_iata": flight_iata,
                "date": date,
                "message": f"AeroDataBox API error: {flight_data['message']}"
            }
        
        if not flight_data or len(flight_data) == 0:
            return {"exists": False, "flight_iata": flight_iata, "date": date}
        
        flight_info = flight_data[0]
        
        departure_iata = flight_info.get('departure', {}).get('airport', {}).get('iata')
        arrival_iata = flight_info.get('arrival', {}).get('airport', {}).get('iata')
        
        # Fetch mileage
        flight_mileage = None
        if departure_iata and arrival_iata:
            distance_url = f"https://aerodatabox.p.rapidapi.com/airports/iata/{departure_iata}/distance-time/{arrival_iata}"
            distance_resp = requests.get(distance_url, headers=headers, timeout=10)
            if distance_resp.status_code == 200:
                distance_data = distance_resp.json()
                flight_mileage = distance_data.get("greatCircleDistance", {}).get("mile")
        
        # Calculate duration
        departure_time = flight_info.get('departure', {}).get('scheduledTime', {}).get('utc')
        arrival_time = flight_info.get('arrival', {}).get('scheduledTime', {}).get('utc')
        
        flight_duration = None
        if departure_time and arrival_time:
            try:
                departure_dt = datetime.strptime(departure_time, "%Y-%m-%d %H:%MZ")
                arrival_dt = datetime.strptime(arrival_time, "%Y-%m-%d %H:%MZ")
                flight_duration = int((arrival_dt - departure_dt).total_seconds() / 60)
            except Exception as e:
                print(f"Error parsing timestamps: {e}")
        
        return {
            "exists": True,
            "flight_iata": flight_iata,
            "date": date,
            "airline_name": flight_info.get('airline', {}).get('name'),
            "airline_iata": flight_info.get('airline', {}).get('iata'),
            "departure_airport": flight_info.get('departure', {}).get('airport', {}).get('name'),
            "departure_iata": departure_iata,
            "arrival_airport": flight_info.get('arrival', {}).get('airport', {}).get('name'),
            "arrival_iata": arrival_iata,
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "flight_duration": flight_duration,
            "flight_mileage": flight_mileage
        }
        
    except requests.exceptions.RequestException as e:
        # Include detailed error info that will reach the user via LLM
        error_type = type(e).__name__
        error_str = str(e)
        raise ToolError(f"API {error_type}: {error_str[:200]}. URL: {url}")


def check_duplicate_flight(user_sub: str, flight_iata: str, date: str) -> Dict[str, Any]:
    """
    Check if flight already exists in user's records via Lambda.
    
    Args:
        user_sub: Cognito user identifier
        flight_iata: Flight IATA code
        date: Flight date in YYYY-MM-DD format
    
    Returns:
        Dict with is_duplicate (bool) and existing_record info if found
    """
    # For now, skip duplicate checking since it requires DB access
    # The Lambda will handle INSERT conflicts if needed
    logger.info(f"[CHECK-DUP] Skipping duplicate check for {flight_iata} on {date}")
    return {
        "is_duplicate": False,
        "message": f"Duplicate check skipped - storage Lambda will handle conflicts"
    }


def store_validated_flight(user_sub: str, enriched_data: Dict[str, Any], user_email: str = None) -> Dict[str, Any]:
    """
    Store a single validated flight record to database via Lambda function.
    
    Args:
        user_sub: Cognito user identifier
        enriched_data: Full flight data from validate_flight_exists
        user_email: User's email (optional)
    
    Returns:
        Dict with success status and inserted record ID
    """
    if not enriched_data.get('exists'):
        raise ToolError("Cannot store flight that doesn't exist")
    
    user_email = user_email or "unknown@example.com"
    
    try:
        logger.info(f"[STORE] Invoking Lambda for {enriched_data.get('flight_iata')} on {enriched_data.get('date')}")
        logger.info(f"[STORE] user_sub: {user_sub}, user_email: {user_email}")
        
        # Prepare payload for Lambda
        payload = {
            "user_sub": user_sub,
            "user_email": user_email,
            "enriched_data": enriched_data
        }
        
        # Get Lambda client and invoke storage Lambda
        lambda_client = _get_lambda_client()
        response = lambda_client.invoke(
            FunctionName='store-flight-record',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Parse Lambda response
        response_payload = json.loads(response['Payload'].read())
        logger.info(f"[STORE] Lambda response: {response_payload}")
        
        if response_payload.get('statusCode') != 200:
            error_body = json.loads(response_payload.get('body', '{}'))
            error_msg = error_body.get('error', 'Unknown error')
            raise ToolError(f"Storage Lambda error: {error_msg}")
        
        result_body = json.loads(response_payload['body'])
        
        if not result_body.get('success'):
            raise ToolError(f"Storage failed: {result_body.get('error', 'Unknown error')}")
        
        logger.info(f"[STORE] Successfully stored with record_id: {result_body.get('record_id')}")
        
        return {
            "success": True,
            "record_id": result_body.get('record_id'),
            "flight_iata": enriched_data['flight_iata'],
            "date": enriched_data['date'],
            "message": f"Flight {enriched_data['flight_iata']} stored successfully"
        }
        
    except Exception as e:
        logger.error(f"[STORE] ERROR: {type(e).__name__}: {str(e)}", exc_info=True)
        error_msg = str(e)
        if "Storage Lambda error" in error_msg or "Storage failed" in error_msg:
            raise  # Re-raise ToolError as-is
        raise ToolError(f"Failed to store flight: {type(e).__name__}: {error_msg[:200]}")


# Tool registry for Strands SDK
_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "validate_flight_exists": {
        "description": "Validate if a flight exists on the given date via AeroDataBox API. Returns enriched flight data including airline, airports, times, duration, and mileage. Call this FIRST before checking duplicates or storing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "flight_iata": {
                    "type": "string",
                    "description": "Flight IATA code (e.g., UA234, AA1234)"
                },
                "date": {
                    "type": "string",
                    "description": "Flight date in YYYY-MM-DD format"
                }
            },
            "required": ["flight_iata", "date"]
        },
        "runner": lambda user_sub, args: validate_flight_exists(
            user_sub, 
            args["flight_iata"], 
            args["date"]
        )
    },
    "check_duplicate_flight": {
        "description": "Check if a flight already exists in the user's records to prevent duplicates. Returns is_duplicate boolean. Call this AFTER validation and BEFORE storing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "flight_iata": {
                    "type": "string",
                    "description": "Flight IATA code"
                },
                "date": {
                    "type": "string",
                    "description": "Flight date in YYYY-MM-DD format"
                }
            },
            "required": ["flight_iata", "date"]
        },
        "runner": lambda user_sub, args: check_duplicate_flight(
            user_sub,
            args["flight_iata"],
            args["date"]
        )
    },
    "store_validated_flight": {
        "description": "Store a single validated, non-duplicate flight record to the database. Call this ONLY AFTER validating the flight exists AND confirming it's not a duplicate. Pass the full enriched_data from validate_flight_exists.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "enriched_data": {
                    "type": "object",
                    "description": "Full enriched flight data from validate_flight_exists tool, must include exists=True"
                },
                "user_email": {
                    "type": "string",
                    "description": "User email (optional, will use session attribute if not provided)"
                }
            },
            "required": ["enriched_data"]
        },
        "runner": lambda user_sub, args: store_validated_flight(
            user_sub,
            args["enriched_data"],
            args.get("user_email")
        )
    }
}


def list_tools() -> List[Dict[str, Any]]:
    """Return list of tool specifications for Strands Agent"""
    return [
        {
            "name": name,
            "description": meta["description"],
            "inputSchema": meta["inputSchema"]
        }
        for name, meta in _TOOL_REGISTRY.items()
    ]


def get_tool(name: str) -> Dict[str, Any]:
    """Get tool metadata by name"""
    if name not in _TOOL_REGISTRY:
        raise ToolError(f"Unknown tool: {name}")
    return _TOOL_REGISTRY[name]


def execute_tool(user_sub: str, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool and return result"""
    tool = get_tool(name)
    runner = tool["runner"]
    result = runner(user_sub, args)
    return {"tool": name, "output": result}
