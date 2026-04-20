# Creating a Fresh Bedrock AgentCore Runtime

## Problem
An existing Runtime consistently returns 502 errors with zero CloudWatch logs, suggesting the Runtime configuration is corrupted or incompatible.

## Solution: Create New Runtime

### Step 1: Delete Old Runtime
In AWS Console → Bedrock → AgentCore → Runtimes:
- Select the existing runtime
- Delete it

### Step 2: Create New Runtime

**Configuration:**
- Name: `parse-email-agent`
- Image URI: `<ecr-image-uri>:parse-email-agent-minimal-v2`
- IAM Role: `arn:aws:iam::<account-id>:role/AgentCoreRuntimeRole`

**VPC Configuration:**
- VPC: `<your-vpc-id>`
- Subnets:
  - `<subnet-id-1>`
  - `<subnet-id-2>`
- Security Group: `<security-group-id>`

**Environment Variables:**
```
BEDROCK_REGION=us-west-2
DB_SECRET_ARN=<your-secrets-manager-arn>
MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0
RAPIDAPI_KEY=<your-rapidapi-key>
STRANDS_TIMEOUT=120
```

### Step 3: Update Lambda Environment Variable

After creating the new Runtime, note its ARN and update the proxy Lambda:
```bash
aws lambda update-function-configuration \
  --function-name proxy-email-parser-agent \
  --region us-west-2 \
  --environment Variables="{AGENTCORE_RUNTIME_ARN=<NEW_RUNTIME_ARN>,...}"
```

### Step 4: Test

Test the minimal image first:
1. In Bedrock console, test Runtime with: `{"prompt": "test"}`
2. Should return: `{"status": "success", "message": "Minimal runtime is working!"}`
3. Check CloudWatch logs - should see "Minimal entrypoint loaded successfully"

If minimal works, then update to full image:
```
<ecr-image-uri>:parse-email-agent
```

## Why This Is Necessary

If a Runtime has been updated many times across multiple image versions and consistently fails to start the container, it may indicate:
- Internal Runtime state corruption
- Incompatibility introduced by repeated updates
- Cached configuration preventing proper image pull

Creating a fresh Runtime ensures clean state and proper initialization.
