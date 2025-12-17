#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="$(cd "$(dirname "$0")" && pwd)/out"

# Самый свежий meta (по времени изменения)
META="$(ls -t "$OUT_DIR"/runmeta_*.json 2>/dev/null | head -n 1 || true)"
if [[ -z "${META}" ]]; then
  echo "ERROR: runmeta_*.json not found in $OUT_DIR"
  echo "Run: python3 loadtest/run_loadtest.py --scenario both --html"
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
REPORT="$OUT_DIR/report_${TS}.md"

python3 - <<'PY' "$META" "$REPORT"
import json, sys, os
from pathlib import Path

meta_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])

meta = json.loads(meta_path.read_text(encoding="utf-8"))

ts = meta.get("timestamp", "unknown")
base_url = meta.get("base_url", "unknown")
env_lines = meta.get("env_lines", [])
notes = meta.get("notes", "")
produced = meta.get("produced", {})
results = meta.get("results", {})

def pct(v):
    return None if v is None else v*100.0

def fnum(v, nd=2):
    return "—" if v is None else f"{v:.{nd}f}"

def grade_latency(p95):
    if p95 is None: return "—"
    if p95 < 50: return "Отлично"
    if p95 < 200: return "Хорошо"
    if p95 < 800: return "Приемлемо"
    return "Плохо"

def grade_err(er):
    if er is None: return "—"
    if er == 0: return "Отлично"
    if er < 0.01: return "Нормально"
    return "Плохо"

# ссылки на артефакты
html_candidates = sorted(meta_path.parent.glob(f"report_{ts}.html"))
html_name = html_candidates[0].name if html_candidates else "—"

lines = []
lines.append(f"# Load Testing Report — Mockups ({ts})")
lines.append("")
lines.append("## Что сделано (пункт 2)")
lines.append("- Подготовлены k6-сценарии нагрузки и выполнены прогоны.")
lines.append("- Собраны метрики: **RPS**, **latency (p95)**, **error rate**.")
lines.append("")
lines.append("## Окружение")
lines.append(f"- BASE_URL: `{base_url}`")
for l in env_lines:
    lines.append(f"- {l}")
lines.append("")
lines.append("## Артефакты")
lines.append(f"- Meta: `{meta_path.name}`")
lines.append(f"- HTML: `{html_name}`")
lines.append("- JSON/LOG: см. файлы в `loadtest/out`")
lines.append("")
lines.append("## Результаты (итоговая таблица)")
lines.append("")
lines.append("| Сценарий | RPS | p95 (ms) | error rate | Комментарий |")
lines.append("|---|---:|---:|---:|---|")

for name, r in results.items():
    rps = r.get("rps")
    p95 = r.get("lat_p95_ms")
    er = r.get("error_rate")
    comment = f"latency: {grade_latency(p95)}, errors: {grade_err(er)}"
    lines.append(f"| {name} | {fnum(rps)} | {fnum(p95)} | {fnum(pct(er))}% | {comment} |")

lines.append("")
lines.append("## Краткий анализ")
lines.append("- Сценарий **Auth flow** обычно показывает меньший RPS, т.к. включает больше шагов (GET+POST) и работу с куками/Identity.")
lines.append("- **p95** отражает “хвосты”: 95% запросов быстрее указанного значения. Для локального окружения значения в десятках миллисекунд считаются очень хорошими.")
lines.append("- **Error rate** = доля запросов с ошибками/не прошедших checks. В идеале стремимся к 0%.")
lines.append("")
lines.append("## Использованные LLM и промпты (заполнить)")
lines.append("- Модель(и): …")
lines.append("- Промпт(ы): … (вставь ключевые запросы, которыми генерировались сценарии/команды/шаблоны отчёта)")
lines.append("")
lines.append("## Команды запуска (пример)")
lines.append("```bash")
lines.append("python3 loadtest/run_loadtest.py --scenario both --html --base-url \"https://host.docker.internal:7146\"")
lines.append("./loadtest/generate_report.sh")
lines.append("```")
lines.append("")
lines.append(f"> Notes: {notes}")

out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"OK: wrote {out_path}")
PY

echo "Generated: $REPORT"