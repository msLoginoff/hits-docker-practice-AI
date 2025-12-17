#!/usr/bin/env bash
set -euo pipefail

SCENARIO="${SCENARIO:-01_anonymous_menu}"
MODE="${MODE:-baseline}"          # baseline | stress
ENGINE="${ENGINE:-docker}"        # docker | local
BASE_URL="${BASE_URL:-http://host.docker.internal:5146}"
OUT_ROOT="${OUT_DIR:-./out}"

# Optional overrides
VUS="${VUS:-}"
DURATION="${DURATION:-}"

SCRIPT_DIR="$(dirname "$0")/scripts/scenarios"
SCRIPT="$SCRIPT_DIR/${SCENARIO}.js"

if [[ ! -f "$SCRIPT" ]]; then
  echo "Scenario script not found: $SCRIPT"
  exit 1
fi

# Default load profiles (tweak as you wish)
if [[ -z "$VUS" || -z "$DURATION" ]]; then
  if [[ "$MODE" == "baseline" ]]; then
    case "$SCENARIO" in
      01_anonymous_menu) VUS="${VUS:-15}"; DURATION="${DURATION:-100s}" ;;
      02_auth_flow)      VUS="${VUS:-8}";  DURATION="${DURATION:-100s}" ;;
      03_checkout_flow)  VUS="${VUS:-8}";  DURATION="${DURATION:-100s}" ;;
      04_admin_browse)   VUS="${VUS:-8}";  DURATION="${DURATION:-100s}" ;;
      *)                 VUS="${VUS:-10}"; DURATION="${DURATION:-100s}" ;;
    esac
  else
    # stress
    case "$SCENARIO" in
      01_anonymous_menu) VUS="${VUS:-50}";  DURATION="${DURATION:-180s}" ;;
      02_auth_flow)      VUS="${VUS:-30}";  DURATION="${DURATION:-180s}" ;;
      03_checkout_flow)  VUS="${VUS:-25}";  DURATION="${DURATION:-180s}" ;;
      04_admin_browse)   VUS="${VUS:-25}";  DURATION="${DURATION:-180s}" ;;
      *)                 VUS="${VUS:-25}";  DURATION="${DURATION:-180s}" ;;
    esac
  fi
fi

mkdir -p "$OUT_ROOT"
TS="$(date +%Y%m%d_%H%M%S)"
SC_OUT="$OUT_ROOT/$SCENARIO"
mkdir -p "$SC_OUT"

SUMMARY_JSON="$SC_OUT/summary_${SCENARIO}_${TS}.json"
ENV_JSON="$SC_OUT/env_${SCENARIO}_${TS}.json"

# Helpful warning
if [[ "$ENGINE" == "docker" && "$BASE_URL" == *"localhost"* ]]; then
  echo "WARNING: ENGINE=docker + BASE_URL contains localhost."
  echo "In Docker, localhost points to the k6 container, not your Mac."
  echo "Use: http://host.docker.internal:5146 (or https://host.docker.internal:7146 with INSECURE=true)"
  echo ""
fi

# Collect env info (best-effort)
OS_NAME="$(uname -s || true)"
OS_VER="$(uname -r || true)"
DOTNET_VER="$(dotnet --version 2>/dev/null || true)"
GIT_REV="$(git rev-parse --short HEAD 2>/dev/null || true)"

# Find DB container (prefer hits-sql name, fallback mssql image)
DB_LINE="$(docker ps --format '{{.ID}} {{.Names}} {{.Image}} {{.Status}} {{.Ports}}' 2>/dev/null | (grep -E 'hits-sql' || true) | head -n 1)"
if [[ -z "$DB_LINE" ]]; then
  DB_LINE="$(docker ps --format '{{.ID}} {{.Names}} {{.Image}} {{.Status}} {{.Ports}}' 2>/dev/null | (grep -E 'mssql' || true) | head -n 1)"
fi

cat > "$ENV_JSON" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "scenario": "$SCENARIO",
  "mode": "$MODE",
  "engine": "$ENGINE",
  "base_url": "$BASE_URL",
  "vus": $VUS,
  "duration": "$DURATION",
  "os": { "name": "$OS_NAME", "version": "$OS_VER" },
  "dotnet_version": "$DOTNET_VER",
  "git": "$GIT_REV",
  "db_container": "$(echo "$DB_LINE" | sed 's/"/\\"/g')"
}
EOF

echo "=== k6 run ==="
echo " scenario: $SCENARIO"
echo " mode:     $MODE"
echo " engine:   $ENGINE"
echo " base_url: $BASE_URL"
echo " vus:      $VUS"
echo " duration: $DURATION"
echo " out:      $SC_OUT"
echo ""

if [[ "$ENGINE" == "docker" ]]; then
  docker run --rm -i \
    -e K6_INSECURE_SKIP_TLS_VERIFY=true \
    -v "$(cd "$SC_OUT" && pwd):/out" \
    -v "$(cd "$(dirname "$0")" && pwd)/scripts:/scripts:ro" \
    grafana/k6:latest run "/scripts/scenarios/${SCENARIO}.js" \
      --vus "$VUS" --duration "$DURATION" \
      --summary-export "/out/$(basename "$SUMMARY_JSON")" \
      -e BASE_URL="$BASE_URL" -e SCENARIO="$SCENARIO" -e MODE="$MODE"
else
  k6 run "$SCRIPT" \
    --vus "$VUS" --duration "$DURATION" \
    --summary-export "$SUMMARY_JSON" \
    -e BASE_URL="$BASE_URL" -e SCENARIO="$SCENARIO" -e MODE="$MODE"
fi

echo ""
echo "Saved:"
echo " - $SUMMARY_JSON"
echo " - $ENV_JSON"
echo ""
echo "Next:"
echo " - SCENARIO=$SCENARIO ./make_report.sh"