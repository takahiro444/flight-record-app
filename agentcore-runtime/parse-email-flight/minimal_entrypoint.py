"""
Minimal AgentCore Runtime entrypoint for debugging.
"""

from bedrock_agentcore.runtime import BedrockAgentCoreApp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Minimal entrypoint loaded successfully")

app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload):
    """Minimal handler that just returns success."""
    logger.info(f"Received payload: {payload}")
    return {
        "status": "success",
        "message": "Minimal runtime is working!"
    }

if __name__ == "__main__":
    import os
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    logger.info(f"Starting minimal app on {host}:{port}")
    app.run(host=host, port=port)
