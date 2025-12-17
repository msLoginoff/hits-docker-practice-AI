#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-https://host.docker.internal:7146}"
OUT_DIR="$(cd "$(dirname "$0")" && pwd)/out"
TS="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$OUT_DIR"

docker run --rm -i \
  -e BASE_URL="$BASE_URL" \
  -v "$(cd "$(dirname "$0")" && pwd):/scripts" \
  grafana/k6 run \
  --summary-export="/scripts/out/auth_$TS.json" \
  /scripts/k6_auth_flow.js

echo "Saved: $OUT_DIR/auth_$TS.json"