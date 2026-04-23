import React, { useState } from 'react';
import { Container, CssBaseline, Typography, Button, AppBar, Toolbar, Chip, Paper, Accordion, AccordionSummary, AccordionDetails, Stack, Alert, Box, Grid, Card, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Divider, Dialog, IconButton, Tooltip, Fade } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FlightTakeoffIcon from '@mui/icons-material/FlightTakeoff';
import MarkEmailReadIcon from '@mui/icons-material/MarkEmailRead';
import TableRowsIcon from '@mui/icons-material/TableRows';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import SecurityIcon from '@mui/icons-material/Security';
import ShieldIcon from '@mui/icons-material/Shield';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import PersonIcon from '@mui/icons-material/Person';
import HubIcon from '@mui/icons-material/Hub';
import EmailIcon from '@mui/icons-material/Email';
import OpenInFullIcon from '@mui/icons-material/OpenInFull';
import CloseIcon from '@mui/icons-material/Close';
import FlightForm from './components/FlightForm';
import FlightTable from './components/FlightTable';
import Layout from './components/Layout';
import ChatWidget from './components/ChatWidget';
import useFlights from './hooks/useFlights';
import { useAuth } from './auth/AuthContext';
import planeLogo from './assets/airplane.svg';

// ---------------------------------------------------------------------------
// Pieces used inside the Application Overview accordion. Extracted here to
// keep the main render clean; they have no props tied to app state.
// ---------------------------------------------------------------------------

const OverviewSectionHeading = ({ children }) => (
  <Typography variant="overline" color="primary" sx={{ fontWeight: 600, letterSpacing: '0.12em' }}>
    {children}
  </Typography>
);

const CAPABILITY_CARDS = [
  {
    icon: FlightTakeoffIcon,
    title: 'Submit a flight',
    body: 'Enter an IATA code + date. We pull details from AeroDataBox and save a record to Postgres.',
  },
  {
    icon: MarkEmailReadIcon,
    title: 'Parse an email',
    body: 'Paste a flight confirmation. An AI agent extracts flights and stores them for you.',
  },
  {
    icon: TableRowsIcon,
    title: 'View your records',
    body: 'Browse stored flights, automatically scoped to your Cognito identity.',
  },
  {
    icon: SmartToyIcon,
    title: 'Chat with your data',
    body: 'Ask questions about your flights; a supervisor orchestrates specialized sub-agents.',
  },
];

const API_ENDPOINTS = [
  { method: 'POST', path: '/retrieve-store-flight-data', lambda: 'retrieve-flight-data' },
  { method: 'POST', path: '/parse-email-flights', lambda: 'proxy-email-parser-agent' },
  { method: 'GET', path: '/parse-email-flights/status/{jobId}', lambda: 'proxy-email-parser-agent' },
  { method: 'GET', path: '/display-flight-record-table', lambda: 'display-flight-record-table' },
  { method: 'POST', path: '/talk-to-flight-record', lambda: 'proxy-flight-record-bedrock-agent' },
  { method: 'GET', path: '/talk-to-flight-record/status/{jobId}', lambda: 'proxy-flight-record-bedrock-agent' },
];

const EMAIL_FLOW = {
  icon: EmailIcon,
  title: 'Email parser flow',
  tags: ['Async polling', 'ARM64 AgentCore', 'Claude 3.5 Haiku'],
  steps: [
    { title: 'Submit', body: 'Proxy Lambda creates a DynamoDB job and returns jobId immediately.' },
    { title: 'Extract', body: 'AgentCore Runtime (ARM64 container) pulls flights out of the email with Claude 3.5 Haiku.' },
    { title: 'Validate', body: 'AeroDataBox enriches each flight with airline, duration, mileage — gracefully degraded for old flights.' },
    { title: 'Store', body: 'VPC-scoped Lambda writes the records to private RDS Postgres.' },
  ],
};

const CHAT_FLOW = {
  icon: HubIcon,
  title: 'Multi-agent chat flow',
  tags: ['Async polling', 'Supervisor agent', 'Live badges'],
  steps: [
    { title: 'Ask', body: 'Proxy Lambda stores the job, self-invokes async, returns jobId.' },
    { title: 'Orchestrate', body: 'Supervisor agent chooses collaborators: Flight-Record-Agent and/or Airline-Status-Agent.' },
    { title: 'Stream', body: 'Each invoked agent is written to DynamoDB incrementally — the UI shows live badges.' },
    { title: 'Answer', body: 'Frontend polls every 4s (max 5 min) and renders the final response.' },
  ],
};

const SECURITY_LAYERS = [
  { icon: ShieldIcon, label: 'WAF', body: 'Coarse filter by IP set + Referer prefix. Default-block returns 401.' },
  { icon: SecurityIcon, label: 'Cognito JWT', body: 'All protected methods require a valid user token.' },
  { icon: VpnKeyIcon, label: 'API key', body: 'Metered REST paths require a usage-plan key.' },
  { icon: PersonIcon, label: 'Per-user scope', body: 'user_sub stored on every row; queries auto-filtered to the authenticated user.' },
];

const MethodChip = ({ method }) => {
  const color = method === 'POST' ? 'info' : method === 'GET' ? 'success' : 'default';
  return (
    <Chip
      size="small"
      label={method}
      color={color}
      sx={{ fontFamily: 'ui-monospace, monospace', fontWeight: 600, minWidth: 52, borderRadius: 1.5 }}
    />
  );
};

const CapabilityCard = ({ icon: Icon, title, body }) => (
  <Card sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column', gap: 1 }}>
    <Box
      sx={{
        width: 40,
        height: 40,
        borderRadius: 2,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'primary.light',
        color: 'primary.dark',
      }}
    >
      <Icon fontSize="small" />
    </Box>
    <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{title}</Typography>
    <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.5 }}>{body}</Typography>
  </Card>
);

const FlowCard = ({ icon: Icon, title, tags, steps }) => (
  <Card sx={{ p: 2.5, height: '100%' }}>
    <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 1.5 }}>
      <Box
        sx={{
          width: 36,
          height: 36,
          borderRadius: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'primary.light',
          color: 'primary.dark',
        }}
      >
        <Icon fontSize="small" />
      </Box>
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{title}</Typography>
    </Stack>
    <Stack direction="row" spacing={0.75} sx={{ mb: 2, flexWrap: 'wrap', gap: 0.75 }}>
      {tags.map((t) => (
        <Chip key={t} size="small" label={t} variant="outlined" />
      ))}
    </Stack>
    <Stack spacing={1.5}>
      {steps.map((step, idx) => (
        <Stack key={step.title} direction="row" spacing={1.5} alignItems="flex-start">
          <Box
            sx={{
              minWidth: 22,
              height: 22,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              bgcolor: 'primary.main',
              color: 'primary.contrastText',
              fontSize: '0.7rem',
              fontWeight: 600,
              mt: 0.25,
            }}
          >
            {idx + 1}
          </Box>
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{step.title}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.5 }}>
              {step.body}
            </Typography>
          </Box>
        </Stack>
      ))}
    </Stack>
  </Card>
);

const SecurityRow = ({ icon: Icon, label, body }) => (
  <Stack direction="row" spacing={1.5} alignItems="flex-start">
    <Box
      sx={{
        minWidth: 32,
        height: 32,
        borderRadius: 1.5,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'primary.light',
        color: 'primary.dark',
        mt: 0.25,
      }}
    >
      <Icon fontSize="small" />
    </Box>
    <Box>
      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{label}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.5 }}>{body}</Typography>
    </Box>
  </Stack>
);

const ARCHITECTURE_IMG = '/app/architecture-diagram.png';
const ARCHITECTURE_ALT = 'AWS architecture: CloudFront, API Gateway, Lambda, RDS, ECR, Bedrock agents';

const ApplicationOverview = () => {
  const [expanded, setExpanded] = useState(false);
  return (
  <Stack spacing={4} sx={{ pt: 1, pb: 1 }}>
    {/* Capabilities */}
    <Box>
      <OverviewSectionHeading>What you can do</OverviewSectionHeading>
      <Grid container spacing={2} sx={{ mt: 0.5 }}>
        {CAPABILITY_CARDS.map((c) => (
          <Grid item xs={12} sm={6} md={3} key={c.title}>
            <CapabilityCard {...c} />
          </Grid>
        ))}
      </Grid>
    </Box>

    {/* API endpoints */}
    <Box>
      <OverviewSectionHeading>API endpoints</OverviewSectionHeading>
      <TableContainer sx={{ mt: 1 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: 80 }}>Method</TableCell>
              <TableCell>Path</TableCell>
              <TableCell>Lambda</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {API_ENDPOINTS.map((e) => (
              <TableRow key={e.path}>
                <TableCell>
                  <MethodChip method={e.method} />
                </TableCell>
                <TableCell>
                  <Typography variant="body2" component="code" sx={{ fontFamily: 'ui-monospace, monospace' }}>
                    {e.path}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip size="small" variant="outlined" label={e.lambda} sx={{ fontFamily: 'ui-monospace, monospace' }} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
        Stage <code>prod</code> on API Gateway <strong>FlightRecordAPI</strong>. Lambdas run Python 3.9/3.12 inside a VPC and read DB credentials from environment.
      </Typography>
    </Box>

    {/* Flow cards */}
    <Box>
      <OverviewSectionHeading>How the AI flows work</OverviewSectionHeading>
      <Grid container spacing={2} sx={{ mt: 0.5 }}>
        <Grid item xs={12} md={6}>
          <FlowCard {...EMAIL_FLOW} />
        </Grid>
        <Grid item xs={12} md={6}>
          <FlowCard {...CHAT_FLOW} />
        </Grid>
      </Grid>
    </Box>

    {/* Security */}
    <Box>
      <OverviewSectionHeading>Security & isolation</OverviewSectionHeading>
      <Stack spacing={1.5} sx={{ mt: 1.5 }}>
        {SECURITY_LAYERS.map((s) => (
          <SecurityRow key={s.label} {...s} />
        ))}
      </Stack>
    </Box>

    <Divider />

    {/* Architecture diagram — click the expand button (or the image) for a
        full-screen view with the full pixel detail. */}
    <Box>
      <OverviewSectionHeading>Architecture</OverviewSectionHeading>
      <Box
        sx={{
          position: 'relative',
          mt: 1.5,
          borderRadius: 3,
          overflow: 'hidden',
          border: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.paper',
          cursor: 'zoom-in',
          transition: 'box-shadow 180ms ease',
          '&:hover': { boxShadow: '0 2px 4px 0 rgba(11, 87, 208, 0.12), 0 6px 12px 4px rgba(11, 87, 208, 0.08)' },
          '&:hover .expand-diagram-button': { opacity: 1 },
        }}
        onClick={() => setExpanded(true)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded(true); } }}
        aria-label="Expand architecture diagram"
      >
        <img
          src={ARCHITECTURE_IMG}
          alt={ARCHITECTURE_ALT}
          style={{ width: '100%', height: 'auto', display: 'block' }}
        />
        <Tooltip title="Expand">
          <IconButton
            className="expand-diagram-button"
            size="small"
            onClick={(e) => { e.stopPropagation(); setExpanded(true); }}
            sx={{
              position: 'absolute',
              top: 8,
              right: 8,
              opacity: 0,
              transition: 'opacity 180ms ease, background-color 160ms ease',
              bgcolor: 'rgba(255,255,255,0.9)',
              color: 'primary.dark',
              backdropFilter: 'blur(6px)',
              '&:hover': { bgcolor: '#ffffff' },
            }}
            aria-label="Expand architecture diagram"
          >
            <OpenInFullIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
        End-to-end AWS architecture: CloudFront → API Gateway → Lambda → RDS / Bedrock / AgentCore. Click to expand.
      </Typography>

      <Dialog
        open={expanded}
        onClose={() => setExpanded(false)}
        fullScreen
        TransitionComponent={Fade}
        PaperProps={{ sx: { bgcolor: 'rgba(15, 23, 42, 0.96)' } }}
      >
        <Box
          sx={{
            position: 'relative',
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            p: { xs: 2, sm: 4 },
          }}
          onClick={() => setExpanded(false)}
        >
          <Tooltip title="Close (Esc)">
            <IconButton
              onClick={() => setExpanded(false)}
              aria-label="Close architecture diagram"
              sx={{
                position: 'absolute',
                top: 16,
                right: 16,
                bgcolor: 'rgba(255,255,255,0.12)',
                color: '#ffffff',
                backdropFilter: 'blur(8px)',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.22)' },
              }}
            >
              <CloseIcon />
            </IconButton>
          </Tooltip>
          <Box
            component="img"
            src={ARCHITECTURE_IMG}
            alt={ARCHITECTURE_ALT}
            onClick={(e) => e.stopPropagation()}
            sx={{
              maxWidth: '100%',
              maxHeight: '100%',
              width: 'auto',
              height: 'auto',
              borderRadius: 2,
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
              cursor: 'default',
            }}
          />
        </Box>
      </Dialog>
    </Box>
  </Stack>
  );
};

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
            <Stack direction="row" spacing={1.5} alignItems="center">
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>Application Overview</Typography>
              <Chip size="small" label="Architecture & API reference" variant="outlined" />
            </Stack>
          </AccordionSummary>
          <AccordionDetails>
            <ApplicationOverview />
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