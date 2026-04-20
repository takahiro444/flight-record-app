#!/usr/bin/env bash
set -euo pipefail

# Deploy React SPA build to S3 without disturbing legacy root index.html.
# Strategy (homepage=/app):
# 1. Build artifacts (static assets) copied to /app/static so paths like /app/static/js/*.js resolve.
# 2. (Optional) Also sync to /static for backward compatibility; disabled by default.
# 3. SPA index.html uploaded under /app/index.html so legacy page remains default root index.
# 4. Cache-Control headers: immutable for hashed static assets, no-cache for HTML & manifest.
# Usage: ./scripts/deploy-app.sh <bucket-name> [prefix]
# Example: ./scripts/deploy-app.sh your-s3-bucket-name app

BUCKET_NAME=${1:-}
APP_PREFIX=${2:-app}

if [[ -z "${BUCKET_NAME}" ]]; then
  echo "Bucket name required. Usage: $0 <bucket-name> [prefix]" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLIENT_DIR="$ROOT_DIR/flight-record-app/client"
BUILD_DIR="$CLIENT_DIR/build"

if [[ ! -d "$BUILD_DIR" ]]; then
  echo "Build directory not found. Run npm build first." >&2
  exit 1
fi

echo "Uploading static assets to s3://$BUCKET_NAME/$APP_PREFIX/static/"
aws s3 sync "$BUILD_DIR/static" "s3://$BUCKET_NAME/$APP_PREFIX/static" \
  --delete \
  --cache-control "public,max-age=31536000,immutable"

# Upload asset-manifest and any other top-level build metadata under app prefix
if [[ -f "$BUILD_DIR/asset-manifest.json" ]]; then
  echo "Uploading asset-manifest.json"
  aws s3 cp "$BUILD_DIR/asset-manifest.json" "s3://$BUCKET_NAME/$APP_PREFIX/asset-manifest.json" \
    --cache-control "no-cache"
fi

echo "Uploading SPA index.html to s3://$BUCKET_NAME/$APP_PREFIX/index.html"
aws s3 cp "$BUILD_DIR/index.html" "s3://$BUCKET_NAME/$APP_PREFIX/index.html" \
  --cache-control "no-cache"

# Duplicate index content at the folder key (e.g., 'app/') so that requests to /app/ (with query params like ?code=...) serve the SPA directly
# rather than performing a redirect that would drop OAuth query parameters.
echo "Uploading duplicate folder index to s3://$BUCKET_NAME/$APP_PREFIX/ (preserves query params)"
aws s3api put-object \
  --bucket "$BUCKET_NAME" \
  --key "$APP_PREFIX/" \
  --content-type "text/html" \
  --cache-control "no-cache" \
  --body "$BUILD_DIR/index.html" >/dev/null

echo "Deployment complete. Access SPA at: https://$BUCKET_NAME.s3-website-us-west-2.amazonaws.com/$APP_PREFIX/index.html (website endpoint)"
echo "Or object URL: https://$BUCKET_NAME.s3.amazonaws.com/$APP_PREFIX/index.html"

echo "Optional: Update Cognito callback/logout URLs to point to /$APP_PREFIX/index.html. For pretty /$APP_PREFIX/ URL use CloudFront or a redirect object for key '$APP_PREFIX/' mapping to index.html."
