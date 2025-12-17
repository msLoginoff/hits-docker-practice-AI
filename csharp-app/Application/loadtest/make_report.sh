#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${OUT_DIR:-./out}"
SCENARIO_FILTER="${SCENARIO_FILTER:-}" # optional

pick_latest() {
  if [[ -n "$SCENARIO_FILTER" ]]; then
    ls -t "$OUT_DIR"/summary_"$SCENARIO_FILTER"_*.json 2>/dev/null | head -n 1 || true
  else
    ls -t "$OUT_DIR"/summary_*.json 2>/dev/null | head -n 1 || true
  fi
}

LATEST_SUMMARY="$(pick_latest)"
if [[ -z "${LATEST_SUMMARY:-}" ]]; then
  echo "No summary_*.json found in $OUT_DIR"
  exit 1
fi

BASENAME="$(basename "$LATEST_SUMMARY")"

# summary_(SCENARIO)_(YYYYMMDD_HHMMSS).json
if [[ "$BASENAME" =~ ^summary_(.*)_([0-9]{8}_[0-9]{6})\.json$ ]]; then
  SCENARIO="${BASH_REMATCH[1]}"
  TS="${BASH_REMATCH[2]}"
else
  echo "Cannot parse summary filename: $BASENAME"
  exit 1
fi

ENV_JSON="$OUT_DIR/env_${SCENARIO}_${TS}.json"
if [[ ! -f "$ENV_JSON" ]]; then
  echo "Env file not found: $ENV_JSON"
  echo "Existing env files:"
  ls -1 "$OUT_DIR"/env_*.json 2>/dev/null || true
  exit 1
fi

REPORT_MD="$OUT_DIR/report_${SCENARIO}_${TS}.md"
REPORT_HTML="$OUT_DIR/report_${SCENARIO}_${TS}.html"

echo "Generating report from:"
echo " - $LATEST_SUMMARY"
echo " - $ENV_JSON"

python3 "$(dirname "$0")/report.py" \
  --summary "$LATEST_SUMMARY" \
  --env "$ENV_JSON" \
  --out-md "$REPORT_MD" \
  --out-html "$REPORT_HTML"

echo "Done:"
echo " - $REPORT_MD"
echo " - $REPORT_HTML"