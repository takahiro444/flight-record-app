# talk-to-flight-record-mcp-backend

Lambda backend implementing an initial Model Context Protocol (MCP)-style surface + chat orchestration for flight record insights.

## Files
- `config.py` – Loads environment variables into a `Settings` dataclass.
- `db.py` – Secrets Manager retrieval + parameterized Postgres queries (mileage range, monthly summary, longest flights, stats overview).
- `tools.py` – Tool registry (metadata + runners) used by planning and direct execution.
- `agentcore_handler.py` – Lambda entry point for Bedrock AgentCore Action Group (operationId → tool runner).
- `action_group_schema.json` – OpenAPI schema for AgentCore action group (operations align with `tools.py`).
- `planning.py` – Bedrock planning call that outputs JSON `{"steps":[{"tool":"...","args":{}}]}` with fallback heuristics if disabled or failed.
- `answer.py` – Bedrock answer synthesis with graceful degradation if the model call errors.
- `handler.py` – Lambda entry point; routes:
  - `GET /mcp/resources`
  - `GET /mcp/resource/{id}` (schema, sample placeholder)
  - `GET /mcp/tools`
  - `POST /mcp/tool/execute` (requires user claims)
  - `POST /chat` (planning → tool execution → answer)

## Expected Environment Variables
| Name | Purpose |
|------|---------|
| DB_SECRET_ARN | ARN of Secrets Manager secret containing host/port/database/user/password |
| BEDROCK_MODEL_ID | Bedrock foundation model ID (e.g. `anthropic.claude-3-haiku-20240307-v1:0`) |
| MAX_TOOL_ROWS | Safety cap for future tools (not yet enforced in current queries) |
| ENABLE_STREAMING | Reserved for streaming responses (false for now) |
| LOG_LEVEL | info/debug control (not yet wired to structured logger) |
| STAGE | Environment stage label (prod/dev) |
| MCP_ENABLE_PLANNING | Toggle planning call; false uses heuristic fallback |
| PLAN_MAX_TOKENS | Max tokens for planning completion |
| ANSWER_MAX_TOKENS | Max tokens for answer completion |
| COST_LOG_ENABLED | Future feature flag for cost telemetry |
| DB_CONNECT_TIMEOUT_SECONDS | Psycopg connection timeout |
| DB_APP_NAME | Postgres application_name for audit |

## Security Notes
- All queries filtered by `user_sub` extracted from Cognito authorizer claims; no anonymous execution.
- Tool interface prevents arbitrary SQL; only defined, parameterized functions execute.
- Secrets cached in-memory during Lambda lifetime to reduce latency.

## Deployment Notes
1. Create & publish dependency Lambda layer (see Layer Instructions below) OR use a container image.
2. Ensure IAM role grants: `bedrock:InvokeModel`, `secretsmanager:GetSecretValue`, and VPC ENI permissions (via AWSLambdaVPCAccessExecutionRole or inline).
3. Configure API Gateway (HTTP API or REST) with Lambda proxy integration for routes listed above.
4. Attach Cognito authorizer to `/chat` and MCP tool execution paths so claims reach Lambda.
5. Set required environment variables (see table above) and add the layer ARN to function configuration.

### AgentCore (Bedrock Agents) path
Use this when deploying an action group to Bedrock Agents without the Strands SDK.

1. Package Lambda code with `agentcore_handler.py`, `tools.py`, `db.py`, `config.py` and dependencies from `requirements-agentcore.txt` (pg8000 only; boto3 provided by the runtime). Entry point: `agentcore_handler.lambda_handler`.
2. Configure environment variables: `DB_SECRET_ARN` (required), `DB_CONNECT_TIMEOUT_SECONDS` (optional, default 3), `DB_APP_NAME` (optional, default `flight-mcp`).
3. Networking: attach the Lambda to private subnets that can reach RDS; allow SG egress to the RDS SG on port 5432; RDS SG should allow ingress from the Lambda SG.
4. IAM: execution role with AWSLambdaVPCAccessExecutionRole managed policy + `secretsmanager:GetSecretValue` for the DB secret + CloudWatch Logs.
5. Action Group schema: upload `action_group_schema.json` when creating the action group in the Bedrock console. The `operationId` values match the tool names in `tools.py`.
6. User identity: provide `user_sub` via `sessionAttributes` or `promptSessionAttributes` when calling InvokeAgent; the handler also accepts it in the request body if you map claims there.
7. Test in the Bedrock console: e.g., "Give me a brief stats overview and monthly mileage for 2025." Expect tool invocations logged in CloudWatch.

### Layer Instructions

Generated artifacts:
- `lambdas/talk-to-flight-record-mcp-backend/requirements.txt` – pinned dependency list.
- `scripts/build-mcp-layer.sh` – builds `layer.zip` under `layer_build/` (uses Docker if available for Amazon Linux compatibility).

Build (macOS / Linux):
```bash
./scripts/build-mcp-layer.sh 3.11
```

Publish layer:
```bash
aws lambda publish-layer-version \
  --layer-name flight-record-mcp-deps \
  --compatible-runtimes python3.11 \
  --zip-file fileb://layer_build/layer.zip \
  --description "Deps for talk-to-flight-record-mcp-backend"
```

Attach layer to function:
```bash
aws lambda update-function-configuration \
  --function-name talk-to-flight-record-mcp-backend \
  --layers <NEW_LAYER_ARN>
```

Notes:
- `psycopg2-binary` chosen for convenience; switch to compiled `psycopg2` if you need finer control.
- `boto3` pinned only if you require a newer Bedrock client than the runtime default.
- Remove unused packages (e.g. `jsonschema`) if size becomes an issue.

## Testing
Use a test event shaped like API Gateway proxy:
```json
{
  "rawPath": "/chat",
  "requestContext": {
    "http": {"method": "POST"},
    "authorizer": {"claims": {"sub": "USER_SUB_VALUE"}}
  },
  "body": "{\"question\": \"How many miles from 2025-04-01 to 2025-09-01?\"}"
}
```
Expect response with plan referencing `query_mileage_range` and parsed answer fallback if Bedrock not reachable.

## Future Enhancements
- Structured logging (JSON) with latency and token counts.
- Validation of input schemas (e.g. using `jsonschema` or `pydantic`).
- Streaming completions when `ENABLE_STREAMING=true`.
- Resource `sample_recent` implemented with a query for last N flights.
- Cost telemetry & tracing (AWS X-Ray).

