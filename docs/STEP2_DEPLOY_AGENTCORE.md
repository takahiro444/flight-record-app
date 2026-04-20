# Step 2: Deploy Strands Agent to Amazon Bedrock AgentCore Runtime

## What is AgentCore Runtime?

**Amazon Bedrock AgentCore Runtime** is a serverless compute service specifically designed for hosting AI agents. Think of it like AWS Lambda, but purpose-built for AI agents with:
- **Session isolation**: Each user gets a dedicated microVM
- **Auto-scaling**: Handles thousands of concurrent sessions
- **Built-in observability**: CloudWatch metrics and traces
- **Pay-per-use**: Only charged for actual agent execution time

## Architecture

```
Frontend → API Gateway → Proxy Lambda → AgentCore Runtime
                            ↓                    ↓
                        DynamoDB            Strands Agent
                        (Job Store)         + Tools
                                               ↓
                                          RDS Postgres
```

---

## Part A: Install AgentCore CLI Tools

Run these commands in your terminal:

```bash
cd <project-root>/agentcore-runtime/parse-email-flight

# Install Python dependencies including AgentCore toolkit
pip install -r requirements.txt

# Verify agentcore CLI is available
agentcore --version
```

---

## Part B: Configure AgentCore Deployment

### 1. Set AWS Credentials

Ensure your AWS CLI is configured:

```bash
# Check current AWS identity
aws sts get-caller-identity

# If not configured, set credentials:
aws configure
# Enter: Access Key ID, Secret Access Key, Region (us-west-2), Output (json)
```

### 2. Configure Agent Entrypoint

```bash
cd <project-root>/agentcore-runtime/parse-email-flight

# Tell AgentCore which file to use as the entry point
agentcore configure --entrypoint agentcore_entrypoint.py
```

This creates a `.agentcore` configuration file with your deployment settings.

---

## Part C: Create IAM Role for AgentCore

AgentCore needs an IAM role to access AWS resources (RDS, Secrets Manager, Bedrock).

### AWS Console Steps:

1. **Go to IAM Console**: https://console.aws.amazon.com/iam
2. **Roles** → **Create role**
3. **Trusted entity type**: AWS service
4. **Use case**: Select **"Bedrock"** (if not available, select "Lambda" temporarily)
5. **Permissions**: Attach these policies:
   - `SecretsManagerReadWrite` (for DB credentials)
   - `AmazonBedrockFullAccess` (for Claude model)
   - Click "Next"
6. **Role name**: `AgentCoreRuntimeRole`
7. **Create role**

8. **Add inline policy** for RDS:
   - Click the role you just created
   - **Add permissions** → **Create inline policy**
   - Click **JSON** tab and paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

   - **Policy name**: `RDSAndLogsAccess`
   - **Create policy**

9. **Copy the Role ARN** (looks like `arn:aws:iam::123456789012:role/AgentCoreRuntimeRole`)
   - You'll need this in the next step

---

## Part D: Deploy to AgentCore Runtime

### Option 1: Deploy via CLI (Recommended)

```bash
cd <project-root>/agentcore-runtime/parse-email-flight

# Deploy to AWS (this packages and uploads your agent)
agentcore launch \
  --role-arn arn:aws:iam::YOUR_ACCOUNT:role/AgentCoreRuntimeRole \
  --region us-west-2 \
  --environment DB_SECRET_ARN=arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:your-secret \
  --environment RAPIDAPI_KEY=your-rapidapi-key \
  --environment MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0 \
  --environment STRANDS_TIMEOUT=120 \
  --environment BEDROCK_REGION=us-west-2
```

**What this does:**
1. Packages your agent code + dependencies
2. Builds a Docker container (ARM64)
3. Pushes to ECR
4. Creates AgentCore Runtime resource
5. Returns Agent Runtime ARN

**Expected output:**
```
✅ Agent deployed successfully!
Agent Runtime ARN: arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/parse-email-flight-abc123
Runtime Session ID Format: Use any string with 33+ characters
```

**Save these values** - you'll need them for Step 3!

### Option 2: Deploy via Console (Alternative)

If CLI doesn't work, use manual deployment:

#### 2.1: Build Docker Image Locally

```bash
cd <project-root>/agentcore-runtime/parse-email-flight

# Create Dockerfile
cat > Dockerfile <<'EOF'
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY agentcore_entrypoint.py .
COPY strand_agent.py .
COPY tools.py .
COPY db.py .
COPY config.py .

# Expose port
EXPOSE 8080

# Run with bedrock-agentcore runtime
CMD ["python", "agentcore_entrypoint.py"]
EOF

# Setup Docker buildx for ARM64
docker buildx create --use --name agentcore-builder

# Build image
docker buildx build \
  --platform linux/arm64 \
  -t parse-email-agent:latest \
  --load .
```

#### 2.2: Push to ECR

```bash
# Get your AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create ECR repository
aws ecr create-repository \
  --repository-name parse-email-agent \
  --region us-west-2

# Login to ECR
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  ${ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com

# Tag and push
docker tag parse-email-agent:latest \
  ${ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/parse-email-agent:latest

docker push ${ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/parse-email-agent:latest
```

#### 2.3: Create AgentCore Runtime via Console

1. **Go to Bedrock Console**: https://console.aws.amazon.com/bedrock
2. **Left sidebar** → **AgentCore** → **Runtimes**
3. Click **Create runtime**

**Runtime details:**
- **Runtime name**: `parse-email-agent`
- **Description**: `Strands agent for parsing flight confirmation emails`

**Runtime artifact:**
- **Artifact type**: Container
- **Container URI**: `123456789012.dkr.ecr.us-west-2.amazonaws.com/parse-email-agent:latest`

**Network configuration:**
- **Network mode**: PUBLIC (or VPC if your RDS is in VPC)

**IAM role:**
- Select: `AgentCoreRuntimeRole` (created in Part C)

**Environment variables:**
- Click **Add environment variable** for each:
  - `DB_SECRET_ARN` = `arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:your-secret`
  - `RAPIDAPI_KEY` = `your-rapidapi-key`
  - `MODEL_ID` = `anthropic.claude-3-5-haiku-20241022-v1:0`
  - `STRANDS_TIMEOUT` = `120`
  - `BEDROCK_REGION` = `us-west-2`

**Create runtime**

Wait 2-3 minutes for status to become **ACTIVE**.

---

## Part E: Test the Agent

### Via CLI:

```bash
# Test invocation
agentcore invoke '{
  "prompt": "Your flight UA234 on January 25, 2026 from San Francisco to New York",
  "sessionAttributes": {
    "user_sub": "test-user-123",
    "user_email": "test@example.com"
  }
}'
```

### Via Python Script:

Create `test_agent.py`:

```python
import boto3
import json

# Initialize client
client = boto3.client('bedrock-agentcore', region_name='us-west-2')

# Your agent runtime ARN (from deployment output)
agent_runtime_arn = 'arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/parse-email-flight-abc123'

# Create payload
payload = json.dumps({
    "prompt": "Your flight UA234 on January 25, 2026 from SFO to JFK",
    "sessionAttributes": {
        "user_sub": "test-user-123",
        "user_email": "test@example.com"
    }
})

# Invoke agent
response = client.invoke_agent_runtime(
    agentRuntimeArn=agent_runtime_arn,
    runtimeSessionId='test-session-12345678901234567890123456789012',  # Min 33 chars
    payload=payload
)

# Read response
response_body = response['response'].read()
result = json.loads(response_body)

print("Agent Response:")
print(json.dumps(result, indent=2))
```

Run it:
```bash
python test_agent.py
```

**Expected Response:**
```json
{
  "status": "success",
  "total_found": 1,
  "stored_count": 1,
  "duplicate_count": 0,
  "failed_count": 0,
  "stored_flights": [
    {
      "iata_code": "UA234",
      "flight_date": "2026-01-25",
      "record_id": 123
    }
  ],
  "summary": "Found 1 flight, stored 1, 0 duplicates"
}
```

---

## Part F: Save Deployment Info

After successful deployment, note these values:

1. **Agent Runtime ARN**: `arn:aws:bedrock-agentcore:us-west-2:ACCOUNT:runtime/parse-email-flight-XXXXX`
2. **Region**: `us-west-2`
3. **IAM Role ARN**: `arn:aws:iam::ACCOUNT:role/AgentCoreRuntimeRole`

These will be used in Step 3 to configure the proxy Lambda.

---

## Troubleshooting

### "agentcore: command not found"
```bash
pip install --upgrade bedrock-agentcore-starter-toolkit
# Or add to PATH:
export PATH="$PATH:$HOME/.local/bin"
```

### "Permission denied" during deployment
- Verify IAM user has permissions to create ECR repos, AgentCore runtimes
- Check role trust policy allows AgentCore service

### "Container failed health check"
- Check CloudWatch Logs: `/aws/bedrock-agentcore/parse-email-flight`
- Verify environment variables are set correctly
- Test locally first: `python agentcore_entrypoint.py`

### "Tools failing with DB connection errors"
- Verify DB_SECRET_ARN is correct
- Check security groups allow AgentCore to reach RDS
- If RDS is in VPC, use VPC network mode for AgentCore

---

## Cost Estimate

**AgentCore Runtime:**
- $0.00002 per second of execution
- Average email parse: ~10 seconds = $0.0002
- 1000 requests/month ≈ $0.20

**Storage:**
- ECR image storage: ~500MB ≈ $0.05/month

**Total**: ~$0.25/month + CloudWatch logs (minimal)

---

Once you have the **Agent Runtime ARN** from this step, you're ready for **Step 3: Deploy Proxy Lambda**!

Let me know when you've completed Step 2 or if you encounter any issues.
