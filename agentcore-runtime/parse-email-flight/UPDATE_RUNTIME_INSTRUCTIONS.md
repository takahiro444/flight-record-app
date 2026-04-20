# AgentCore Runtime Update Instructions

## Problem
The AgentCore Runtime is failing with "API validation and database connectivity error" despite having RAPIDAPI_KEY configured correctly in environment variables.

## Solution
The Runtime needs to use the new debug image that includes detailed error logging.

## New Image Available in ECR
**Image URI:** `<ecr-image-uri>:parse-email-agent-debug`

## Changes in Debug Image
Enhanced error logging in `tools.py`:
- **validate_flight_exists()**: Logs API key presence, request URL, response status, and detailed error messages
- **check_duplicate_flight()**: Logs database connection status, query execution, and stack traces on errors

## Steps to Update Runtime via AWS Console

### 1. Navigate to Bedrock AgentCore Runtime
```
AWS Console → Bedrock → AgentCore → Runtimes → <your-agent-runtime-id>
```

### 2. Update Image
Click "Edit" or "Update" button, then:
- Change **Container Image URI** to: `<ecr-image-uri>:parse-email-agent-debug`
- Keep all other settings unchanged:
  - Network Mode: VPC
  - Subnets: `<subnet-id-1>`, `<subnet-id-2>`
  - Security Group: `<security-group-id>`
  - Environment Variables: RAPIDAPI_KEY, MODEL_ID, etc.

### 3. Save and Wait for Deployment
- Click "Save" or "Update"
- Wait for Runtime status to return to "READY" (may take 2-5 minutes)

### 4. Test with Enhanced Logging
Run test script:
```bash
python3 scripts/test-agentcore-direct.py
```

### 5. Check CloudWatch Logs for Details
```bash
aws logs filter-log-events \
  --log-group-name /aws/bedrock-agentcore/runtimes/<your-agent-runtime-id>-DEFAULT \
  --start-time $(($(date +%s) - 600))000 \
  --region us-west-2 \
  --max-items 100 \
  | jq -r '.events[] | .message'
```

Look for log entries like:
- `[VALIDATE] API key present: True, length: 60`
- `[VALIDATE] Calling AeroDataBox API: https://...`
- `[VALIDATE] Response status: 200`
- `[VALIDATE] API error: ConnectionError: ...` (if failing)
- `[DUPLICATE_CHECK] Database connection established` (if successful)
- `[DUPLICATE_CHECK] Database error: OperationalError: ...` (if failing)

## Expected Outcomes

### If API Key Not Loaded
Logs will show: `[VALIDATE] API key present: False, length: 0`
**Fix:** Verify environment variables in console, restart Runtime

### If VPC Blocks External API
Logs will show: `[VALIDATE] API error: ConnectionError: ... timeout`
**Fix:** Check security group `<security-group-id>` allows outbound HTTPS (443) to 0.0.0.0/0

### If Database Connection Fails
Logs will show: `[DUPLICATE_CHECK] Database error: OperationalError: ... connection refused`
**Fix:** Check RDS security group allows inbound 5432 from `<security-group-id>`

### If Everything Works
Logs will show: `[VALIDATE] Response status: 200` and `[DUPLICATE_CHECK] Database connection established`
Result: Flights stored successfully

## Security Group Checks

### Runtime Security Group
Navigate to: **EC2 → Security Groups → `<security-group-id>`**

**Required Outbound Rules:**
```
Type: HTTPS (443)
Protocol: TCP
Port: 443
Destination: 0.0.0.0/0
Description: Allow RapidAPI access
```

### RDS Security Group
Navigate to: **RDS → Databases → `<your-rds-instance>` → VPC security groups**

**Required Inbound Rules:**
```
Type: PostgreSQL (5432)
Protocol: TCP
Port: 5432
Source: <security-group-id>
Description: Allow AgentCore Runtime access
```

## Alternative: Create New Runtime

If updating the existing Runtime is not possible via console, create a new one:

### Create New Runtime via Console
1. Go to **Bedrock → AgentCore → Runtimes → Create Runtime**
2. Fill in:
   - Name: `parse-email-agent-debug-v2`
   - Image URI: `<ecr-image-uri>:parse-email-agent-debug`
   - Network Mode: VPC
   - Subnets: `<subnet-id-1>`, `<subnet-id-2>`
   - Security Group: `<security-group-id>`
3. Add Environment Variables (values from your `.env` or Secrets Manager):
   ```
   RAPIDAPI_KEY=<your-rapidapi-key>
   MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0
   BEDROCK_REGION=us-west-2
   DB_SECRET_ARN=<your-secrets-manager-arn>
   ```
4. Create and wait for status "READY"
5. Copy new Runtime ARN

### Update Lambda to Use New Runtime
```bash
aws lambda update-function-configuration \
  --function-name proxy-email-parser-agent \
  --region us-west-2 \
  --environment "Variables={AGENTCORE_RUNTIME_ARN=<NEW_RUNTIME_ARN>,...}"
```

## Troubleshooting Commands

### Check Runtime Status
```bash
aws bedrock-agentcore get-agent-runtime \
  --agent-runtime-arn arn:aws:bedrock-agentcore:<region>:<account-id>:runtime/<your-agent-runtime-id> \
  --region us-west-2
```

### Test Direct Invocation
```bash
python3 scripts/test-agentcore-direct.py
```

### Check Recent Logs
```bash
aws logs filter-log-events \
  --log-group-name /aws/bedrock-agentcore/runtimes/<your-agent-runtime-id>-DEFAULT \
  --start-time $(($(date +%s) - 3600))000 \
  --region us-west-2 \
  | jq '.events[] | {time: (.timestamp/1000 | strftime("%H:%M:%S")), message}'
```

### Verify ECR Image
```bash
aws ecr describe-images \
  --repository-name flight-record-app \
  --image-ids imageTag=parse-email-agent-debug \
  --region us-west-2
```

## Expected Debug Output

When working correctly, logs should show:
```
[VALIDATE] API key present: True, length: 60
[VALIDATE] Calling AeroDataBox API: https://aerodatabox.p.rapidapi.com/flights/number/AS521/2026-01-06?dateLocalRole=Departure
[VALIDATE] Response status: 200
[DUPLICATE_CHECK] Starting for AS521 on 2026-01-06
[DUPLICATE_CHECK] Database connection established
[STORE] Starting store for AS521 on 2026-01-06
[STORE] Database connection established successfully
[STORE] Executing INSERT query...
```
