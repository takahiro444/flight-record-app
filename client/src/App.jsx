import React, { useState } from 'react';
import { Container, CssBaseline, Typography, Button, AppBar, Toolbar, Chip, Paper, Accordion, AccordionSummary, AccordionDetails, Stack, Alert, Box } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FlightForm from './components/FlightForm';
import FlightTable from './components/FlightTable';
import Layout from './components/Layout';
import ChatWidget from './components/ChatWidget';
import useFlights from './hooks/useFlights';
import { useAuth } from './auth/AuthContext';
import planeLogo from './assets/airplane.svg';

const App = () => {
  const [apiKeyLocal, setApiKeyLocal] = useState('');
  const { flightResponse, records, filtered, loading, error, recordsMeta, rawRecordsResponse, fetchFlightData, fetchFlightRecords } = useFlights();
  const { isAuthenticated, login, logout, authError, claims, idToken } = useAuth();

  const handleLoadRecords = () => {
    fetchFlightRecords(apiKeyLocal || null);
  };

  return (
    <Layout>
      <CssBaseline />
      <AppBar position="static" color="primary" elevation={1} sx={{ mb: 3 }}>
        <Toolbar>
          <Stack direction="row" alignItems="center" spacing={1.5} sx={{ flexGrow: 1 }}>
            <Box
              component="img"
              src={planeLogo}
              alt="Flight Record App logo"
              sx={{ height: 36, width: 'auto' }}
            />
            <Typography variant="h6">Flight Record App</Typography>
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center">
            {records?.length > 0 && (
              <Chip size="small" label={`${records.length} records`} variant="outlined" />
            )}
            {isAuthenticated && claims?.email && (
              <Chip size="small" color="success" label={claims.email} />
            )}
            {isAuthenticated && claims?.sub && (
              <Chip size="small" color="info" label={`sub:${claims.sub.substring(0,8)}…`} />
            )}
            {!isAuthenticated ? (
              <Button size="small" color="inherit" onClick={login}>Login</Button>
            ) : (
              <Button size="small" color="inherit" onClick={logout}>Logout</Button>
            )}
          </Stack>
        </Toolbar>
      </AppBar>
      <Container maxWidth="md" sx={{ pb: 6 }}>
        <Accordion defaultExpanded={false} sx={{ mb: 4 }} disableGutters elevation={1}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />} aria-controls="overview-content" id="overview-header">
            <Typography variant="subtitle1">Application Overview</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="body2" paragraph>
              This React frontend (Material UI) provides four primary capabilities: (1) submit a flight to be retrieved and stored, (2) <strong>parse confirmation emails</strong> to automatically extract and store flights, (3) view stored flight records, and (4) chat with multi-agent AI system for stats insights and airline status queries.
            </Typography>
            <Typography variant="body2" paragraph>
              Core REST paths (API Gateway <strong>FlightRecordAPI</strong>, stage <code>prod</code>):
            </Typography>
            <Typography component="div" variant="body2" sx={{ ml: 2 }}>
              • <code>POST /retrieve-store-flight-data</code> (Lambda: <strong>retrieve-flight-data</strong>) – pulls flight data (AeroDataBox via RapidAPI) and stores a record in RDS Postgres.<br />
              • <code>POST /parse-email-flights</code> (Lambda: <strong>proxy-email-parser-agent</strong>) – initiates async email parsing via AgentCore Runtime, returns jobId immediately.<br />
              • <code>GET /parse-email-flights/status/{`{jobId}`}</code> – polls email parsing job status with real-time progress updates.<br />
              • <code>GET /display-flight-record-table</code> (Lambda: <strong>display-flight-record-table</strong>) – queries the <code>flight_record</code> table and returns rows.<br />
              • <code>POST /talk-to-flight-record</code> (Lambda: <strong>proxy-flight-record-bedrock-agent</strong>) – initiates async AI query, returns jobId immediately.<br />
              • <code>GET /talk-to-flight-record/status/{`{jobId}`}</code> – polls async job status with real-time agent progress updates.
            </Typography>
            <Typography variant="body2" paragraph sx={{ mt: 2 }}>
              Data persistence: Lambdas run Python 3.9/3.12 inside a VPC and connect to an RDS Postgres instance using environment variables for credentials. The <code>psycopg2</code> layer is attached for database access.
            </Typography>
            <Typography variant="body2" paragraph>
              <strong>Email Parser Architecture:</strong> The email parser uses AWS Bedrock AgentCore Runtime with an <strong>ARM64 container</strong> running Claude 3.5 Haiku. When you paste a confirmation email, the proxy Lambda creates a job in DynamoDB (<code>email-parse-jobs</code>) and invokes the AgentCore Runtime asynchronously. The Runtime extracts flight details from the email text, validates flights against AeroDataBox API (enriching with airline name, duration, mileage), and stores records via a VPC Lambda proxy (<code>store-flight-record</code>) to maintain RDS security (private subnet only). The parser gracefully degrades for historical flights outside API retention, storing email-extracted data without enrichment.
            </Typography>
            <Typography variant="body2" paragraph>
              <strong>Multi-Agent AI Architecture:</strong> The chat widget uses async polling pattern to handle complex queries that exceed API Gateway's 29-second timeout. When you submit a question, the proxy Lambda creates a job in DynamoDB (<code>flight-chat-jobs</code>) with status PENDING, then invokes itself asynchronously for background processing. The frontend polls every 4 seconds (max 5 minutes) to check job status.
            </Typography>
            <Typography variant="body2" paragraph>
              The background Lambda invokes the <strong>Supervisor Agent</strong>, which orchestrates collaboration between specialized agents: <strong>Flight-Record-Agent</strong> for your flight data and <strong>Airline-Status-Agent</strong> for elite status benefits. As each agent is invoked, the Lambda writes the agent name to DynamoDB incrementally, enabling real-time badge display in the UI showing which agents are actively analyzing your request. All agents use Claude 3.5 Haiku via Bedrock.
            </Typography>
            <Typography variant="body2" paragraph>
              Security boundary layers now include: (1) AWS WAF WebACL for coarse filtering (IP set + Referer prefix), (2) Cognito User Pool authorizer enforcing valid user tokens on protected methods (including chat), and (3) API Gateway usage plan + API key for metering of REST paths. Unauthenticated calls receive 401; authenticated without key on metered REST paths receive 403.
            </Typography>
            <Typography variant="body2" paragraph>
              Per-user data isolation is achieved by storing <code>user_sub</code> and <code>user_email</code> with each record and filtering queries server-side. The GET endpoint returns only your records (flag <code>filtered=true</code>) when authenticated; the chat system automatically scopes all database queries to your Cognito <code>sub</code> claim, ensuring complete data isolation across users.
            </Typography>
            <Typography variant="body2" paragraph>
              This card view standardizes the UX versus the original HTML while keeping architecture changes minimal: no additional backend layer, direct invocation of existing Lambdas, and reuse of the same API Gateway stage. The async polling pattern ensures complex multi-agent queries complete successfully without timeout errors.
            </Typography>
            <Typography variant="body2" gutterBottom sx={{ fontWeight: 600 }}>Architecture Diagram</Typography>
            <Box sx={{ mt: 2, mb: 2, maxWidth: '100%', overflow: 'auto' }}>
              <img 
                src="/app/architecture-diagram.png" 
                alt="AWS Architecture Diagram showing CloudFront, API Gateway, Lambda functions, RDS, NAT Gateway, ECR, and Bedrock agents"
                style={{ width: '100%', height: 'auto', border: '1px solid #e0e0e0', borderRadius: '4px' }}
              />
              <Typography variant="caption" display="block" sx={{ mt: 1, color: 'text.secondary' }}>
                Complete AWS architecture including NAT Gateway for external API calls and ECR for container images
              </Typography>
            </Box>
            <Typography variant="body2" gutterBottom sx={{ fontWeight: 600, mt: 2 }}>Architecture Diagram (ASCII - Simplified)</Typography>
            <Typography component="pre" variant="caption" sx={{ p: 1, bgcolor: 'grey.100', overflow: 'auto', maxHeight: 320 }}>
{`           +--------------------------------------+                 
     |         CloudFront (SPA)             |
     |  Default root: app/index.html        |
     +----------------+---------------------+
          |
+----------------------+    |    +--------------------+    +-------------------+
| Legacy HTML (S3)     |    |    | React SPA (S3/app) |    | Local Dev (Proxy) |
+----------+-----------+    |    +---------+----------+    +----------+--------+
     | Referer         |            | Referer                 | Inject Referer
     v                 |            v                         v
  +------------------------ WAF WebACL ------------------------+
  |  Allow: IP Set, Referer starts-with S3 URL | Block: 401    |
  +-----------------------------+------------------------------+
              v
         +-----------------------+
         | API Gateway prod      |
         +-----------+-----------+
               |
     +---------+----------+----------+----------+----------+----------+
     |         |          |          |          |          |          |
 POST /ret  GET /disp POST /parse POST /talk GET /parse GET /talk
  -store     -flight   -email      -to-flight /status    /status
  -flight    -table    -flights    -record    /{jobId}   /{jobId}
     |         |          |          |          |          |
   +-v---+ +--v---+  +---v---------+ +--------v--------+ | |
   |Retr.| |Disp.|  |proxy-email  | |proxy-bedrock    | | |
   |py3.9| |py3.9|  |-parser-agent| |-agent (py3.12)  | | |
   +--+--+ +--+--+  +------+------+ +--------+--------+ | |
      |       |            |                 |          | |
      v       v            v                 v          v v
   +------+ +------+ +------------+   +-----------+ +-------+ +-------+
   | RDS  | | RDS  | | DynamoDB   |   | DynamoDB  | | Dynamo| | Dynamo|
   |flight| |query | |email-parse-|   |flight-chat| | (read)| | (read)|
   +------+ +------+ |jobs (job)  |   |-jobs (job)| +-------+ +-------+
                     +-----+------+   +-----+-----+
                           |                |
          +----------------+                +------------------+
          | Async invoke                    | Async invoke self
          v                                 v
    +---------------------+        +-----------------------+
    | AgentCore Runtime   |        | Background: Bedrock   |
    | parse_email_agent_v2|        | Supervisor Agent      |
    | ARM64 container     |        | Multi-agent collab    |
    +----------+----------+        +-----------+-----------+
               |                               |
        +------+------+                 +------+------+
        |             |                 |             |
        v             v                 v             v
    +-------+   +--------+       +-----------+ +----------+
    |Bedrock|   |Aerodatab|      |Flight-Rec.| |Airline-  |
    |Claude |   |ox API   |      |Agent      | |Status-Agt|
    +-------+   +----+---+       +-----+-----+ +-----+----+
                     |                 |             |
                     v                 v             v
              [Enrich flight]    [DB queries]  [Status lookup]
                     |                 |             |
                     v                 v             v
              +-------------+    +-------------------------+
              |Lambda: store|    | UPDATE DynamoDB:        |
              |-flight-rec. |    | status: COMPLETED       |
              |(VPC, pg8000)|    | answer + agents_invoked |
              +------+------+    +-------------------------+
                     |
                     v
              +------------+
              | RDS Private|
              | (VPC only) |
              +------------+`}
            </Typography>
          </AccordionDetails>
        </Accordion>
        <Paper elevation={3} sx={{ p: 3, mb: 4 }}>
          <Typography variant="h6" gutterBottom>Submit Flight</Typography>
          <FlightForm
            onApiKeyChange={setApiKeyLocal}
            fetchFlightData={fetchFlightData}
            loading={loading}
            error={error}
          />
          {authError && (
            <Chip label={authError} color="error" variant="outlined" sx={{ mt: 2 }} />
          )}
          {flightResponse && (
            <Alert severity="success" icon={<CheckCircleIcon />} sx={{ mt: 2 }}>
              Flight stored
              {flightResponse.user_sub && (
                <Typography variant="caption" display="block">
                  user_sub: {flightResponse.user_sub}
                </Typography>
              )}
            </Alert>
          )}
          {error && !loading && (
            <Chip
              label={error}
              color="error"
              variant="outlined"
              sx={{ mt: 2 }}
            />
          )}
        </Paper>
        <Paper elevation={3} sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>Flight Records</Typography>
          <Button
            variant="outlined"
            onClick={handleLoadRecords}
            disabled={loading}
            sx={{ mb: 2 }}
          >
            {loading ? 'Loading...' : 'Load Records'}
          </Button>
          {filtered && (
            <Typography variant="caption" sx={{ mb: 1, display: 'block' }}>
              Filtered to authenticated user (row_count={recordsMeta?.row_count ?? 'n/a'} mode={recordsMeta?.query_mode || 'n/a'})
            </Typography>
          )}
          {!filtered && recordsMeta && (
            <Typography variant="caption" sx={{ mb: 1, display: 'block' }}>
              Unfiltered query (row_count={recordsMeta?.row_count ?? 'n/a'} mode={recordsMeta?.query_mode || 'n/a'})
            </Typography>
          )}
          {/* Debug hint if filtering active but zero records returned */}
          {filtered && records.length === 0 && isAuthenticated && (
            <Alert severity="info" sx={{ mb: 2 }}>
              No records matched your user_sub ({claims?.sub}). If this looks wrong, we may need to backfill or update the attribution value in the database.
            </Alert>
          )}
          {/* Client-side fallback filtering: if backend returned unfiltered rows but user is authenticated,
              hide rows belonging to a different user_sub to avoid cross-account leakage while authorizer
              claim propagation is investigated. */}
          {(() => {
            const backendFiltered = filtered || (recordsMeta?.query_mode === 'filtered');
            let displayRecords = records;
            let clientFiltered = false;
            if (!backendFiltered && isAuthenticated && claims?.sub && records.length) {
              const allSameSub = records.every(r => r.user_sub === records[0].user_sub);
              const mismatched = allSameSub && records[0].user_sub && records[0].user_sub !== claims.sub;
              if (mismatched) {
                displayRecords = records.filter(r => r.user_sub === claims.sub);
                clientFiltered = true;
              }
            }
            return (
              <>
                {clientFiltered && displayRecords.length === 0 && (
                  <Alert severity="warning" sx={{ mb: 2 }}>
                    Backend returned {records.length} rows for a different user_sub ({records[0].user_sub}). Temporarily hidden client-side. Your sub is {claims.sub}. This indicates authorizer claims not reaching Lambda.
                  </Alert>
                )}
                <FlightTable
                  apiKey={apiKeyLocal}
                  records={displayRecords}
                  loading={loading}
                  error={error}
                />
              </>
            );
          })()}
          {/* Debug panel: raw response */}
          {rawRecordsResponse && (
            <Accordion sx={{ mt: 3 }} defaultExpanded={false}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}><Typography variant="caption">Raw Records Response Debug</Typography></AccordionSummary>
              <AccordionDetails>
                <Typography component="pre" variant="caption" sx={{ maxHeight: 300, overflow: 'auto', bgcolor: 'grey.100', p:1 }}>
                  {JSON.stringify(rawRecordsResponse, null, 2)}
                </Typography>
              </AccordionDetails>
            </Accordion>
          )}
        </Paper>
      </Container>
      <ChatWidget
        isAuthenticated={isAuthenticated}
        idToken={idToken}
        userSub={claims?.sub}
        defaultQuestion="Give me a brief stats overview and monthly mileage for 2025."
        onRequireLogin={login}
      />
    </Layout>
  );
};

export default App;