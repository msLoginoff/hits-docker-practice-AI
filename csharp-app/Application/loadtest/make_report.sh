#!/usr/bin/env bash
set -euo pipefail

OUT_ROOT="${OUT_DIR:-./out}"
SCENARIO="${SCENARIO:-}"

if [[ -z "$SCENARIO" ]]; then
  echo "Usage: SCENARIO=<scenario_name> ./make_report.sh"
  echo "Example: SCENARIO=03_checkout_flow ./make_report.sh"
  exit 1
fi

SC_OUT="$OUT_ROOT/$SCENARIO"
if [[ ! -d "$SC_OUT" ]]; then
  echo "Scenario folder not found: $SC_OUT"
  exit 1
fi

LATEST_SUMMARY="$(ls -t "$SC_OUT"/summary_"$SCENARIO"_*.json 2>/dev/null | head -n 1 || true)"
if [[ -z "${LATEST_SUMMARY:-}" ]]; then
  echo "No summary json found in $SC_OUT"
  exit 1
fi

BASENAME="$(basename "$LATEST_SUMMARY")"
if [[ "$BASENAME" =~ ^summary_(.*)_([0-9]{8}_[0-9]{6})\.json$ ]]; then
  TS="${BASH_REMATCH[2]}"
else
  echo "Cannot parse summary filename: $BASENAME"
  exit 1
fi

ENV_JSON="$SC_OUT/env_${SCENARIO}_${TS}.json"
if [[ ! -f "$ENV_JSON" ]]; then
  echo "Env file not found: $ENV_JSON"
  exit 1
fi

REPORT_MD="$SC_OUT/report_${SCENARIO}_${TS}.md"
REPORT_HTML="$SC_OUT/report_${SCENARIO}_${TS}.html"

echo "Generating report:"
echo " - summary: $LATEST_SUMMARY"
echo " - env:     $ENV_JSON"

python3 "$(dirname "$0")/report.py" \
  --summary "$LATEST_SUMMARY" \
  --env "$ENV_JSON" \
  --out-md "$REPORT_MD" \
  --out-html "$REPORT_HTML"

echo "Done:"
echo " - $REPORT_MD"
echo " - $REPORT_HTML"