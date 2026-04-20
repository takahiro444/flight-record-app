"""
Entry point for AWS Bedrock AgentCore Runtime.
This code runs INSIDE AgentCore, not in a separate Lambda.

AgentCore will invoke this handler for each agent request.
"""

import json
import asyncio
import logging
from typing import Any, Dict

from strand_agent import make_agent, run_email_parse

logger = logging.getLogger()
logger.setLevel(logging.INFO)


async def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Entry point invoked by AgentCore Runtime.
    
    Event structure from AgentCore:
    {
      "inputText": "Parse this email: <email content>",
      "sessionState": {
        "sessionAttributes": {
          "user_sub": "cognito-sub-id",
          "user_email": "user@example.com"
        }
      },
      "sessionId": "unique-session-id"
    }
    
    Returns:
    {
      "completion": "Human-readable summary",
      "sessionState": {
        "sessionAttributes": {
          "total_found": 3,
          "stored_count": 2,
          "duplicate_count": 1,
          ...
        }
      }
    }
    """
    
    logger.info(f"AgentCore invocation: sessionId={event.get('sessionId')}")
    
    # Extract input
    input_text = event.get('inputText', '')
    session_state = event.get('sessionState', {})
    session_attrs = session_state.get('sessionAttributes', {})
    
    user_sub = session_attrs.get('user_sub')
    user_email = session_attrs.get('user_email')
    
    if not user_sub:
        logger.error("Missing user_sub in session attributes")
        return {
            "completion": "Error: User authentication required",
            "sessionState": {"sessionAttributes": {"error": "missing_user_sub"}}
        }
    
    if not input_text or len(input_text) < 10:
        logger.error("Invalid or missing input text")
        return {
            "completion": "Error: Email text is required",
            "sessionState": {"sessionAttributes": {"error": "invalid_input"}}
        }
    
    try:
        # Create and run Strands agent
        logger.info(f"Creating agent for user {user_sub}")
        agent = make_agent()
        
        logger.info(f"Running email parse for {len(input_text)} characters of text")
        result = await run_email_parse(agent, input_text, user_sub, user_email)
        
        parsed_result = result.get('parsed_result', {})
        summary = result.get('summary', 'Parsing completed')
        
        logger.info(f"Parse complete: found={parsed_result.get('total_found')}, "
                   f"stored={parsed_result.get('stored_count')}, "
                   f"duplicates={parsed_result.get('duplicate_count')}")
        
        # Return result to AgentCore
        return {
            "completion": summary,
            "sessionState": {
                "sessionAttributes": {
                    "total_found": parsed_result.get('total_found', 0),
                    "stored_count": parsed_result.get('stored_count', 0),
                    "duplicate_count": parsed_result.get('duplicate_count', 0),
                    "failed_count": parsed_result.get('failed_count', 0),
                    "stored_flights": json.dumps(parsed_result.get('stored_flights', [])),
                    "duplicates_skipped": json.dumps(parsed_result.get('duplicates_skipped', [])),
                    "failed_flights": json.dumps(parsed_result.get('failed_flights', []))
                }
            }
        }
        
    except Exception as e:
        logger.exception("Error during email parsing")
        return {
            "completion": f"Error parsing email: {str(e)}",
            "sessionState": {
                "sessionAttributes": {
                    "error": str(e),
                    "total_found": 0,
                    "stored_count": 0
                }
            }
        }


# For local testing (not used by AgentCore)
def sync_handler(event, context):
    """Synchronous wrapper for local testing"""
    return asyncio.run(lambda_handler(event, context))
