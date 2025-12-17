#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://host.docker.internal:5146}"
ENGINE="${ENGINE:-docker}"
OUT_DIR="${OUT_DIR:-./out}"

# можно подкрутить нагрузки отдельно на каждый сценарий:
declare -A VUS_MAP=(
  [01_anonymous_menu]=15
  [02_auth_flow]=8
  [03_checkout_flow]=5
  [04_admin_browse]=5
)
declare -A DUR_MAP=(
  [01_anonymous_menu]=100s
  [02_auth_flow]=100s
  [03_checkout_flow]=100s
  [04_admin_browse]=100s
)

SCENARIOS=(01_anonymous_menu 02_auth_flow 03_checkout_flow 04_admin_browse)

for s in "${SCENARIOS[@]}"; do
  echo "=== Running $s ==="
  SCENARIO="$s" BASE_URL="$BASE_URL" ENGINE="$ENGINE" OUT_DIR="$OUT_DIR" \
    VUS="${VUS_MAP[$s]}" DURATION="${DUR_MAP[$s]}" \
    ./run.sh
done

echo "=== Building suite report ==="
./make_suite_report.sh