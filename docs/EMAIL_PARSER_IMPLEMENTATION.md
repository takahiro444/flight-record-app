# Email Parser Feature - Complete Implementation

## Directory Structure

```
flight-record-app-node/
├── agentcore-runtime/
│   └── parse-email-flight/          # AgentCore Runtime deployment package
│       ├── handler.py               # Entry point (called by AgentCore)
│       ├── strand_agent.py          # Agent definition + tools
│       ├── tools.py                 # Tool implementations
│       ├── db.py                    # Database connection
│       ├── config.py                # Environment config
│       ├── requirements.txt         # Dependencies
│       ├── .env.example             # Example environment variables
│       └── README.md                # Deployment documentation
│
└── lambdas/
    └── proxy-email-parser-agent/    # API Gateway proxy Lambda
        ├── handler.py               # Routes API requests, manages jobs
        ├── requirements.txt         # boto3 only
        ├── iam-policy.json          # IAM permissions
        └── README.md                # Deployment documentation
```

## Architecture Flow

```
┌─────────────┐      ┌─────────────────┐      ┌───────────────────┐      ┌─────────────────┐
│   React     │      │  API Gateway    │      │  Proxy Lambda     │      │  AgentCore      │
│   Frontend  │─────▶│  (Cognito auth) │─────▶│  (Job Manager)    │─────▶│  Runtime        │
│             │      │                 │      │                   │      │  (Agent Host)   │
└─────────────┘      └─────────────────┘      └───────────────────┘      └─────────────────┘
       │                                              │                            │
       │ 1. POST email_text                          │                            │
       │─────────────────────────────────────────────▶                            │
       │                                              │                            │
       │                                        2. Create job                      │
       │                                        (DynamoDB)                         │
       │                                              │                            │
       │ 3. Return jobId (PENDING)                   │                            │
       │◀─────────────────────────────────────────────│                            │
       │                                              │                            │
       │                                        4. Invoke self                     │
       │                                        async (background)                 │
       │                                              │                            │
       │                                              │ 5. Call AgentCore          │
       │                                              │────────────────────────────▶
       │                                              │                            │
       │                                              │                      6. Execute agent
       │                                              │                      + tools in sandbox
       │                                              │                            │
       │                                              │ 7. Return results          │
       │                                              │◀────────────────────────────│
       │                                              │                            │
       │                                        8. Update job                      │
       │                                        (COMPLETED)                        │
       │                                              │                            │
       │ 9. Poll status (every 4s)                   │                            │
       │─────────────────────────────────────────────▶│                            │
       │                                              │                            │
       │ 10. Return results when ready                │                            │
       │◀─────────────────────────────────────────────│                            │
       │                                              │                            │
       └────────────────────────────────────────────────────────────────────────────────────
                                                      │
                                                      ▼
                                              ┌─────────────────┐
                                              │   DynamoDB      │
                                              │   (Job Store)   │
                                              │   + TTL (24h)   │
                                              └─────────────────┘
                                                      │
                                                      ▼
                                              ┌─────────────────┐
                                              │  RDS Postgres   │
                                              │  (Flight Data)  │
                                              └─────────────────┘
```

## Key Concepts

### AgentCore Runtime vs Lambda

**AgentCore Runtime:**
- ✅ AWS-managed serverless service for hosting AI agents
- ✅ Runs Strands SDK agent code
- ✅ Executes tools alongside agent
- ✅ Handles LLM orchestration
- ❌ Not directly accessible via API Gateway

**Proxy Lambda:**
- ✅ Standard AWS Lambda function
- ✅ Handles API Gateway routing
- ✅ Manages async job tracking
- ✅ Calls AgentCore Runtime via SDK
- ❌ Does NOT run agent or tools

### Why Two Components?

1. **AgentCore Runtime** hosts the agent (like Lambda hosts functions)
2. **Proxy Lambda** provides API Gateway integration + async polling

This is similar to how you'd use Lambda + Step Functions - each has a specific role.

## Deployment Order

### 1. Create DynamoDB Table

```bash
aws dynamodb create-table \
  --table-name flight-email-parse-jobs \
  --attribute-definitions AttributeName=jobId,AttributeType=S \
  --key-schema AttributeName=jobId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-west-2

# Enable TTL
aws dynamodb update-time-to-live \
  --table-name flight-email-parse-jobs \
  --time-to-live-specification "Enabled=true, AttributeName=expireAt"
```

### 2. Deploy AgentCore Agent

```bash
cd agentcore-runtime/parse-email-flight

# Install dependencies
pip install -r requirements.txt -t package/

# Create deployment package
zip -r agent.zip handler.py strand_agent.py tools.py db.py config.py package/

# Deploy to AgentCore Runtime
aws bedrock-agentcore create-agent \
  --agent-name parse-email-flight \
  --runtime-arn "arn:aws:lambda:us-west-2:ACCOUNT:function:agentcore-runtime" \
  --deployment-package fileb://agent.zip \
  --handler handler.lambda_handler \
  --environment Variables="{
    DB_SECRET_ARN=arn:aws:secretsmanager:...,
    RAPIDAPI_KEY=your-key,
    MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0
  }"

# Note the AGENT_ID returned (e.g., abc-123-def)
```

### 3. Deploy Proxy Lambda

```bash
cd lambdas/proxy-email-parser-agent

# Create deployment package
zip -r proxy.zip handler.py

# Create Lambda
aws lambda create-function \
  --function-name proxy-email-parser-agent \
  --runtime python3.12 \
  --handler handler.lambda_handler \
  --role arn:aws:iam::ACCOUNT:role/lambda-exec-role \
  --zip-file fileb://proxy.zip \
  --timeout 60 \
  --memory-size 256 \
  --environment Variables="{
    AGENTCORE_AGENT_ID=abc-123-def,
    AGENTCORE_AGENT_ALIAS_ID=prod,
    DYNAMODB_TABLE_NAME=flight-email-parse-jobs,
    BEDROCK_REGION=us-west-2
  }"

# Attach IAM policy
aws iam put-role-policy \
  --role-name lambda-exec-role \
  --policy-name EmailParserPolicy \
  --policy-document file://iam-policy.json
```

### 4. Configure API Gateway

```bash
# Add POST route
aws apigatewayv2 create-route \
  --api-id <api-id> \
  --route-key "POST /parse-email-and-store" \
  --target "integrations/INTEGRATION_ID" \
  --authorization-type JWT \
  --authorizer-id lqe0wb

# Add GET status route
aws apigatewayv2 create-route \
  --api-id <api-id> \
  --route-key "GET /parse-email-and-store/status/{jobId}" \
  --target "integrations/INTEGRATION_ID" \
  --authorization-type JWT \
  --authorizer-id lqe0wb

# Update WAF rules if needed
```

## Tool Workflow

When the agent is invoked, it processes the email through these tools:

### 1. validate_flight_exists(iata_code, date)
- Calls RapidAPI AeroDataBox to verify flight is real
- Returns: `{exists: true/false, details: {...}}`
- Used to prevent storing fake flights

### 2. check_duplicate_flight(user_sub, iata_code, date)
- Queries RDS Postgres for existing matching record
- Returns: `{is_duplicate: true/false, existing_id: ...}`
- Prevents duplicate entries

### 3. store_validated_flight(user_sub, flight_details)
- Inserts new flight record into Postgres
- Returns: `{success: true, record_id: ...}`
- Only called if flight is valid AND not duplicate

## Structured Output

The agent returns `EmailParseResult` via session attributes:

```python
{
  "total_found": 3,           # Flights detected in email
  "stored_count": 2,          # Successfully stored
  "duplicate_count": 1,       # Skipped (already in DB)
  "failed_count": 0,          # Failed validation
  "stored_flights": [         # Details of stored flights
    {
      "iata_code": "UA234",
      "flight_date": "2026-01-25",
      "record_id": 123
    }
  ],
  "duplicate_flights": [...], # Skipped flights
  "failed_flights": [...]     # Invalid flights
}
```

## Frontend Integration Points

### 1. Add Toggle in FlightForm.jsx

```jsx
import { ToggleButtonGroup, ToggleButton } from '@mui/material';

const [inputMode, setInputMode] = useState('code'); // 'code' or 'email'

<ToggleButtonGroup
  value={inputMode}
  exclusive
  onChange={(e, val) => setInputMode(val)}
>
  <ToggleButton value="code">Enter IATA Code</ToggleButton>
  <ToggleButton value="email">Paste Email</ToggleButton>
</ToggleButtonGroup>

{inputMode === 'email' ? (
  <TextField
    multiline
    rows={8}
    label="Flight confirmation email"
    value={emailText}
    onChange={(e) => setEmailText(e.target.value)}
  />
) : (
  // Existing IATA code + date inputs
)}
```

### 2. Add API Call in api.js

```javascript
export const parseFlightEmail = async ({ emailText, userSub, idToken }) => {
  const response = await fetch(`${API_BASE_URL}/parse-email-and-store`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${idToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ email_text: emailText })
  });
  return response.json();
};

export const pollEmailParseResult = async ({ jobId, idToken, onProgress }) => {
  const MAX_ATTEMPTS = 75; // 5 minutes
  const POLL_INTERVAL = 4000; // 4 seconds
  
  for (let i = 0; i < MAX_ATTEMPTS; i++) {
    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL));
    
    const response = await fetch(
      `${API_BASE_URL}/parse-email-and-store/status/${jobId}`,
      { headers: { 'Authorization': `Bearer ${idToken}` } }
    );
    const data = await response.json();
    
    onProgress({
      status: data.status,
      attempts: i + 1,
      maxAttempts: MAX_ATTEMPTS
    });
    
    if (data.status === 'COMPLETED' || data.status === 'ERROR') {
      return data;
    }
  }
  
  throw new Error('Timeout waiting for email parsing');
};
```

### 3. Handle Submit in FlightForm.jsx

```javascript
const handleEmailSubmit = async () => {
  setLoading(true);
  
  try {
    const resp = await parseFlightEmail({
      emailText,
      userSub: user.sub,
      idToken: user.idToken
    });
    
    if (resp.jobId) {
      // Poll for results
      const result = await pollEmailParseResult({
        jobId: resp.jobId,
        idToken: user.idToken,
        onProgress: (progress) => {
          setProgressText(`Processing... ${progress.attempts}/${progress.maxAttempts}`);
        }
      });
      
      if (result.status === 'COMPLETED') {
        showSnackbar(`Stored ${result.stored_count} flights, ${result.duplicate_count} duplicates skipped`);
        refreshFlightTable();
      } else {
        showSnackbar(`Error: ${result.error}`, 'error');
      }
    }
  } catch (error) {
    showSnackbar('Failed to parse email', 'error');
  } finally {
    setLoading(false);
  }
};
```

## Testing

### Local Testing (AgentCore Agent)

```bash
cd agentcore-runtime/parse-email-flight

# Set environment variables
export USER_SUB=test-user-123
export DB_DIRECT_HOST=127.0.0.1
export DB_DIRECT_PORT=5432
export DB_DIRECT_NAME=mydb
export DB_DIRECT_USER=myuser
export DB_DIRECT_PASSWORD=mypass
export RAPIDAPI_KEY=your-key

# Test with sample email
python3 -c "
import asyncio
from handler import lambda_handler

event = {
    'inputText': '''
    Your flight UA234 on January 25, 2026 from SFO to JFK
    Also booked: AA100 on Feb 10, 2026 LAX-ORD
    ''',
    'sessionAttributes': {
        'user_sub': 'test-user-123',
        'user_email': 'test@example.com'
    }
}

result = asyncio.run(lambda_handler(event, None))
print(result)
"
```

### End-to-End Testing

```bash
# 1. Submit email
curl -X POST https://<api-id>.execute-api.us-west-2.amazonaws.com/prod/parse-email-and-store \
  -H "Authorization: Bearer ${ID_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "email_text": "Your flight UA234 on Jan 25, 2026 from SFO to JFK"
  }'
# Returns: {"jobId": "abc-123", "status": "PENDING"}

# 2. Poll status
while true; do
  curl https://<api-id>.execute-api.us-west-2.amazonaws.com/prod/parse-email-and-store/status/abc-123 \
    -H "Authorization: Bearer ${ID_TOKEN}"
  sleep 4
done
```

## Monitoring

### CloudWatch Logs

```bash
# Proxy Lambda logs
aws logs tail /aws/lambda/proxy-email-parser-agent --follow

# AgentCore agent logs
aws logs tail /aws/agentcore/parse-email-flight --follow
```

### Key Metrics

- **Job latency**: Time from PENDING → COMPLETED (target: <60s)
- **Success rate**: COMPLETED / (COMPLETED + ERROR)
- **Storage rate**: stored_count / total_found
- **Duplicate rate**: duplicate_count / total_found

## Cost Estimates

- **AgentCore Runtime**: $0.00002 per second of agent execution (~$0.001/request)
- **Proxy Lambda**: Minimal (free tier covers most usage)
- **DynamoDB**: On-demand, ~$0.000001/request
- **Claude 3.5 Haiku**: ~$0.001/request (via Bedrock)

**Total**: ~$0.002-0.003 per email parsed

## Troubleshooting

### Job stuck in PENDING
- Check proxy Lambda CloudWatch logs for async invocation errors
- Verify Lambda has permission to invoke itself
- Check DynamoDB for job record

### Job status ERROR with "Agent not found"
- Verify AGENTCORE_AGENT_ID is correct
- Ensure AgentCore agent is deployed and active
- Check IAM policy allows bedrock-agentcore-runtime:InvokeAgent

### Flights not being stored
- Check AgentCore agent logs for tool execution errors
- Verify RDS connection (security groups, VPC)
- Check DB_SECRET_ARN is correct
- Test direct tool execution locally

### RapidAPI validation failures
- Verify RAPIDAPI_KEY is valid
- Check AeroDataBox API quota
- Look for rate limiting errors

## Next Steps

1. ✅ Complete code implementation (DONE)
2. ⏳ Deploy DynamoDB table
3. ⏳ Deploy AgentCore agent
4. ⏳ Deploy proxy Lambda
5. ⏳ Configure API Gateway routes
6. ⏳ Add frontend toggle UI
7. ⏳ Test end-to-end with sample emails
8. ⏳ Monitor and iterate

