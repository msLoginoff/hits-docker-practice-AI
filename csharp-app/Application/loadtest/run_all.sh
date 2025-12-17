#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://host.docker.internal:5146}"
ENGINE="${ENGINE:-docker}"
OUT_DIR="${OUT_DIR:-./out}"
MODE="${MODE:-baseline}"   # baseline | stress

SCENARIOS=(01_anonymous_menu 02_auth_flow 03_checkout_flow 04_admin_browse)

for s in "${SCENARIOS[@]}"; do
  echo ""
  echo "=============================="
  echo "Running scenario: $s ($MODE)"
  echo "=============================="
  SCENARIO="$s" MODE="$MODE" BASE_URL="$BASE_URL" ENGINE="$ENGINE" OUT_DIR="$OUT_DIR" \
    ./run.sh
done

echo ""
echo "=============================="
echo "Building suite report"
echo "=============================="
OUT_DIR="$OUT_DIR" ./make_suite_report.sh