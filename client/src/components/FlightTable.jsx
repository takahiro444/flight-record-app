import React, { useMemo, useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Skeleton,
  Paper,
  Chip,
  Stack,
  Box,
  IconButton,
  Tooltip,
  FormControlLabel,
  Switch,
} from '@mui/material';
import FlightTakeoffIcon from '@mui/icons-material/FlightTakeoff';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';

// ---------------------------------------------------------------------------
// Pure formatting helpers. All transformations happen in the browser against
// whatever shape the display-flight-record-table Lambda returns — no schema
// change in Postgres.
// ---------------------------------------------------------------------------

const TECHNICAL_COLUMNS = ['id', 'user_sub', 'user_email'];

const formatDate = (value) => {
  if (!value) return { primary: '—', secondary: '' };
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return { primary: String(value), secondary: '' };
  const primary = d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  const secondary = d.toLocaleDateString('en-US', { weekday: 'short' });
  return { primary, secondary };
};

const parseTimeToHHMM = (value) => {
  if (!value) return null;
  if (typeof value === 'string') {
    // Handles "HH:MM", "HH:MM:SS", "2026-01-06T09:30:00Z", or free-form text.
    const match = value.match(/(\d{1,2}):(\d{2})/);
    if (match) return `${match[1].padStart(2, '0')}:${match[2]}`;
    const d = new Date(value);
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    }
  }
  return String(value);
};

const formatDurationMinutes = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  // Try ISO-8601 duration like "PT2H45M".
  if (typeof value === 'string') {
    const iso = value.match(/^PT(?:(\d+)H)?(?:(\d+)M)?/);
    if (iso && (iso[1] || iso[2])) {
      const h = parseInt(iso[1] || '0', 10);
      const m = parseInt(iso[2] || '0', 10);
      return h && m ? `${h}h ${m}m` : h ? `${h}h` : `${m}m`;
    }
    // "Xh Ym" already formatted — pass through.
    if (/\d+h/i.test(value)) return value;
  }
  // Treat as minutes.
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) return String(value);
  const h = Math.floor(num / 60);
  const m = Math.round(num % 60);
  if (!h) return `${m}m`;
  if (!m) return `${h}h`;
  return `${h}h ${m}m`;
};

const formatMileage = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  return `${num.toLocaleString('en-US')} mi`;
};

const truncate = (value, head = 8) => {
  if (!value) return '—';
  const str = String(value);
  return str.length > head + 4 ? `${str.slice(0, head)}…${str.slice(-4)}` : str;
};

// ---------------------------------------------------------------------------
// Cell renderers.
// ---------------------------------------------------------------------------

const RouteCell = ({ row }) => {
  const fromCode = row.departure_iata || row.departure_airport || '—';
  const toCode = row.arrival_iata || row.arrival_airport || '—';
  const fromName = row.departure_airport && row.departure_airport !== row.departure_iata ? row.departure_airport : null;
  const toName = row.arrival_airport && row.arrival_airport !== row.arrival_iata ? row.arrival_airport : null;
  return (
    <Stack direction="row" spacing={1.25} alignItems="center">
      <Box
        sx={{
          width: 32,
          height: 32,
          borderRadius: 1.5,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'primary.light',
          color: 'primary.dark',
          flexShrink: 0,
        }}
      >
        <FlightTakeoffIcon fontSize="small" />
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Stack direction="row" spacing={0.75} alignItems="center">
          <Typography variant="body2" sx={{ fontFamily: 'ui-monospace, monospace', fontWeight: 600 }}>{fromCode}</Typography>
          <ArrowForwardIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          <Typography variant="body2" sx={{ fontFamily: 'ui-monospace, monospace', fontWeight: 600 }}>{toCode}</Typography>
        </Stack>
        {(fromName || toName) && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.3 }} noWrap>
            {fromName || fromCode} → {toName || toCode}
          </Typography>
        )}
      </Box>
    </Stack>
  );
};

const FlightCell = ({ row }) => (
  <Stack spacing={0.25}>
    <Chip
      size="small"
      label={row.flight_iata || '—'}
      sx={{
        fontFamily: 'ui-monospace, monospace',
        fontWeight: 600,
        width: 'fit-content',
        bgcolor: 'primary.light',
        color: 'primary.dark',
        borderRadius: 1.5,
      }}
    />
    {row.airline_name && (
      <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.3 }} noWrap>
        {row.airline_name}
      </Typography>
    )}
  </Stack>
);

const DateCell = ({ value }) => {
  const { primary, secondary } = formatDate(value);
  return (
    <Stack spacing={0.25} sx={{ whiteSpace: 'nowrap' }}>
      <Typography variant="body2" sx={{ fontWeight: 500 }}>{primary}</Typography>
      {secondary && <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.3 }}>{secondary}</Typography>}
    </Stack>
  );
};

const TimeCell = ({ row }) => {
  const dep = parseTimeToHHMM(row.departure_time);
  const arr = parseTimeToHHMM(row.arrival_time);
  if (!dep && !arr) return <Typography variant="body2" color="text.secondary">—</Typography>;
  return (
    <Stack direction="row" spacing={0.75} alignItems="center">
      <Typography variant="body2" sx={{ fontFamily: 'ui-monospace, monospace', fontWeight: 500 }}>{dep || '—'}</Typography>
      <ArrowForwardIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
      <Typography variant="body2" sx={{ fontFamily: 'ui-monospace, monospace', fontWeight: 500 }}>{arr || '—'}</Typography>
    </Stack>
  );
};

const SubCell = ({ value }) => {
  const onCopy = async (e) => {
    e.stopPropagation();
    try { await navigator.clipboard.writeText(String(value)); } catch (_) { /* noop */ }
  };
  if (!value) return <Typography variant="caption" color="text.secondary">—</Typography>;
  return (
    <Stack direction="row" spacing={0.5} alignItems="center">
      <Tooltip title={value} placement="top">
        <Typography variant="caption" sx={{ fontFamily: 'ui-monospace, monospace', color: 'text.secondary' }}>
          {truncate(value, 8)}
        </Typography>
      </Tooltip>
      <IconButton size="small" onClick={onCopy} sx={{ color: 'text.secondary' }} aria-label="copy">
        <ContentCopyIcon sx={{ fontSize: 14 }} />
      </IconButton>
    </Stack>
  );
};

// ---------------------------------------------------------------------------
// Empty / loading / error states.
// ---------------------------------------------------------------------------

const EmptyState = () => (
  <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      py: 6,
      px: 3,
      textAlign: 'center',
      gap: 1,
    }}
  >
    <Box
      sx={{
        width: 56,
        height: 56,
        borderRadius: '50%',
        bgcolor: 'primary.light',
        color: 'primary.dark',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        mb: 1,
      }}
    >
      <FlightTakeoffIcon />
    </Box>
    <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>No flights yet</Typography>
    <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 360 }}>
      Submit a flight or paste a confirmation email above, then press <strong>Load Records</strong> to see your trips here.
    </Typography>
  </Box>
);

const LoadingRows = () => (
  <TableContainer>
    <Table size="small">
      <TableHead>
        <TableRow>
          {['Route', 'Flight', 'Date', 'Time', 'Duration', 'Mileage'].map((h) => (
            <TableCell key={h}><Skeleton /></TableCell>
          ))}
        </TableRow>
      </TableHead>
      <TableBody>
        {Array.from({ length: 5 }).map((_, r) => (
          <TableRow key={r}>
            {Array.from({ length: 6 }).map((_, c) => (
              <TableCell key={c}><Skeleton /></TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </TableContainer>
);

// ---------------------------------------------------------------------------
// Main table.
// ---------------------------------------------------------------------------

const FlightTable = ({ records, loading, error }) => {
  const [showTechnical, setShowTechnical] = useState(false);

  // Any keys returned by the backend that we haven't mapped into a designed
  // column — useful for forward-compatibility if the backend adds fields.
  const extraKeys = useMemo(() => {
    if (!records || !records.length) return [];
    const known = new Set([
      'id', 'date', 'flight_iata', 'airline_name', 'airline_iata',
      'departure_airport', 'departure_iata', 'arrival_airport', 'arrival_iata',
      'departure_time', 'arrival_time', 'flight_duration', 'flight_mileage',
      'user_sub', 'user_email',
    ]);
    return Object.keys(records[0]).filter((k) => !known.has(k));
  }, [records]);

  if (loading) return <LoadingRows />;
  if (error) return <Typography color="error">Error: {error}</Typography>;
  if (!records || !records.length) return <EmptyState />;

  return (
    <Box>
      <Stack direction="row" justifyContent="flex-end" sx={{ mb: 1 }}>
        <FormControlLabel
          control={(
            <Switch
              size="small"
              checked={showTechnical}
              onChange={(e) => setShowTechnical(e.target.checked)}
            />
          )}
          label={<Typography variant="caption" color="text.secondary">Show technical columns</Typography>}
        />
      </Stack>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Route</TableCell>
              <TableCell>Flight</TableCell>
              <TableCell sx={{ whiteSpace: 'nowrap' }}>Date</TableCell>
              <TableCell sx={{ whiteSpace: 'nowrap' }}>Time</TableCell>
              <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>Duration</TableCell>
              <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>Mileage</TableCell>
              {showTechnical && TECHNICAL_COLUMNS.map((k) => (
                <TableCell key={k}>{k}</TableCell>
              ))}
              {showTechnical && extraKeys.map((k) => (
                <TableCell key={k}>{k}</TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {records.map((row, idx) => (
              <TableRow key={row.id ?? idx}>
                <TableCell><RouteCell row={row} /></TableCell>
                <TableCell><FlightCell row={row} /></TableCell>
                <TableCell><DateCell value={row.date} /></TableCell>
                <TableCell><TimeCell row={row} /></TableCell>
                <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                  <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                    {formatDurationMinutes(row.flight_duration)}
                  </Typography>
                </TableCell>
                <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                  <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>
                    {formatMileage(row.flight_mileage)}
                  </Typography>
                </TableCell>
                {showTechnical && (
                  <>
                    <TableCell>
                      <Typography variant="caption" sx={{ fontFamily: 'ui-monospace, monospace', color: 'text.secondary' }}>
                        {row.id ?? '—'}
                      </Typography>
                    </TableCell>
                    <TableCell><SubCell value={row.user_sub} /></TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">{row.user_email || '—'}</Typography>
                    </TableCell>
                    {extraKeys.map((k) => (
                      <TableCell key={k}>
                        <Typography variant="caption" color="text.secondary">
                          {row[k] === null || row[k] === undefined ? '—' : String(row[k])}
                        </Typography>
                      </TableCell>
                    ))}
                  </>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default FlightTable;
