import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';

// Cognito Auth Context with PKCE Authorization Code flow.
// Environment variables required:
//   REACT_APP_COGNITO_DOMAIN
//   REACT_APP_COGNITO_CLIENT_ID
//   REACT_APP_COGNITO_REDIRECT_URI
//   REACT_APP_COGNITO_LOGOUT_URI (optional)
// Scopes currently limited to openid,email; add 'profile' later if enabled.

const AuthContext = createContext(null);

function base64UrlEncode(buffer) {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '');
}

function generateCodeVerifier() {
  const array = new Uint8Array(64);
  // Use window.crypto explicitly to avoid ESLint no-restricted-globals warning on 'self'.
  (window.crypto).getRandomValues(array);
  return Array.from(array).map(b => ('0' + b.toString(16)).slice(-2)).join('');
}

// Minimal SHA-256 implementation fallback (returns Uint8Array) for insecure contexts (HTTP S3 website endpoint
// where window.crypto.subtle is unavailable). Based on FIPS 180-4; optimized for brevity not speed.
function sha256Fallback(message) {
  function rotr(n, x) { return (x >>> n) | (x << (32 - n)); }
  function toBytes(str) { return new TextEncoder().encode(str); }
  const bytes = typeof message === 'string' ? toBytes(message) : message;
  const l = bytes.length * 8;
  const withOne = new Uint8Array(((bytes.length + 9 + 63) >> 6) << 6);
  withOne.set(bytes);
  withOne[bytes.length] = 0x80;
  const view = new DataView(withOne.buffer);
  view.setUint32(withOne.length - 4, l >>> 0, false); // low bits
  view.setUint32(withOne.length - 8, Math.floor(l / 0x100000000), false); // high bits
  const K = [
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
  ];
  let H0=0x6a09e667,H1=0xbb67ae85,H2=0x3c6ef372,H3=0xa54ff53a,H4=0x510e527f,H5=0x9b05688c,H6=0x1f83d9ab,H7=0x5be0cd19;
  const w = new Uint32Array(64);
  for (let i = 0; i < withOne.length; i += 64) {
    for (let t = 0; t < 16; ++t) w[t] = view.getUint32(i + t*4, false);
    for (let t = 16; t < 64; ++t) {
      const s0 = rotr(7,w[t-15]) ^ rotr(18,w[t-15]) ^ (w[t-15]>>>3);
      const s1 = rotr(17,w[t-2]) ^ rotr(19,w[t-2]) ^ (w[t-2]>>>10);
      w[t] = (w[t-16] + s0 + w[t-7] + s1) >>> 0;
    }
    let a=H0,b=H1,c=H2,d=H3,e=H4,f=H5,g=H6,h=H7;
    for (let t = 0; t < 64; ++t) {
      const S1 = rotr(6,e) ^ rotr(11,e) ^ rotr(25,e);
      const ch = (e & f) ^ (~e & g);
      const temp1 = (h + S1 + ch + K[t] + w[t]) >>> 0;
      const S0 = rotr(2,a) ^ rotr(13,a) ^ rotr(22,a);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + maj) >>> 0;
      h=g; g=f; f=e; e=(d + temp1) >>> 0; d=c; c=b; b=a; a=(temp1 + temp2) >>> 0;
    }
    H0=(H0+a)>>>0; H1=(H1+b)>>>0; H2=(H2+c)>>>0; H3=(H3+d)>>>0; H4=(H4+e)>>>0; H5=(H5+f)>>>0; H6=(H6+g)>>>0; H7=(H7+h)>>>0;
  }
  const out = new Uint8Array(32);
  const hv = [H0,H1,H2,H3,H4,H5,H6,H7];
  for (let i=0;i<hv.length;i++){ out[i*4]=(hv[i]>>>24)&255; out[i*4+1]=(hv[i]>>>16)&255; out[i*4+2]=(hv[i]>>>8)&255; out[i*4+3]=hv[i]&255; }
  return out;
}

async function generateCodeChallenge(verifier) {
  try {
    if (window.crypto && window.crypto.subtle) {
      const data = new TextEncoder().encode(verifier);
      const digest = await window.crypto.subtle.digest('SHA-256', data);
      return base64UrlEncode(digest);
    }
    console.warn('[Auth] crypto.subtle unavailable; using JS SHA-256 fallback. Consider HTTPS object or CloudFront domain.');
    return base64UrlEncode(sha256Fallback(verifier));
  } catch (e) {
    console.error('[Auth] generateCodeChallenge failure', e);
    throw e;
  }
}

export function AuthProvider({ children }) {
  const domain = process.env.REACT_APP_COGNITO_DOMAIN;
  const clientId = process.env.REACT_APP_COGNITO_CLIENT_ID;
  const redirectUri = process.env.REACT_APP_COGNITO_REDIRECT_URI;
  const logoutUri = process.env.REACT_APP_COGNITO_LOGOUT_URI || redirectUri;
  // Stable scopes array to avoid re-renders and silence exhaustive-deps lint warning.
  const scopes = useMemo(() => ['openid', 'email'], []);

  // Runtime configuration validation (non-fatal). Helps surface common misconfigurations that lead to 'Invalid request'.
  useEffect(() => {
    try {
      if (!domain || !clientId || !redirectUri) {
        console.warn('[Auth][Config] Missing required env vars (domain/clientId/redirectUri).');
      }
      // Warn if domain looks like it accidentally used user pool id pattern with underscore removed (heuristic only).
      const poolIdPattern = /us-[a-z0-9-]+_[A-Za-z0-9]+/; // actual pool id format
      if (poolIdPattern.test(clientId)) {
        console.warn('[Auth][Config] clientId matches user pool id pattern. Ensure this is the App Client ID, not the pool id.');
      }
      // Check if redirect host differs from current host (sessionStorage origin mismatch risk for PKCE).
      try {
        const ru = new URL(redirectUri);
        if (window.location.host !== ru.host) {
          console.debug('[Auth][Config] redirectUri host differs from current host; PKCE verifier will not persist across origins.', {
            currentHost: window.location.host,
            redirectHost: ru.host
          });
        }
      } catch (e) {
        console.warn('[Auth][Config] redirectUri is not a valid URL string:', redirectUri);
      }
      // Simple Hosted UI domain shape check.
      if (!/\.auth\.[a-z0-9-]+\.amazoncognito\.com$/.test(domain)) {
        console.warn('[Auth][Config] Cognito domain does not match expected pattern *.auth.<region>.amazoncognito.com:', domain);
      }
    } catch (e) {
      console.warn('[Auth][Config] Validation exception', e);
    }
  }, [domain, clientId, redirectUri]);

  const [idToken, setIdToken] = useState(() => localStorage.getItem('id_token'));
  const [accessToken, setAccessToken] = useState(() => localStorage.getItem('access_token'));
  const [refreshToken, setRefreshToken] = useState(() => localStorage.getItem('refresh_token'));
  const [expiresAt, setExpiresAt] = useState(() => {
    const stored = localStorage.getItem('expires_at');
    return stored ? parseInt(stored, 10) : null;
  });
  const [claims, setClaims] = useState(() => {
    const stored = localStorage.getItem('claims');
    return stored ? JSON.parse(stored) : null;
  });
  const [apiKey, setApiKey] = useState('');
  const [authError, setAuthError] = useState(null);
  const [exchanging, setExchanging] = useState(false);

  const isAuthenticated = !!idToken && expiresAt && Date.now() < expiresAt;

  // Persist tokens to localStorage whenever they change
  useEffect(() => {
    if (idToken) localStorage.setItem('id_token', idToken);
    else localStorage.removeItem('id_token');
  }, [idToken]);

  useEffect(() => {
    if (accessToken) localStorage.setItem('access_token', accessToken);
    else localStorage.removeItem('access_token');
  }, [accessToken]);

  useEffect(() => {
    if (refreshToken) localStorage.setItem('refresh_token', refreshToken);
    else localStorage.removeItem('refresh_token');
  }, [refreshToken]);

  useEffect(() => {
    if (expiresAt) localStorage.setItem('expires_at', expiresAt.toString());
    else localStorage.removeItem('expires_at');
  }, [expiresAt]);

  useEffect(() => {
    if (claims) localStorage.setItem('claims', JSON.stringify(claims));
    else localStorage.removeItem('claims');
  }, [claims]);

  const buildLoginUrl = useCallback(async () => {
    console.debug('[Auth] Build login URL env', { domain, clientId, redirectUri });
    const verifier = generateCodeVerifier();
    sessionStorage.setItem('pkce_verifier', verifier);
    const challenge = await generateCodeChallenge(verifier);
    const params = new URLSearchParams({
      client_id: clientId,
      response_type: 'code',
      scope: scopes.join(' '),
      redirect_uri: redirectUri,
      code_challenge_method: 'S256',
      code_challenge: challenge
    });
    return `${domain}/login?${params.toString()}`;
  }, [clientId, domain, redirectUri, scopes]);

  const login = useCallback(async () => {
    try {
      const url = await buildLoginUrl();
      console.debug('[Auth] Redirecting to Hosted UI', url);
      window.location.assign(url);
    } catch (e) {
      setAuthError('Failed to initiate login');
      console.error('[Auth] Login initiation failure', e);
    }
  }, [buildLoginUrl]);

  const logout = useCallback(() => {
    setIdToken(null); setAccessToken(null); setRefreshToken(null); setExpiresAt(null); setClaims(null); setApiKey('');
    localStorage.removeItem('id_token');
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('expires_at');
    localStorage.removeItem('claims');
    const params = new URLSearchParams({ client_id: clientId, logout_uri: logoutUri });
    window.location.assign(`${domain}/logout?${params.toString()}`);
  }, [clientId, logoutUri, domain]);

  useEffect(() => {
    const url = new URL(window.location.href);
    const code = url.searchParams.get('code');
    const error = url.searchParams.get('error');
    if (error) {
      setAuthError(error);
      return;
    }
    if (!code) return;
    // Diagnostics: log code param and current origin details for PKCE troubleshooting.
    console.debug('[Auth] Detected code param during redirect:', { code, origin: window.location.origin, redirectUri });
    const verifier = sessionStorage.getItem('pkce_verifier');
    if (!verifier) {
      // Common cause: user initiated login from a different origin than redirectUri (S3 REST vs website endpoint) so sessionStorage is empty.
      console.warn('[Auth] PKCE verifier missing. Likely origin mismatch or page reload. Code cannot be exchanged.');
      setAuthError('Login redirect lost PKCE verifier (likely origin mismatch). Please click Login again.');
      return;
    }
    const performExchange = async () => {
      setExchanging(true);
      try {
        const body = new URLSearchParams({
          grant_type: 'authorization_code',
          client_id: clientId,
          code,
          redirect_uri: redirectUri,
          code_verifier: verifier
        });
        console.debug('[Auth] Performing token exchange with PKCE', { hasVerifier: !!verifier, redirectUri });
        const resp = await fetch(`${domain}/oauth2/token`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: body.toString()
        });
        if (!resp.ok) throw new Error(`Token exchange failed (${resp.status})`);
        const json = await resp.json();
        const { id_token, access_token, refresh_token, expires_in } = json;
        setIdToken(id_token); setAccessToken(access_token); setRefreshToken(refresh_token || null);
        setExpiresAt(Date.now() + expires_in * 1000);
        if (id_token) {
          try {
            const payload = id_token.split('.')[1];
            const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
            setClaims(decoded);
          } catch (e) { console.warn('Failed to decode id_token claims', e); }
        }
        window.history.replaceState({}, document.title, url.pathname);
      } catch (e) {
        console.error('[Auth] Token exchange error', e);
        setAuthError(e.message);
      } finally {
        setExchanging(false);
      }
    };
    performExchange();
  }, [clientId, domain, redirectUri]);

  const value = { idToken, accessToken, refreshToken, expiresAt, claims, apiKey, setApiKey, isAuthenticated, authError, exchanging, login, logout };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() { return useContext(AuthContext); }
