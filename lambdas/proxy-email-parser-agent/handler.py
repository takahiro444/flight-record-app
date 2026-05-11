"""
Proxy Lambda for Email Parser Agent (AgentCore Runtime).
Handles async job tracking and invokes AgentCore Runtime.

Routes:
- POST /parse-email-and-store -> Create job, invoke AgentCore async
- GET /parse-email-and-store/status/{jobId} -> Poll job status
- Background processing -> Invoke AgentCore Runtime
"""

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

# AWS clients
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')


def _json_response(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization,Content-Type",
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
    return raw if isinstance(raw, dict) else {}


def _extract_user_info(event: Dict[str, Any], body: Dict[str, Any]) -> tuple:
    """Extract user_sub and user_email from the verified Cognito JWT claims only.

    The request body is untrusted input and must never override identity claims.
    """
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {}) or {}
    user_sub = claims.get("sub")
    user_email = claims.get("email")
    return user_sub, user_email


def _route(event: Dict[str, Any]) -> str:
    return event.get("rawPath") or event.get("path") or ""


def _get_table():
    """Get DynamoDB table for job storage"""
    table_name = os.environ.get("DYNAMODB_TABLE_NAME", "flight-email-parse-jobs")
    return dynamodb.Table(table_name)


def _get_agentcore_client():
    """Get AgentCore Runtime client"""
    region = os.environ.get("BEDROCK_REGION") or os.environ.get("AWS_REGION") or "us-west-2"
    return boto3.client("bedrock-agentcore", region_name=region)


def _agent_config() -> Dict[str, str]:
    """Get AgentCore Runtime ARN"""
    runtime_arn = os.environ.get("AGENTCORE_RUNTIME_ARN")
    if not runtime_arn:
        raise RuntimeError("AGENTCORE_RUNTIME_ARN env var is required")
    
    return {"runtimeArn": runtime_arn}


def invoke_agentcore(
    client,
    agent_config: Dict[str, str],
    email_text: str,
    user_sub: str,
    user_email: str,
    job_id: str,
    table
) -> Dict[str, Any]:
    """
    Invoke AgentCore Runtime to parse email.
    AgentCore hosts and executes the Strands agent code.
    """
    session_id = f"job-{job_id}"
    
    payload_dict = {
        "prompt": email_text,
        "sessionAttributes": {
            "user_sub": user_sub,
            "user_email": user_email or "unknown@example.com"
        }
    }
    payload_bytes = json.dumps(payload_dict).encode('utf-8')
    
    logger.info(f"Invoking AgentCore runtime for job {job_id}")
    
    try:
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=agent_config["runtimeArn"],
            runtimeSessionId=session_id,
            contentType='application/json',
            accept='application/json',
            payload=payload_bytes
        )
        
        # Parse response
        response_body = resp['response'].read()
        result = json.loads(response_body)
        
        logger.info(f"AgentCore result: status={result.get('status')}, found={result.get('total_found')}")
        
        return {
            "sessionId": session_id,
            "result": result
        }
        
    except Exception as e:
        logger.exception(f"AgentCore invocation failed for job {job_id}")
        raise


def handle_email_submit(event: Dict[str, Any]) -> Dict[str, Any]:
    """POST /parse-email-and-store - Create job, invoke async, return jobId"""
    body = _parse_body(event)
    user_sub, user_email = _extract_user_info(event, body)
    
    if not user_sub:
        return _json_response(401, {"error": "Missing user authentication"})
    
    email_text = body.get("email_text", "").strip()
    if not email_text or len(email_text) < 10:
        return _json_response(400, {
            "error": "email_text required and must be at least 10 characters"
        })
    
    # Limit email size
    if len(email_text) > 50000:
        return _json_response(400, {"error": "Email text too large (max 50KB)"})
    
    job_id = str(uuid.uuid4())
    table = _get_table()
    
    # Write PENDING job to DynamoDB
    now = int(time.time())
    table.put_item(Item={
        "jobId": job_id,
        "status": "PENDING",
        "email_text": email_text,
        "user_sub": user_sub,
        "user_email": user_email,
        "createdAt": now,
        "expireAt": now + 86400,  # TTL: 24 hours
    })
    
    logger.info(f"Created job {job_id} for user {user_sub}, email length: {len(email_text)}")
    
    # Invoke this same Lambda function asynchronously for background processing
    function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    try:
        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps({
                "source": "async-background",
                "jobId": job_id,
                "email_text": email_text,
                "user_sub": user_sub,
                "user_email": user_email
            })
        )
        logger.info(f"Invoked background processing for job {job_id}")
    except Exception as e:
        logger.error(f"Failed to invoke async Lambda: {e}")
        # Continue anyway, job can be retried
    
    return _json_response(200, {
        "jobId": job_id,
        "status": "PENDING",
        "message": "Email parsing started"
    })


def handle_status_check(event: Dict[str, Any]) -> Dict[str, Any]:
    """GET /parse-email-and-store/status/{jobId} - Poll job status"""
    path = _route(event)
    job_id = path.split("/")[-1]
    
    table = _get_table()
    
    try:
        response = table.get_item(Key={"jobId": job_id})
        
        if "Item" not in response:
            return _json_response(404, {"error": "Job not found"})
        
        item = response["Item"]
        status = item["status"]
        
        result = {
            "jobId": job_id,
            "status": status,
            "createdAt": item.get("createdAt")
        }
        
        if status == "COMPLETED":
            result["answer"] = item.get("answer")
            result["summary"] = item.get("summary")
            result["total_found"] = item.get("total_found", 0)
            result["stored_count"] = item.get("stored_count", 0)
            result["duplicate_count"] = item.get("duplicate_count", 0)
            result["failed_count"] = item.get("failed_count", 0)
            result["stored_flights"] = item.get("stored_flights", [])
            result["duplicate_flights"] = item.get("duplicate_flights", [])
            result["failed_flights"] = item.get("failed_flights", [])
            result["completedAt"] = item.get("completedAt")
        elif status == "ERROR":
            result["error"] = item.get("error")
            result["completedAt"] = item.get("completedAt")
        
        return _json_response(200, result)
        
    except Exception as e:
        logger.exception("Status check error")
        return _json_response(500, {"error": str(e)})


def handle_background_processing(event: Dict[str, Any]) -> Dict[str, Any]:
    """Background processing - Invoke AgentCore Runtime"""
    job_id = event["jobId"]
    email_text = event["email_text"]
    user_sub = event["user_sub"]
    user_email = event.get("user_email")
    
    table = _get_table()
    
    # Update status to PROCESSING
    table.update_item(
        Key={"jobId": job_id},
        UpdateExpression="SET #status = :status, processingAt = :now",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "PROCESSING", ":now": int(time.time())}
    )
    
    logger.info(f"Starting background processing for job {job_id}")
    
    try:
        # Invoke AgentCore Runtime (which hosts the Strands agent)
        client = _get_agentcore_client()
        agent_cfg = _agent_config()
        
        result = invoke_agentcore(
            client=client,
            agent_config=agent_cfg,
            email_text=email_text,
            user_sub=user_sub,
            user_email=user_email,
            job_id=job_id,
            table=table
        )
        
        result_data = result.get("result", {})
        
        # Extract results from structured output
        total_found = int(result_data.get("total_found", 0))
        stored_count = int(result_data.get("stored_count", 0))
        duplicate_count = int(result_data.get("duplicate_count", 0))
        failed_count = int(result_data.get("failed_count", 0))
        summary = result_data.get("summary", "Parsing completed")
        
        # Update job to COMPLETED
        table.update_item(
            Key={"jobId": job_id},
            UpdateExpression="""SET #status = :status, 
                                answer = :answer, 
                                summary = :summary,
                                total_found = :total_found,
                                stored_count = :stored_count,
                                duplicate_count = :duplicate_count,
                                failed_count = :failed_count,
                                stored_flights = :stored_flights,
                                duplicate_flights = :duplicate_flights,
                                failed_flights = :failed_flights,
                                completedAt = :now""",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "COMPLETED",
                ":answer": json.dumps(result_data),
                ":summary": summary,
                ":total_found": total_found,
                ":stored_count": stored_count,
                ":duplicate_count": duplicate_count,
                ":failed_count": failed_count,
                ":stored_flights": result_data.get("stored_flights", []),
                ":duplicate_flights": result_data.get("duplicate_flights", []),
                ":failed_flights": result_data.get("failed_flights", []),
                ":now": int(time.time())
            }
        )
        
        logger.info(f"Job {job_id} completed: found={total_found}, stored={stored_count}, duplicates={duplicate_count}")
        return {"statusCode": 200, "body": "Success"}
        
    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        
        # Update job to ERROR
        table.update_item(
            Key={"jobId": job_id},
            UpdateExpression="SET #status = :status, #error = :error, completedAt = :now",
            ExpressionAttributeNames={"#status": "status", "#error": "error"},
            ExpressionAttributeValues={
                ":status": "ERROR",
                ":error": str(e),
                ":now": int(time.time())
            }
        )
        
        return {"statusCode": 500, "body": f"Error: {str(e)}"}


def lambda_handler(event, context):
    """Main Lambda handler - routes requests"""
    logger.info(f"Event: {json.dumps({k: event.get(k) for k in ['httpMethod', 'path', 'rawPath', 'source']})}")
    
    # Handle async background processing
    if event.get("source") == "async-background":
        return handle_background_processing(event)
    
    # Handle API Gateway routes
    route = _route(event)
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    
    # CORS preflight
    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization,Content-Type",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            },
            "body": ""
        }
    
    # POST /parse-email-and-store
    if "parse-email-and-store" in route and "status" not in route and method == "POST":
        return handle_email_submit(event)
    
    # GET /parse-email-and-store/status/{jobId}
    elif "status" in route and method == "GET":
        return handle_status_check(event)
    
    else:
        return _json_response(404, {"error": f"Not found: {method} {route}"})
