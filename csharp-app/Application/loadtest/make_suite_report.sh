#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${OUT_DIR:-./out}"
python3 "$(dirname "$0")/suite_report.py" --out "$OUT_DIR"