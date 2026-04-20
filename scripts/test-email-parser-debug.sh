#!/bin/bash
# Test email parser endpoint to debug authorization issues.
#
# Required environment variables:
#   API_BASE_URL     - API Gateway base URL, e.g. https://<api-id>.execute-api.<region>.amazonaws.com/prod
#   CLOUDFRONT_ORIGIN - CloudFront origin allowed by WAF, e.g. https://<dist-id>.cloudfront.net

if [[ -z "${API_BASE_URL:-}" || -z "${CLOUDFRONT_ORIGIN:-}" ]]; then
  echo "ERROR: Set API_BASE_URL and CLOUDFRONT_ORIGIN env vars before running." >&2
  exit 1
fi

ENDPOINT="${API_BASE_URL%/}/parse-email-and-store"
REFERER="${CLOUDFRONT_ORIGIN%/}/app"

echo "=== Testing Email Parser Endpoint ==="
echo ""
echo "1. Testing WITHOUT Referer (should be blocked by WAF):"
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid-token" \
  -d '{"email_text":"Test email with flight UA100 on Jan 15", "user_sub":"test-user"}' \
  -w "\nHTTP Status: %{http_code}\n\n"

echo ""
echo "2. Testing WITH CloudFront Referer (should pass WAF, fail auth):"
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid-token" \
  -H "Referer: $REFERER" \
  -d '{"email_text":"Test email with flight UA100 on Jan 15", "user_sub":"test-user"}' \
  -w "\nHTTP Status: %{http_code}\n\n"

echo ""
echo "3. Testing WITHOUT Authorization header (should fail):"
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Referer: $REFERER" \
  -d '{"email_text":"Test email with flight UA100 on Jan 15", "user_sub":"test-user"}' \
  -w "\nHTTP Status: %{http_code}\n\n"

echo ""
echo "Instructions:"
echo "- To test with your REAL Cognito ID token:"
echo "  1. Open browser DevTools (F12) on $REFERER"
echo "  2. Run: localStorage.getItem('id_token')"
echo "  3. Copy the token and run:"
echo ""
echo "  curl -X POST '$ENDPOINT' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H 'Authorization: Bearer YOUR_ACTUAL_TOKEN' \\"
echo "    -H 'Referer: $REFERER' \\"
echo "    -d '{\"email_text\":\"Flight UA100 on January 15, 2026\", \"user_sub\":\"YOUR_USER_SUB\"}'"
echo ""
