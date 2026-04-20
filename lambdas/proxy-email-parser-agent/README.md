# Proxy Lambda for Email Parser Agent

This Lambda function is a **thin proxy** between API Gateway and AWS Bedrock AgentCore Runtime.

## Purpose

- Routes API Gateway requests to AgentCore Runtime
- Manages async job tracking in DynamoDB
- Provides polling endpoints for frontend

## NOT Responsible For

- ❌ Running agent code (that's in AgentCore Runtime)
- ❌ Executing tools (that's in AgentCore Runtime)
- ❌ LLM orchestration (that's in AgentCore Runtime)

## Routes

### POST /parse-email-and-store
Creates a job in DynamoDB and invokes itself asynchronously for background processing.

**Request:**
```json
{
  "email_text": "Your flight confirmation email text..."
}
```

**Response:**
```json
{
  "jobId": "uuid",
  "status": "PENDING",
  "message": "Email parsing started"
}
```

### GET /parse-email-and-store/status/{jobId}
Polls job status from DynamoDB.

**Response (PENDING/PROCESSING):**
```json
{
  "jobId": "uuid",
  "status": "PROCESSING",
  "createdAt": 1234567890
}
```

**Response (COMPLETED):**
```json
{
  "jobId": "uuid",
  "status": "COMPLETED",
  "total_found": 3,
  "stored_count": 2,
  "duplicate_count": 1,
  "failed_count": 0,
  "answer": "Summary text...",
  "completedAt": 1234567890
}
```

## Environment Variables

```bash
AGENTCORE_AGENT_ID=abc-123-def          # AgentCore agent ID (from deployment)
AGENTCORE_AGENT_ALIAS_ID=prod           # AgentCore agent alias (default: prod)
DYNAMODB_TABLE_NAME=flight-email-parse-jobs
BEDROCK_REGION=us-west-2
```

## Deployment

```bash
cd lambdas/proxy-email-parser-agent

# Create deployment package
zip -r proxy.zip handler.py

# Deploy Lambda
aws lambda create-function \
  --function-name proxy-email-parser-agent \
  --runtime python3.12 \
  --handler handler.lambda_handler \
  --role arn:aws:iam::ACCOUNT:role/lambda-execution-role \
  --zip-file fileb://proxy.zip \
  --timeout 60 \
  --memory-size 256 \
  --environment Variables="{
    AGENTCORE_AGENT_ID=abc-123-def,
    AGENTCORE_AGENT_ALIAS_ID=prod,
    DYNAMODB_TABLE_NAME=flight-email-parse-jobs,
    BEDROCK_REGION=us-west-2
  }"

# Update existing function
aws lambda update-function-code \
  --function-name proxy-email-parser-agent \
  --zip-file fileb://proxy.zip
```

## IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore-runtime:InvokeAgent"
      ],
      "Resource": "arn:aws:bedrock-agentcore:*:*:agent/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/flight-email-parse-jobs"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": "arn:aws:lambda:*:*:function:proxy-email-parser-agent"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

## DynamoDB Table Schema

Table: `flight-email-parse-jobs`
- Partition Key: `jobId` (String)
- TTL Attribute: `expireAt`

**Item Structure:**
```json
{
  "jobId": "uuid",
  "status": "PENDING|PROCESSING|COMPLETED|ERROR",
  "email_text": "...",
  "user_sub": "cognito-sub",
  "user_email": "user@example.com",
  "answer": "Parsing summary...",
  "summary": "Short summary...",
  "total_found": 3,
  "stored_count": 2,
  "duplicate_count": 1,
  "failed_count": 0,
  "createdAt": 1234567890,
  "processingAt": 1234567891,
  "completedAt": 1234567920,
  "expireAt": 1234567890 + 86400
}
```

## Testing

```bash
# Test POST endpoint
curl -X POST https://<api-id>.execute-api.us-west-2.amazonaws.com/prod/parse-email-and-store \
  -H "Authorization: Bearer ${ID_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "email_text": "Your flight UA234 on Jan 25, 2026 from SFO to JFK"
  }'

# Response: {"jobId": "abc-123", "status": "PENDING"}

# Test status polling
curl https://<api-id>.execute-api.us-west-2.amazonaws.com/prod/parse-email-and-store/status/abc-123 \
  -H "Authorization: Bearer ${ID_TOKEN}"
```

## Architecture Flow

```
1. API Gateway receives POST /parse-email-and-store
2. Lambda creates DynamoDB job (status: PENDING)
3. Lambda invokes itself async (Event invocation)
4. Returns jobId immediately to client
5. Background processing:
   - Updates status to PROCESSING
   - Calls AgentCore Runtime (hosts Strands agent)
   - AgentCore executes tools, parses email
   - Returns structured results
   - Lambda updates job to COMPLETED
6. Client polls GET /status/{jobId} every 4 seconds
7. Eventually receives COMPLETED with results
```

## Monitoring

### CloudWatch Logs
```bash
aws logs tail /aws/lambda/proxy-email-parser-agent --follow
```

### Metrics
- Invocations (should match API requests)
- Errors (AgentCore invocation failures)
- Duration (should be <5s for API routes, 20-60s for background)

## Troubleshooting

### Job stuck in PENDING
- Check Lambda async invocation succeeded
- Check Lambda execution role has InvokeFunction permission
- Look for Lambda errors in CloudWatch Logs

### Job status ERROR
- Check error field in DynamoDB item
- Common causes:
  - AgentCore agent not deployed
  - Invalid AGENTCORE_AGENT_ID
  - Network issues (VPC, security groups)
  - RDS connection timeout

### AgentCore invocation fails
- Verify agent ID is correct
- Check IAM role has bedrock-agentcore-runtime:InvokeAgent
- Ensure agent is in same region as Lambda
