#!/usr/bin/env python3
import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List


def run_cmd(cmd: List[str], cwd: Optional[str] = None) -> Tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.returncode, p.stdout


def now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def docker_k6_run(script_name: str, base_url: str, scripts_dir: Path, out_dir: Path,
                  extra_env: Dict[str, str]) -> Tuple[Path, Path]:
    ts = now_ts()
    summary_path = out_dir / f"{script_name}_{ts}.json"
    log_path = out_dir / f"{script_name}_{ts}.log"

    env_args = []
    for k, v in extra_env.items():
        env_args += ["-e", f"{k}={v}"]

    cmd = [
        "docker", "run", "--rm", "-i",
        "-e", f"BASE_URL={base_url}",
        *env_args,
        "-v", f"{scripts_dir}:/scripts",
        "grafana/k6", "run",
        f"--summary-export=/scripts/out/{summary_path.name}",
        f"/scripts/{script_name}.js",
    ]

    code, out = run_cmd(cmd)
    log_path.write_text(out, encoding="utf-8")

    if code != 0:
        print(out)
        raise SystemExit(f"k6 failed for {script_name}. See log: {log_path}")

    if not summary_path.exists():
        raise SystemExit(f"Expected summary json not found: {summary_path}")

    return summary_path, log_path


def get_metric(m: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    return m.get(name)


def ms(v: Optional[float]) -> Optional[float]:
    return None if v is None else float(v)


def pct(v: Optional[float]) -> Optional[float]:
    return None if v is None else float(v) * 100.0


def extract_core(summary: Dict[str, Any]) -> Dict[str, Any]:
    metrics = summary.get("metrics", {})
    http_reqs = get_metric(metrics, "http_reqs") or {}
    dur = get_metric(metrics, "http_req_duration") or {}
    failed = get_metric(metrics, "http_req_failed") or {}
    iters = get_metric(metrics, "iterations") or {}

    return {
        "requests_count": http_reqs.get("count"),
        "rps": http_reqs.get("rate"),
        "lat_avg_ms": dur.get("avg"),
        "lat_p95_ms": dur.get("p(95)"),
        "lat_p99_ms": dur.get("p(99)"),
        "lat_max_ms": dur.get("max"),
        "error_rate": failed.get("value"),  # 0..1
        "iterations_count": iters.get("count"),
        "iterations_rate": iters.get("rate"),
    }


def grade_latency(p95_ms: float) -> str:
    if p95_ms < 50:
        return "Отлично (очень быстро)"
    if p95_ms < 200:
        return "Хорошо"
    if p95_ms < 800:
        return "Приемлемо"
    return "Плохо (медленно)"


def grade_errors(err_rate: float) -> str:
    if err_rate == 0:
        return "Отлично (0% ошибок)"
    if err_rate < 0.01:
        return "Нормально (<1%)"
    return "Плохо (>=1%)"


def safe_float(x: Any) -> Optional[float]:
    try:
        return None if x is None else float(x)
    except Exception:
        return None


def html_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def make_html_report(report_path: Path, meta: Dict[str, Any], results: Dict[str, Dict[str, Any]]) -> None:
    rows = []
    for name, r in results.items():
        rps = safe_float(r.get("rps"))
        p95 = safe_float(r.get("lat_p95_ms"))
        err = safe_float(r.get("error_rate"))

        rps_s = f"{rps:.2f}" if rps is not None else "—"
        p95_s = f"{p95:.2f} ms" if p95 is not None else "—"
        err_s = f"{pct(err):.2f}%" if err is not None else "—"

        lat_grade = grade_latency(p95) if p95 is not None else "—"
        err_grade = grade_errors(err) if err is not None else "—"

        rows.append(f"""
          <tr>
            <td><b>{html_escape(name)}</b></td>
            <td>{rps_s}</td>
            <td>{p95_s}</td>
            <td>{err_s}</td>
            <td>{html_escape(lat_grade)}</td>
            <td>{html_escape(err_grade)}</td>
          </tr>
        """)

    notes = meta.get("notes", "")
    env_lines = "<br/>".join(html_escape(x) for x in meta.get("env_lines", []))

    html = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Load Test Report — Mockups</title>
  <style>
    body {{ font-family: -apple-system, system-ui, Segoe UI, Roboto, Arial; margin: 24px; }}
    .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 16px; margin-bottom: 16px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #eee; padding: 10px; text-align: left; }}
    th {{ background: #fafafa; }}
    code {{ background: #f6f8fa; padding: 2px 6px; border-radius: 6px; }}
    .muted {{ color: #666; }}
  </style>
</head>
<body>
  <h1>Load Test Report — Mockups</h1>

  <div class="card">
    <h2>Окружение</h2>
    <div class="muted">{env_lines}</div>
    <p class="muted" style="margin-top:10px;">{html_escape(notes)}</p>
  </div>

  <div class="card">
    <h2>Результаты</h2>
    <table>
      <thead>
        <tr>
          <th>Сценарий</th>
          <th>RPS</th>
          <th>Latency p95</th>
          <th>Error rate</th>
          <th>Оценка latency</th>
          <th>Оценка ошибок</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>Авто-вывод</h2>
    <ul>
      <li>RPS — это пропускная способность (сколько запросов/сек реально обработано).</li>
      <li>Latency p95 — ключевая метрика “хвостов”: 95% запросов быстрее этого значения.</li>
      <li>Error rate — доля запросов, которые не прошли проверки/вернули ошибки.</li>
      <li>Сценарии с логином почти всегда дают меньший RPS, потому что там больше действий и обычно есть паузы (sleep), как у реального пользователя.</li>
    </ul>
  </div>

  <div class="card">
    <h2>Файлы</h2>
    <p class="muted">Исходные JSON summary и лог stdout лежат рядом в папке <code>loadtest/out</code>.</p>
  </div>
</body>
</html>
"""
    report_path.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run k6 load tests via Docker and generate JSON + HTML reports.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("--scenario", choices=["browse", "auth", "both"], default="both",
                        help="Which scenario(s) to run.")
    parser.add_argument("--base-url", default="https://host.docker.internal:7146",
                        help="Base URL of the app as seen from Docker container.")
    parser.add_argument("--email", default="Java@DlyaLox.ov", help="Login email for auth scenario.")
    parser.add_argument("--password", default=".NetDlyaPacan0v", help="Login password for auth scenario.")
    parser.add_argument("--out-dir", default="loadtest/out", help="Output directory (json/log/html).")
    parser.add_argument("--html", action="store_true", help="Generate HTML report.")
    parser.add_argument("--notes", default="App запущен локально (dotnet run). DB: SQL Server в Docker. Load tool: k6 в Docker.",
                        help="Free-form notes to embed into report.")
    parser.add_argument("--env", action="append", default=[],
                        help="Extra environment lines (repeatable), e.g. --env 'dotnet: 6.0'")

    args = parser.parse_args()

    project_root = Path.cwd()
    scripts_dir = (project_root / "loadtest").resolve()
    out_dir = (project_root / args.out_dir).resolve()
    ensure_dir(out_dir)

    # k6 reads scripts from /scripts; we also want to write summary into /scripts/out
    ensure_dir(scripts_dir / "out")

    # Meta environment lines
    env_lines = [
        f"Дата/время: {datetime.now().isoformat(timespec='seconds')}",
        f"BASE_URL: {args.base_url}",
        f"OS: {platform.platform()}",
        f"Python: {platform.python_version()}",
        "k6: grafana/k6 (Docker)",
        *args.env,
    ]

    results = {}

    if args.scenario in ("browse", "both"):
        summary, log = docker_k6_run(
            script_name="k6_menu_browse",
            base_url=args.base_url,
            scripts_dir=scripts_dir,
            out_dir=out_dir,
            extra_env={}
        )
        data = json.loads(summary.read_text(encoding="utf-8"))
        results["Browse (anonymous menu)"] = extract_core(data)
        print(f"[OK] Browse сценарий: {summary.name} / {log.name}")

    if args.scenario in ("auth", "both"):
        summary, log = docker_k6_run(
            script_name="k6_auth_flow",
            base_url=args.base_url,
            scripts_dir=scripts_dir,
            out_dir=out_dir,
            extra_env={"EMAIL": args.email, "PASSWORD": args.password}
        )
        data = json.loads(summary.read_text(encoding="utf-8"))
        results["Auth flow (login→account→logout)"] = extract_core(data)
        print(f"[OK] Auth сценарий: {summary.name} / {log.name}")

    if args.html:
        report_path = out_dir / f"report_{now_ts()}.html"
        make_html_report(report_path, meta={"env_lines": env_lines, "notes": args.notes}, results=results)
        print(f"[OK] HTML report generated: {report_path}")

    # Print a small console summary too
    print("\n=== Summary ===")
    for name, r in results.items():
        rps = safe_float(r.get("rps"))
        p95 = safe_float(r.get("lat_p95_ms"))
        err = safe_float(r.get("error_rate"))
        print(f"- {name}")
        print(f"  RPS: {rps:.2f}" if rps is not None else "  RPS: —")
        print(f"  p95: {p95:.2f} ms ({grade_latency(p95)})" if p95 is not None else "  p95: —")
        print(f"  error: {pct(err):.2f}% ({grade_errors(err)})" if err is not None else "  error: —")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())