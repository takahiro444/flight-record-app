import React, { useEffect, useMemo, useState } from 'react';
import { Container, CssBaseline, Box, Typography, IconButton, Tooltip, Divider } from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { useAuth } from '../auth/AuthContext';
import { fetchWhoAmI } from '../utils/api';

const Layout = ({ children }) => {
  const { idToken, claims } = useAuth();
  const [whoami, setWhoami] = useState(null);
  const [copyHint, setCopyHint] = useState('Copy');

  const localIdentity = useMemo(() => {
    if (!claims) return null;
    const email = claims.email || claims['custom:email'] || null;
    const sub = claims.sub || null;
    return { email, sub };
  }, [claims]);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (!idToken) return;
      try {
        const data = await fetchWhoAmI(idToken);
        if (!cancelled) setWhoami(data);
      } catch (e) {
        // Non-fatal; UI can show local decoded claims instead.
        console.warn('[Layout] whoami fetch failed', e);
      }
    };
    run();
    return () => { cancelled = true; };
  }, [idToken]);

  const identity = whoami || localIdentity;

  const onCopy = async () => {
    try {
      if (!identity?.sub) return;
      await navigator.clipboard.writeText(identity.sub);
      setCopyHint('Copied');
      setTimeout(() => setCopyHint('Copy'), 1200);
    } catch (e) {
      setCopyHint('Failed');
      setTimeout(() => setCopyHint('Copy'), 1200);
    }
  };

  return (
    <Container component="main" maxWidth="md">
      <CssBaseline />
      <Box sx={{ pt: 2, pb: 1 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Signed in as
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Typography variant="body2" sx={{ wordBreak: 'break-all', overflowWrap: 'anywhere', whiteSpace: 'normal' }}>
            {identity?.email || 'Unknown email'}
          </Typography>
          <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
          <Typography
            variant="body2"
            sx={{
              wordBreak: 'break-all',
              overflowWrap: 'anywhere',
              whiteSpace: 'normal',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
            }}
          >
            sub: {identity?.sub || '—'}
          </Typography>
          <Tooltip title={copyHint}>
            <span>
              <IconButton size="small" onClick={onCopy} disabled={!identity?.sub} aria-label="copy sub">
                <ContentCopyIcon fontSize="inherit" />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      </Box>
      {children}
    </Container>
  );
};

export default Layout;