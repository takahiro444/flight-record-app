# Email Parser Agent (AgentCore Runtime)

This is a **Strands SDK-based agent** deployed to **AWS Bedrock AgentCore Runtime**.

## What This Is

- **NOT a Lambda function**
- **Deployment package for AgentCore Runtime**
- Contains agent logic, tools, and dependencies
- Runs inside AWS-managed AgentCore Runtime service

## Architecture

```
API Gateway → Lambda (proxy-email-parser-agent) → AgentCore Runtime (THIS CODE)
```

AgentCore Runtime hosts and executes:
- Strands agent orchestration (`strand_agent.py`)
- Tool implementations (`tools.py`)
- Database access (`db.py`)
- All in a single managed runtime environment

## Components

### handler.py
Entry point invoked by AgentCore Runtime. Receives email text and session attributes, runs the Strands agent, returns structured results.

### strand_agent.py
Defines the Strands SDK agent with:
- System prompt for email parsing
- Tool definitions (validate, check duplicate, store)
- Structured output schema (EmailParseResult)

### tools.py
Three tool implementations:
1. `validate_flight_exists()` - Calls RapidAPI AeroDataBox
2. `check_duplicate_flight()` - Queries RDS Postgres
3. `store_validated_flight()` - Inserts into RDS

### db.py
Database connection helpers using pg8000, supports both Secrets Manager (production) and direct connection (local testing).

### config.py
Environment variable configuration using dataclass pattern.

## Environment Variables

```bash
BEDROCK_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0
RAPIDAPI_KEY=your-rapidapi-key
DB_SECRET_ARN=arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:...
ANSWER_MAX_TOKENS=800
DB_APP_NAME=email-parser-agent
```

## Local Testing

```bash
# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set local DB connection (via SSH tunnel)
export DB_DIRECT_HOST=127.0.0.1
export DB_DIRECT_PORT=5432
export DB_DIRECT_NAME=postgres
export DB_DIRECT_USER=your_user
export DB_DIRECT_PASSWORD=your_password
export RAPIDAPI_KEY=your_key

# Test locally
python -c "
import asyncio
from handler import lambda_handler

event = {
    'inputText': '''
    Your flight confirmation:
    Flight UA234 on January 25, 2026
    San Francisco (SFO) to New York (JFK)
    ''',
    'sessionState': {
        'sessionAttributes': {
            'user_sub': 'test-user-123',
            'user_email': 'test@example.com'
        }
    },
    'sessionId': 'test-session'
}

result = asyncio.run(lambda_handler(event, None))
print(result)
"
```

## Deployment to AgentCore Runtime

### 1. Package the code

```bash
cd agentcore-runtime/parse-email-flight

# Create deployment package
zip -r email-parser-agent.zip \
  handler.py \
  strand_agent.py \
  tools.py \
  db.py \
  config.py \
  requirements.txt

# Verify package contents
unzip -l email-parser-agent.zip
```

### 2. Deploy to AgentCore Runtime

```bash
# Deploy agent
aws bedrock-agentcore deploy-agent \
  --agent-name email-parser-agent \
  --runtime python3.12 \
  --code-package file://email-parser-agent.zip \
  --entry-point handler.lambda_handler \
  --model-id anthropic.claude-3-5-haiku-20241022-v1:0 \
  --environment Variables="{
    RAPIDAPI_KEY=${RAPIDAPI_KEY},
    DB_SECRET_ARN=${DB_SECRET_ARN},
    ANSWER_MAX_TOKENS=800
  }" \
  --vpc-config SubnetIds=${SUBNET_IDS},SecurityGroupIds=${SG_IDS} \
  --timeout 300 \
  --memory 512

# Output will include:
# agentId: abc-123-def-456
# agentArn: arn:aws:bedrock-agentcore:us-west-2:ACCOUNT:agent/abc-123-def-456
```

### 3. Create production alias

```bash
aws bedrock-agentcore create-agent-alias \
  --agent-id abc-123-def-456 \
  --alias-name prod \
  --description "Production alias for email parser agent"

# Output:
# agentAliasId: PRODXYZ123
```

### 4. Test invocation

```bash
aws bedrock-agentcore-runtime invoke-agent \
  --agent-id abc-123-def-456 \
  --agent-alias-id PRODXYZ123 \
  --session-id test-session-123 \
  --input-text "Parse this email: Flight UA234 on Jan 25, 2026 from SFO to JFK" \
  --session-state '{"sessionAttributes":{"user_sub":"test-user","user_email":"test@example.com"}}' \
  --enable-trace \
  output.json

# Check results
cat output.json | jq .completion
```

## Monitoring

### CloudWatch Logs
AgentCore agents log to CloudWatch Logs automatically:
```bash
aws logs tail /aws/bedrock-agentcore/email-parser-agent --follow
```

### Traces
Enable tracing in invocations to see tool execution details.

### Metrics
Monitor in CloudWatch:
- `AgentInvocations` - Total invocations
- `AgentErrors` - Error count
- `AgentDuration` - Execution time
- `ToolInvocations` - Tool call count

## Differences from Lambda

| Feature | Lambda | AgentCore Runtime |
|---------|--------|------------------|
| **Deployment** | `aws lambda create-function` | `aws bedrock-agentcore deploy-agent` |
| **Timeout** | 15 minutes max | Configurable, no hard limit |
| **Scaling** | Concurrent executions | Agent-optimized scaling |
| **Cold Start** | 1-5 seconds | <1 second (pre-warmed) |
| **Purpose** | General compute | AI agent workloads |

## Troubleshooting

### Agent fails to deploy
- Check `requirements.txt` has valid packages
- Verify VPC configuration if accessing RDS
- Ensure IAM role has necessary permissions

### Tool execution errors
- Check CloudWatch Logs for detailed error messages
- Verify environment variables are set correctly
- Test tools locally first with direct DB connection
