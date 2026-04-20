# Multi-Agent Trace Display Implementation

## Overview
Added UI feature to display which Bedrock agents were invoked for each user query in the Flight Agent Chat Window.

## Architecture Flow
```
User Query → API Gateway → Proxy Lambda → Supervisor Agent
                                              ↓
                                         ┌────┴────┐
                                         ↓         ↓
                              Flight-Record-Agent  Airline-Status-Agent
                                 ↓ RDS               ↓ Knowledge Base
```

## Implementation Details

### 1. Lambda Handler Updates (`lambdas/proxy-flight-record-bedrock-agent/handler.py`)

**Added Trace Capture:**
```python
# Enable trace in Bedrock agent invocation
response = bedrock_agent.invoke_agent(
    agentId=agent_id,
    agentAliasId=agent_alias_id,
    sessionId=session_id,
    inputText=question,
    enableTrace=True  # NEW: Enables trace events
)
```

**Parse Trace Events:**
```python
agents_invoked = []
for event in stream:
    if "trace" in event:
        trace = event["trace"]["trace"]
        if "orchestrationTrace" in trace:
            orch = trace["orchestrationTrace"]
            if "invocationInput" in orch:
                inv_input = orch["invocationInput"]
                if "collaboratorInvocationInput" in inv_input:
                    collab = inv_input["collaboratorInvocationInput"]
                    if "collaboratorName" in collab:
                        agent_name = collab["collaboratorName"]
                        if agent_name not in agents_invoked:
                            agents_invoked.append(agent_name)
```

**Return Metadata:**
```python
return {
    'statusCode': 200,
    'body': json.dumps({
        "answer": final_answer,
        "agents_invoked": agents_invoked  # NEW: Array of agent names
    })
}
```

### 2. React ChatWidget Updates (`flight-record-app/client/src/components/ChatWidget.jsx`)

**Added Chip Component:**
```jsx
import { Chip } from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
```

**Store Agent Metadata:**
```jsx
const resp = await postFlightChat({ question: q, userSub, idToken });
const answer = resp?.answer || '(no answer returned)';
const agentsInvoked = resp?.agents_invoked || [];
setMessages(prev => [...prev, { 
  role: 'assistant', 
  text: answer, 
  agents_invoked: agentsInvoked  // Store in message
}]);
```

**Display Agent Badges:**
```jsx
{m.role === 'assistant' && m.agents_invoked && m.agents_invoked.length > 0 && (
  <Box sx={{ mb: 0.5, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
    {m.agents_invoked.map((agent, i) => (
      <Chip
        key={i}
        label={agent}
        size="small"
        icon={<SmartToyIcon />}
        color="secondary"
        variant="outlined"
        sx={{ fontSize: '0.7rem', height: 22 }}
      />
    ))}
  </Box>
)}
```

## Expected Behavior

### Query Type 1: Flight Data Only
**User:** "How many miles did I fly in 2024?"
**Agents Invoked:** `["Flight-Record-Agent"]`
**UI Display:** Single chip with "Flight-Record-Agent" label above response

### Query Type 2: Airline Documentation Only
**User:** "What are United Gold status requirements?"
**Agents Invoked:** `["Airline-Status-Agent"]`
**UI Display:** Single chip with "Airline-Status-Agent" label above response

### Query Type 3: Collaborative
**User:** "Based on my flights, what status do I qualify for?"
**Agents Invoked:** `["Flight-Record-Agent", "Airline-Status-Agent"]`
**UI Display:** Two chips above response showing both agents

## Testing

### 1. Manual Testing via React UI
1. Start dev server: `cd flight-record-app/client && npm start`
2. Login with Cognito credentials
3. Open chat widget (floating blue button)
4. Test three query types above
5. Verify agent badges appear correctly

### 2. API Testing via Script
```bash
# Set credentials
export ID_TOKEN="<cognito-id-token>"
export USER_SUB="<user-sub-claim>"

# Run test script
./scripts/test-multi-agent-traces.sh
```

Expected output includes `agents_invoked` array in JSON response for each query.

## Deployment Status

✅ **Lambda:** Deployed to `proxy-flight-record-bedrock-agent` (us-west-2)
   - Last Updated: 2026-01-15T22:14:20.000+0000
   - CodeSha256: iYRI54jWuwwpL98K/PXNNCdlOvprI+9cs2SWxJ508+Q=

⏳ **React App:** Code updated, needs deployment to S3
   ```bash
   cd flight-record-app/client
   npm run build
   ./scripts/deploy-app.sh your-s3-bucket-name app
   ```

## Configuration

### Agent IDs (Environment Variables in Lambda)
Set these from your own Bedrock Agent deployment:
- **Supervisor:** `AGENT_ID=<supervisor-agent-id>`, `AGENT_ALIAS_ID=<supervisor-alias-id>`
- **Collaborators:**
  - Flight-Record-Agent: `<flight-record-agent-id>` (alias: `<flight-record-alias-id>`)
  - Airline-Status-Agent: `<airline-status-agent-id>` (alias: `<airline-status-alias-id>`)

### Multi-Agent Collaboration Settings (in Bedrock Console)
- Supervisor can invoke both collaborator agents via IAM policy
- Policy: `bedrock:InvokeAgent` for both agent ARNs

## Troubleshooting

### No agents_invoked in Response
**Cause:** Trace events not captured or supervisor not invoking collaborators
**Fix:** 
1. Verify `enableTrace=True` in Lambda handler
2. Check CloudWatch logs for trace event structure
3. Confirm supervisor has multi-agent collaboration enabled

### Wrong Agent Invoked
**Cause:** Supervisor instruction unclear about routing logic
**Fix:** Update supervisor agent instruction with explicit routing examples

### UI Not Showing Badges
**Cause:** React component not receiving `agents_invoked` from API
**Fix:** 
1. Inspect network response in browser DevTools
2. Verify `postFlightChat` utility returns full response
3. Check console for JavaScript errors

## Future Enhancements

1. **Visual Flow Diagram:** Show agent execution sequence with arrows (Supervisor → Flight → Airline)
2. **Timing Metrics:** Display execution time for each agent
3. **Expandable Details:** Click chip to see agent's specific actions/queries
4. **Agent Icons:** Different icons for different agent types (database vs knowledge base)
5. **Color Coding:** Different chip colors per agent type
