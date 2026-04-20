/*
  Dev proxy to allow local React app to call API Gateway endpoints that are
  protected by WAF referer/IP rules. We inject the S3 site Referer header.

  Usage:
  1. Set DEV_PROXY_API_TARGET and DEV_PROXY_WAF_REFERER in your .env.development.
  2. Set REACT_APP_API_BASE_URL=/apiGateway in your .env.development.
  3. Start the dev server; fetch calls to `${API_BASE_URL}/display-flight-record-table`
     will be proxied to the API Gateway target with a forged Referer header.
*/
const { createProxyMiddleware } = require('http-proxy-middleware');

const API_STAGE_BASE = process.env.DEV_PROXY_API_TARGET;
const WAF_REFERER = process.env.DEV_PROXY_WAF_REFERER;

if (!API_STAGE_BASE || !WAF_REFERER) {
  throw new Error(
    'Missing required env vars for dev proxy: DEV_PROXY_API_TARGET and DEV_PROXY_WAF_REFERER must be set in .env.development'
  );
}

module.exports = function(app) {
  app.use(
    '/apiGateway',
    createProxyMiddleware({
      target: API_STAGE_BASE,
      changeOrigin: true,
      pathRewrite: (path, req) => {
        // /apiGateway/display-flight-record-table -> /prod/display-flight-record-table
        return path.replace(/^\/apiGateway/, '');
      },
      onProxyReq: (proxyReq) => {
        // Inject referer header to satisfy WAF rule
        proxyReq.setHeader('referer', WAF_REFERER);
      },
      logLevel: 'warn'
    })
  );
};
