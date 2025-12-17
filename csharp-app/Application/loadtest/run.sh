#!/usr/bin/env bash
set -euo pipefail

SCENARIO="${SCENARIO:-01_anonymous_menu}"
BASE_URL="${BASE_URL:-http://localhost:5146}"
VUS="${VUS:-15}"
DURATION="${DURATION:-100s}"
OUT_DIR="${OUT_DIR:-./out}"
ENGINE="${ENGINE:-docker}" # docker | local
INSECURE="${INSECURE:-true}"

# для checkout
USER_COUNT="${USER_COUNT:-10}"

mkdir -p "$OUT_DIR"

TS="$(date +%Y%m%d_%H%M%S)"
SC_OUT="$OUT_DIR/$SCENARIO"
mkdir -p "$SC_OUT"

SUMMARY_JSON="$SC_OUT/summary_${SCENARIO}_${TS}.json"
ENV_JSON="$SC_OUT/env_${SCENARIO}_${TS}.json"

echo "== Loadtest =="
echo "scenario: $SCENARIO"
echo "base_url : $BASE_URL"
echo "vus      : $VUS"
echo "duration : $DURATION"
echo "engine   : $ENGINE"
echo ""

if [[ "$ENGINE" == "docker" && "$BASE_URL" == *"localhost"* ]]; then
  echo "WARNING: ENGINE=docker + BASE_URL contains localhost."
  echo "In Docker, localhost points to the k6 container, not your Mac."
  echo "Use: http://host.docker.internal:5146 (or https://host.docker.internal:7146 with INSECURE=true)"
  echo ""
fi

# --- environment snapshot ---
OS_NAME="$(uname -s || true)"
OS_VER="$(uname -r || true)"
DOTNET_VER="$(dotnet --version 2>/dev/null || echo "n/a")"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo "n/a")"

# docker DB detection (prefer by name hits-sql, fallback to mssql)
DB_CONTAINER_LINE="$(docker ps --filter "name=hits-sql" --format "{{.ID}} {{.Image}} {{.Status}} {{.Ports}}" | head -n 1 || true)"
if [[ -z "$DB_CONTAINER_LINE" ]]; then
  DB_CONTAINER_LINE="$(docker ps --filter "ancestor=mcr.microsoft.com/mssql/server" --format "{{.ID}} {{.Image}} {{.Status}} {{.Ports}}" | head -n 1 || true)"
fi

cat > "$ENV_JSON" <<EOF
{
  "timestamp": "$TS",
  "scenario": "$SCENARIO",
  "base_url": "$BASE_URL",
  "vus": $VUS,
  "duration": "$DURATION",
  "engine": "$ENGINE",
  "git_sha": "$GIT_SHA",
  "os": { "name": "$OS_NAME", "version": "$OS_VER" },
  "dotnet_version": "$DOTNET_VER",
  "db_container": "$(echo "$DB_CONTAINER_LINE" | sed 's/"/\\"/g')"
}
EOF

# --- k6 run ---
SCRIPT_PATH="./scenarios/${SCENARIO}.js"

K6_ARGS=(run "$SCRIPT_PATH" --vus "$VUS" --duration "$DURATION" --summary-export "$SUMMARY_JSON")
if [[ "$INSECURE" == "true" ]]; then
  K6_ARGS+=(--insecure-skip-tls-verify)
fi

echo "Running k6..."
if [[ "$ENGINE" == "local" ]]; then
  BASE_URL="$BASE_URL" USER_COUNT="$USER_COUNT" k6 "${K6_ARGS[@]}"
else
  # docker k6: скрипты читаем из /scripts, результаты пишем в /out
  docker run --rm -i \
    -e BASE_URL="$BASE_URL" \
    -e USER_COUNT="$USER_COUNT" \
    -v "$(pwd):/scripts" \
    -v "$(cd "$SC_OUT" && pwd):/out" \
    grafana/k6 \
    run "/scripts/scenarios/${SCENARIO}.js" \
      --vus "$VUS" --duration "$DURATION" \
      --summary-export "/out/$(basename "$SUMMARY_JSON")" \
      $( [[ "$INSECURE" == "true" ]] && echo "--insecure-skip-tls-verify" )
fi

echo ""
echo "Saved:"
echo " - $SUMMARY_JSON"
echo " - $ENV_JSON"