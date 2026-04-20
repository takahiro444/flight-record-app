#!/bin/bash
# Update AgentCore Runtime with Environment Variables.
# Copy this script and fill in the placeholder values for your deployment.
# Required env vars / placeholders to set before running:
#   AGENT_RUNTIME_ID  - your AgentCore runtime ID
#   ECR_IMAGE_URI     - your ECR container image URI
#   ROLE_ARN          - IAM role ARN for AgentCore
#   SUBNET_IDS        - comma-separated subnet IDs (JSON array format)
#   SECURITY_GROUP_ID - security group ID
#   DB_SECRET_ARN     - Secrets Manager ARN for DB credentials
#   RAPIDAPI_KEY      - your RapidAPI key (set via environment, not in this file)

AGENT_RUNTIME_ID="${AGENT_RUNTIME_ID:-<your-agent-runtime-id>}"
ECR_IMAGE_URI="${ECR_IMAGE_URI:-<your-ecr-image-uri>}"
ROLE_ARN="${ROLE_ARN:-<your-role-arn>}"
SUBNET_IDS="${SUBNET_IDS:-<subnet-id-1>\",\"<subnet-id-2>}"
SECURITY_GROUP_ID="${SECURITY_GROUP_ID:-<your-security-group-id>}"
DB_SECRET_ARN="${DB_SECRET_ARN:-<your-secrets-manager-arn>}"
RAPIDAPI_KEY="${RAPIDAPI_KEY:-}"

if [ -z "$RAPIDAPI_KEY" ]; then
    echo "⚠️  ERROR: Set the RAPIDAPI_KEY environment variable before running."
    exit 1
fi

echo "Updating AgentCore Runtime: $AGENT_RUNTIME_ID"
echo "Using RapidAPI Key: ${RAPIDAPI_KEY:0:10}... (hidden)"
echo ""

aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id "$AGENT_RUNTIME_ID" \
  --region us-west-2 \
  --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"$ECR_IMAGE_URI\"}}" \
  --role-arn "$ROLE_ARN" \
  --network-configuration "{\"networkMode\":\"VPC\",\"vpcConfiguration\":{\"subnetIds\":[\"$SUBNET_IDS\"],\"securityGroupIds\":[\"$SECURITY_GROUP_ID\"]}}" \
  --environment-variables "{
    \"DB_SECRET_ARN\":\"$DB_SECRET_ARN\",
    \"RAPIDAPI_KEY\":\"$RAPIDAPI_KEY\",
    \"MODEL_ID\":\"anthropic.claude-3-5-haiku-20241022-v1:0\",
    \"STRANDS_TIMEOUT\":\"120\",
    \"BEDROCK_REGION\":\"us-west-2\"
  }"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Runtime updated successfully!"
    echo ""
    echo "Verifying configuration..."
    sleep 3
    aws bedrock-agentcore-control get-agent-runtime \
      --agent-runtime-id "$AGENT_RUNTIME_ID" \
      --region us-west-2 \
      --query '{Status:status,EnvVars:environmentVariables}' \
      --output json
else
    echo ""
    echo "❌ Update failed. Check error message above."
    exit 1
fi
