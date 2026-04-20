# proxy-flight-record-bedrock-agent

A lightweight Lambda proxy that forwards chat requests to the Bedrock Agent via `bedrock-agent-runtime`.

## Environment variables
- `AGENT_ID` (required): Bedrock Agent ID from your deployment
- `AGENT_ALIAS_ID` (optional but recommended): Alias ID from your deployment
- `BEDROCK_REGION` (optional): Defaults to `AWS_REGION` or `us-west-2`

## Request shape
POST `/chat` or `/proxy/chat`
```json
{
  "question": "Give me a brief stats overview and monthly mileage for 2024."
}
```

The proxy expects `user_sub` from the Cognito authorizer claims (`sub` or `cognito:username`). Optionally you can pass `user_sub` in the JSON body for testing.

## Response shape
```json
{
  "answer": "...agent response text...",
  "sessionId": "<uuid>"
}
```

## Deployment notes
- Runtime: Python 3.12
- Permissions for this function’s role:
  - `bedrock:InvokeAgent` (and Async/Session variants) on the target agent/alias ARN
- No external dependencies beyond the AWS SDK included in the Lambda runtime.
