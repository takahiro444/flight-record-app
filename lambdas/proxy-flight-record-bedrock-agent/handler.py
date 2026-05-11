import json
import logging
import os
import time
import uuid
from decimal import Decimal
from typing import Any, Dict

import boto3

# Custom JSON encoder to handle DynamoDB Decimal types
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB and Lambda clients
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')


def _json_response(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization,Content-Type,x-api-key",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    raw = event.get("body")
    if raw and isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _extract_user_sub(event: Dict[str, Any], body: Dict[str, Any]) -> str | None:
    # Identity is taken ONLY from the verified Cognito JWT claims.
    # The request body is untrusted input and must never be a source of identity.
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {}) or {}
    return claims.get("sub") or claims.get("cognito:username")


def _route(event: Dict[str, Any]) -> str:
    return event.get("rawPath") or event.get("path") or ""


def _build_client():
    region = os.environ.get("BEDROCK_REGION") or os.environ.get("AWS_REGION") or "us-west-2"
    return boto3.client("bedrock-agent-runtime", region_name=region)


def _agent_ids() -> Dict[str, str]:
    agent_id = os.environ.get("AGENT_ID")
    if not agent_id:
        raise RuntimeError("AGENT_ID env var is required")
    alias_id = os.environ.get("AGENT_ALIAS_ID")
    return {"agentId": agent_id, "agentAliasId": alias_id}


def _get_table():
    """Get DynamoDB table for job storage"""
    table_name = os.environ.get("DYNAMODB_TABLE_NAME", "flight-chat-jobs")
    return dynamodb.Table(table_name)


def invoke_bedrock(client, *, agent_ids: Dict[str, str], question: str, user_sub: str, job_id: str = None, table = None) -> Dict[str, Any]:
    """Standalone function to invoke Bedrock agent and capture trace. Used by background handler.
    
    If job_id and table are provided, will update DynamoDB incrementally as agents are discovered.
    """
    session_id = str(uuid.uuid4())
    params = {
        "agentId": agent_ids["agentId"],
        "sessionId": session_id,
        "inputText": question,
        "sessionState": {
            "sessionAttributes": {"user_sub": user_sub},
            "promptSessionAttributes": {"user_sub": user_sub},
        },
        "enableTrace": True,  # Enable trace to capture agent invocations
    }
    if agent_ids.get("agentAliasId"):
        params["agentAliasId"] = agent_ids["agentAliasId"]

    resp = client.invoke_agent(**params)

    # Collect text chunks and trace information
    answer = ""
    agents_invoked = []
    
    for event in resp.get("completion", []):
        if "chunk" in event:
            answer += event["chunk"].get("bytes", b"").decode("utf-8")
        
        # Capture trace events for agent collaborations
        if "trace" in event:
            trace = event["trace"].get("trace", {})
            
            # Check for orchestration trace (agent-to-agent calls)
            if "orchestrationTrace" in trace:
                orch = trace["orchestrationTrace"]
                
                # Capture collaborator invocations from INPUT (when agent is being called)
                if "invocationInput" in orch:
                    inv_input = orch.get("invocationInput", {})
                    if "agentCollaboratorInvocationInput" in inv_input:
                        collab = inv_input["agentCollaboratorInvocationInput"]
                        agent_name = collab.get("agentCollaboratorName", "")
                        if agent_name and agent_name not in agents_invoked:
                            agents_invoked.append(agent_name)
                            # Update DynamoDB incrementally for real-time UI updates
                            if job_id and table:
                                try:
                                    table.update_item(
                                        Key={"jobId": job_id},
                                        UpdateExpression="SET agents_invoked = :agents",
                                        ExpressionAttributeValues={":agents": agents_invoked}
                                    )
                                    logger.info(f"Updated job {job_id} with agent: {agent_name}")
                                except Exception as e:
                                    logger.warning(f"Failed to update agents incrementally: {e}")
                
                # Also capture from OUTPUT (when agent returns result)
                if "observation" in orch:
                    obs = orch.get("observation", {})
                    if "agentCollaboratorInvocationOutput" in obs:
                        collab_out = obs["agentCollaboratorInvocationOutput"]
                        agent_name = collab_out.get("agentCollaboratorName", "")
                        if agent_name and agent_name not in agents_invoked:
                            agents_invoked.append(agent_name)
                            # Update DynamoDB incrementally for real-time UI updates
                            if job_id and table:
                                try:
                                    table.update_item(
                                        Key={"jobId": job_id},
                                        UpdateExpression="SET agents_invoked = :agents",
                                        ExpressionAttributeValues={":agents": agents_invoked}
                                    )
                                    logger.info(f"Updated job {job_id} with agent: {agent_name}")
                                except Exception as e:
                                    logger.warning(f"Failed to update agents incrementally: {e}")
    
    # Always include the supervisor agent
    if "Supervisor" not in str(agents_invoked):
        agents_invoked.insert(0, "Supervisor Agent")
    
    logger.info(f"Agents invoked: {agents_invoked}")
    return {
        "sessionId": session_id, 
        "answer": answer.strip(),
        "agents_invoked": agents_invoked
    }


def handle_chat_submit(event: Dict[str, Any], body: Dict[str, Any], user_sub: str) -> Dict[str, Any]:
    """POST /talk-to-flight-record - Create job, invoke Lambda async, return jobId"""
    question = body.get("question", "").strip()
    if not question:
        return _json_response(400, {"error": "question is required"})
    
    job_id = str(uuid.uuid4())
    table = _get_table()
    
    # Write PENDING job to DynamoDB
    table.put_item(Item={
        "jobId": job_id,
        "status": "PENDING",
        "question": question,
        "user_sub": user_sub,
        "createdAt": int(time.time()),
        "expireAt": int(time.time()) + 86400,  # TTL: 24 hours
    })
    
    logger.info(f"Created job {job_id} for user {user_sub}")
    
    # Invoke this same Lambda function asynchronously for background processing
    function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    try:
        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps({
                "source": "async-background",
                "jobId": job_id,
                "question": question,
                "user_sub": user_sub,
            })
        )
        logger.info(f"Invoked async processing for job {job_id}")
    except Exception as e:
        logger.error(f"Failed to invoke async Lambda: {e}", exc_info=True)
        # Update job to ERROR
        table.update_item(
            Key={"jobId": job_id},
            UpdateExpression="SET #status = :error, #error = :msg",
            ExpressionAttributeNames={"#status": "status", "#error": "error"},
            ExpressionAttributeValues={":error": "ERROR", ":msg": f"Failed to start processing: {str(e)}"}
        )
        return _json_response(500, {"error": "Failed to start processing"})
    
    return _json_response(200, {
        "jobId": job_id,
        "status": "PENDING",
        "message": "Processing started"
    })


def handle_status_check(event: Dict[str, Any]) -> Dict[str, Any]:
    """GET /talk-to-flight-record/status/{jobId} - Read job status from DynamoDB"""
    job_id = event.get("pathParameters", {}).get("jobId")
    if not job_id:
        return _json_response(400, {"error": "jobId path parameter required"})
    
    table = _get_table()
    try:
        response = table.get_item(Key={"jobId": job_id})
    except Exception as e:
        logger.error(f"DynamoDB get_item error: {e}", exc_info=True)
        return _json_response(500, {"error": "Failed to retrieve job status"})
    
    if "Item" not in response:
        return _json_response(404, {"error": "Job not found"})
    
    item = response["Item"]
    
    # Return different fields based on status
    result = {
        "jobId": job_id,
        "status": item.get("status", "UNKNOWN"),
    }
    
    if item.get("status") == "COMPLETED":
        result["answer"] = item.get("answer", "")
        result["agents_invoked"] = item.get("agents_invoked", [])
        result["sessionId"] = item.get("sessionId")
        result["completedAt"] = item.get("completedAt")
    elif item.get("status") == "ERROR":
        result["error"] = item.get("error", "Unknown error")
    elif item.get("status") == "PROCESSING":
        result["message"] = "Agents are analyzing your request..."
        # Include any agents discovered so far for real-time UI updates
        result["agents_invoked"] = item.get("agents_invoked", [])
    
    result["createdAt"] = item.get("createdAt")
    
    return _json_response(200, result)


def handle_background_processing(payload: Dict[str, Any]):
    """Background async handler - calls Bedrock and updates DynamoDB"""
    job_id = payload.get("jobId")
    question = payload.get("question")
    user_sub = payload.get("user_sub")
    
    if not all([job_id, question, user_sub]):
        logger.error(f"Missing required fields in async payload: {payload}")
        return
    
    table = _get_table()
    
    # Update status to PROCESSING
    try:
        table.update_item(
            Key={"jobId": job_id},
            UpdateExpression="SET #status = :processing",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":processing": "PROCESSING"}
        )
    except Exception as e:
        logger.error(f"Failed to update job to PROCESSING: {e}")
    
    try:
        # Call Bedrock agent
        client = _build_client()
        agent_ids = _agent_ids()
        result = invoke_bedrock(client, agent_ids=agent_ids, question=question, user_sub=user_sub, job_id=job_id, table=table)
        
        # Update DynamoDB with COMPLETED result
        table.update_item(
            Key={"jobId": job_id},
            UpdateExpression="SET #status = :completed, answer = :answer, agents_invoked = :agents, sessionId = :sid, completedAt = :time",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":completed": "COMPLETED",
                ":answer": result.get("answer", ""),
                ":agents": result.get("agents_invoked", []),
                ":sid": result.get("sessionId", ""),
                ":time": int(time.time())
            }
        )
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
        # Update DynamoDB with ERROR
        try:
            table.update_item(
                Key={"jobId": job_id},
                UpdateExpression="SET #status = :error, #error = :msg, completedAt = :time",
                ExpressionAttributeNames={"#status": "status", "#error": "error"},
                ExpressionAttributeValues={
                    ":error": "ERROR",
                    ":msg": str(e),
                    ":time": int(time.time())
                }
            )
        except Exception as update_error:
            logger.error(f"Failed to update job to ERROR: {update_error}")


def lambda_handler(event, context):  # type: ignore[override]
    logger.info(f"Received event: {json.dumps(event, default=str)[:500]}")
    
    # Check if this is an async background invocation
    if event.get("source") == "async-background":
        handle_background_processing(event)
        return  # No response needed for async invocations
    
    # Normal API Gateway invocation
    path = _route(event)
    method = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod")

    if method == "OPTIONS":
        return _json_response(200, {"ok": True})

    # Route to status check for GET /talk-to-flight-record/status/{jobId}
    if method == "GET" and "/status/" in path:
        return handle_status_check(event)

    # Route to chat submit for POST /talk-to-flight-record
    if path in ("/chat", "/proxy/chat", "/talk-to-flight-record") and method == "POST":
        body = _parse_body(event)
        user_sub = _extract_user_sub(event, body)
        if not user_sub:
            return _json_response(401, {"error": "missing user_sub (Cognito claim)"})
        return handle_chat_submit(event, body, user_sub)
    
    return _json_response(404, {"error": f"No route for {method} {path}"})
