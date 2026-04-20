"""
AgentCore Runtime entrypoint for email parser agent.
This wraps our Strands agent for deployment to Amazon Bedrock AgentCore Runtime.
"""

from bedrock_agentcore.runtime import BedrockAgentCoreApp
import asyncio
import json
import logging
import os

# Configure logging for CloudWatch
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("AgentCore entrypoint loaded")

# Initialize AgentCore app
app = BedrockAgentCoreApp()

# Agent initialized lazily to avoid startup issues
_agent = None

def get_agent():
    """Get or create agent (lazy initialization)"""
    global _agent
    if _agent is None:
        from strand_agent import make_agent
        _agent = make_agent()
    return _agent

@app.entrypoint
async def invoke(payload):
    """
    Process email parsing request via AgentCore Runtime.
    
    Expected payload structure:
    {
        "prompt": "email text...",  # or "inputText"
        "sessionAttributes": {
            "user_sub": "cognito-sub",
            "user_email": "user@example.com"
        }
    }
    """
    logger.info(f"Received payload keys: {list(payload.keys())}")
    
    # Extract email text
    email_text = payload.get("prompt") or payload.get("inputText") or payload.get("email_text", "")
    
    if not email_text or len(email_text) < 10:
        return {
            "error": "email_text required and must be at least 10 characters",
            "status": "error"
        }
    
    # Extract session attributes
    session_attrs = payload.get("sessionAttributes", {})
    user_sub = session_attrs.get("user_sub") or payload.get("user_sub")
    user_email = session_attrs.get("user_email") or payload.get("user_email")
    
    if not user_sub:
        return {
            "error": "user_sub required in sessionAttributes",
            "status": "error"
        }
    
    logger.info(f"Processing email for user {user_sub}, length: {len(email_text)}")
    
    try:
        # Get agent (lazy initialization)
        agent = get_agent()
        
        # Run agent
        from strand_agent import run_email_parse
        result = await run_email_parse(agent, email_text, user_sub, user_email)
        
        # Extract parsed result
        parsed = result.get("parsed_result", {})
        
        response = {
            "status": "success",
            "total_found": parsed.get("total_found", 0),
            "stored_count": parsed.get("stored_count", 0),
            "duplicate_count": parsed.get("duplicate_count", 0),
            "failed_count": parsed.get("failed_count", 0),
            "stored_flights": parsed.get("stored_flights", []),
            "duplicate_flights": parsed.get("duplicate_flights", []),
            "failed_flights": parsed.get("failed_flights", []),
            "summary": parsed.get("summary", "")
        }
        
        logger.info(f"Success: {response['stored_count']} stored, {response['duplicate_count']} duplicates")
        return response
        
    except Exception as e:
        logger.exception("Agent execution failed")
        return {
            "error": str(e),
            "status": "error"
        }


if __name__ == "__main__":
    # Run the app locally for testing
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    logger.info(f"Starting AgentCore app on {host}:{port}")
    app.run(host=host, port=port)
