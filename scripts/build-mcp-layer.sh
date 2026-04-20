#!/usr/bin/env bash
set -euo pipefail

# Build a Lambda layer zip for talk-to-flight-record-mcp-backend dependencies.
# Usage:
#   ./scripts/build-mcp-layer.sh [python_version]
# Examples:
#   ./scripts/build-mcp-layer.sh 3.11
#   (If omitted defaults to 3.11)
#
# Output: layer.zip in ./layer_build
# Contents: python/lib/python<version>/site-packages/*
#
# NOTE: On macOS, compiling psycopg2 can produce incompatible binaries. We pin psycopg2-binary
# in requirements.txt so a pure wheel is used. If you switch to psycopg2 (source build), use Docker.

PY_VER="${1:-3.11}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAMBDA_DIR="$ROOT_DIR/lambdas/talk-to-flight-record-mcp-backend"
REQ_FILE="$LAMBDA_DIR/requirements.txt"
BUILD_DIR="$ROOT_DIR/layer_build"
SITE_PACKAGES_DIR="$BUILD_DIR/python/lib/python${PY_VER}/site-packages"

rm -rf "$BUILD_DIR" && mkdir -p "$SITE_PACKAGES_DIR"

echo "[INFO] Using Python version $PY_VER"

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "[INFO] Docker daemon running. Building inside Amazon Linux base image for compatibility."
    if ! docker run --rm -v "$LAMBDA_DIR":/src -v "$SITE_PACKAGES_DIR":/opt/site-packages -w /src public.ecr.aws/lambda/python:${PY_VER} \
      bash -c "pip install -r requirements.txt -t /opt/site-packages && find /opt/site-packages -name '*.dist-info' -prune -exec rm -rf {} +"; then
        echo "[ERROR] Docker build failed. Falling back to local pip (wheels may be incompatible with Lambda)."
        pip install -r "$REQ_FILE" -t "$SITE_PACKAGES_DIR"
    fi
  else
    echo "[WARN] Docker CLI present but daemon not running. Falling back to local pip install (wheels may be incompatible with Lambda)."
    pip install -r "$REQ_FILE" -t "$SITE_PACKAGES_DIR"
  fi
else
  echo "[WARN] Docker not installed. Local pip fallback (wheels may be incompatible)."
  pip install -r "$REQ_FILE" -t "$SITE_PACKAGES_DIR"
fi
# Strip dist-info to save space (optional)
find "$SITE_PACKAGES_DIR" -name '*.dist-info' -prune -exec rm -rf {} +

pushd "$BUILD_DIR" >/dev/null
zip -r layer.zip python > /dev/null
popd >/dev/null

SIZE=$(du -h "$BUILD_DIR/layer.zip" | cut -f1)
echo "[INFO] Layer zip built: $BUILD_DIR/layer.zip ($SIZE)"

echo "[NEXT] Publish layer (AWS CLI example):"
cat <<EOF
aws lambda publish-layer-version \
  --layer-name flight-record-mcp-deps \
  --compatible-runtimes python${PY_VER} \
  --zip-file fileb://$BUILD_DIR/layer.zip \
  --description "Dependencies for talk-to-flight-record-mcp-backend (psycopg2-binary, boto3, jsonschema)"

# After publishing, attach layer to the function:
aws lambda update-function-configuration \
  --function-name talk-to-flight-record-mcp-backend \
  --layers <NEW_LAYER_ARN>
EOF
