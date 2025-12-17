#!/usr/bin/env python3
import argparse
import json
import platform
import re
import subprocess
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


def try_cmd(cmd: List[str]) -> Optional[str]:
    code, out = run_cmd(cmd)
    return out.strip() if code == 0 else None


def parse_duration_to_seconds(s: str) -> int:
    # "15s" / "2m" / "1h"
    m = re.match(r"^\s*(\d+)\s*([smh])\s*$", s)
    if not m:
        return 0
    n = int(m.group(1))
    unit = m.group(2)
    if unit == "s":
        return n
    if unit == "m":
        return n * 60
    if unit == "h":
        return n * 3600
    return 0


def parse_k6_stages(js_path: Path) -> Dict[str, Any]:
    """
    Очень простая эвристика: ищем duration:".." и target: N
    Работает для наших скриптов (stages: [{duration:"..", target:..}, ...])
    """
    txt = js_path.read_text(encoding="utf-8", errors="ignore")

    durations = re.findall(r'duration\s*:\s*["\']([^"\']+)["\']', txt)
    targets = re.findall(r'target\s*:\s*(\d+)', txt)

    total_sec = sum(parse_duration_to_seconds(d) for d in durations)
    max_vu = max([int(x) for x in targets], default=0)

    return {
        "stages": [{"duration": d} for d in durations],
        "duration_seconds": total_sec,
        "duration_human": f"{total_sec // 60}m{total_sec % 60:02d}s" if total_sec else "unknown",
        "max_vus": max_vu,
    }


def detect_db_container() -> str:
    """
    Сначала ищем по имени hits-sql,
    если не нашли — по образу mssql.
    """
    fmt = "{{.Names}}|{{.Image}}|{{.ID}}"
    out = try_cmd(["docker", "ps", "--format", fmt])
    if not out:
        return "not detected (docker ps unavailable)"

    lines = [l.strip() for l in out.splitlines() if l.strip()]
    # 1) по имени hits-sql (contains)
    for l in lines:
        name, image, cid = l.split("|", 2)
        if "hits-sql" in name:
            return f"detected by name: {name} ({image}, {cid[:12]})"

    # 2) по образу mssql
    for l in lines:
        name, image, cid = l.split("|", 2)
        if "mssql" in image.lower():
            return f"detected by image: {name} ({image}, {cid[:12]})"

    return "not detected"


def docker_k6_version() -> str:
    out = try_cmd(["docker", "run", "--rm", "grafana/k6", "version"])
    return out or "unknown"


def docker_k6_run(script_base: str, base_url: str, scripts_dir: Path, out_dir: Path,
                  extra_env: Dict[str, str]) -> Tuple[Path, Path]:
    ts = now_ts()
    summary_path = out_dir / f"{script_base}_{ts}.json"
    log_path = out_dir / f"{script_base}_{ts}.log"

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
        f"/scripts/{script_base}.js",
    ]

    code, out = run_cmd(cmd)
    log_path.write_text(out, encoding="utf-8")

    if code != 0:
        print(out)
        raise SystemExit(f"k6 failed for {script_base}. See log: {log_path}")

    if not summary_path.exists():
        raise SystemExit(f"Expected summary json not found: {summary_path}")

    return summary_path, log_path


def extract_core(summary: Dict[str, Any]) -> Dict[str, Any]:
    metrics = summary.get("metrics", {})

    http_reqs = metrics.get("http_reqs", {}) or {}
    dur = metrics.get("http_req_duration", {}) or {}
    failed = metrics.get("http_req_failed", {}) or {}
    iters = metrics.get("iterations", {}) or {}

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


def pct(v: Optional[float]) -> Optional[float]:
    return None if v is None else float(v) * 100.0


def safe_float(x: Any) -> Optional[float]:
    try:
        return None if x is None else float(x)
    except Exception:
        return None


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


def html_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def make_html_report(report_path: Path, env_lines: List[str], notes: str,
                     results: Dict[str, Dict[str, Any]]) -> None:
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

    env_block = "<br/>".join(html_escape(x) for x in env_lines)

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
    <div class="muted">{env_block}</div>
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
      <li>RPS — пропускная способность (сколько запросов/сек реально обработано).</li>
      <li>Latency p95 — “хвост”: 95% запросов быстрее этого значения.</li>
      <li>Error rate — доля запросов с ошибками/не прошедших checks.</li>
      <li>Сценарии с логином обычно дают меньший RPS, потому что там больше шагов и “пользовательские паузы”.</li>
    </ul>
  </div>

  <div class="card">
    <h2>Артефакты</h2>
    <p class="muted">JSON summary и stdout-логи лежат в <code>loadtest/out</code>.</p>
  </div>
</body>
</html>
"""
    report_path.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run k6 load tests via Docker and generate JSON + HTML + meta.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("--scenario", choices=["browse", "auth", "both"], default="both")
    parser.add_argument("--base-url", default="https://host.docker.internal:7146")
    parser.add_argument("--email", default="Java@DlyaLox.ov")
    parser.add_argument("--password", default=".NetDlyaPacan0v")
    parser.add_argument("--out-dir", default="loadtest/out")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--notes", default="App: dotnet run (macOS). DB: SQL Server in Docker. Load tool: k6 in Docker.")
    args = parser.parse_args()

    root = Path.cwd()
    loadtest_dir = (root / "loadtest").resolve()
    out_dir = (root / args.out_dir).resolve()
    ensure_dir(out_dir)
    ensure_dir(loadtest_dir / "out")  # must exist for docker volume write

    # Auto env collection
    docker_ver = (try_cmd(["docker", "--version"]) or "unknown").strip()
    dotnet_ver = (try_cmd(["dotnet", "--version"]) or "unknown").strip()
    k6_ver = docker_k6_version()
    db_info = detect_db_container()

    env_lines = [
        f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"BASE_URL: {args.base_url}",
        f"OS: {platform.platform()} ({platform.machine()})",
        f".NET: {dotnet_ver}",
        f"Docker: {docker_ver}",
        f"k6: {k6_ver}",
        f"DB container: {db_info}",
    ]

    # parse scenario durations from JS files
    browse_meta = parse_k6_stages(loadtest_dir / "k6_menu_browse.js")
    auth_meta = parse_k6_stages(loadtest_dir / "k6_auth_flow.js")

    results: Dict[str, Dict[str, Any]] = {}
    produced: Dict[str, Any] = {"browse": None, "auth": None}

    if args.scenario in ("browse", "both"):
        summary, log = docker_k6_run(
            script_base="k6_menu_browse",
            base_url=args.base_url,
            scripts_dir=loadtest_dir,
            out_dir=out_dir,
            extra_env={}
        )
        data = json.loads(summary.read_text(encoding="utf-8"))
        results["Browse (anonymous menu)"] = extract_core(data)
        produced["browse"] = {"summary": summary.name, "log": log.name, "script": "k6_menu_browse.js", "script_meta": browse_meta}
        print(f"[OK] Browse: {summary.name} / {log.name}")

    if args.scenario in ("auth", "both"):
        summary, log = docker_k6_run(
            script_base="k6_auth_flow",
            base_url=args.base_url,
            scripts_dir=loadtest_dir,
            out_dir=out_dir,
            extra_env={"EMAIL": args.email, "PASSWORD": args.password}
        )
        data = json.loads(summary.read_text(encoding="utf-8"))
        results["Auth flow (login→account→logout)"] = extract_core(data)
        produced["auth"] = {"summary": summary.name, "log": log.name, "script": "k6_auth_flow.js", "script_meta": auth_meta}
        print(f"[OK] Auth: {summary.name} / {log.name}")

    # write meta file for "latest report" discovery
    meta_ts = now_ts()
    meta_path = out_dir / f"runmeta_{meta_ts}.json"
    meta = {
        "timestamp": meta_ts,
        "base_url": args.base_url,
        "env_lines": env_lines,
        "notes": args.notes,
        "produced": produced,
        "results": results,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Meta: {meta_path.name}")

    if args.html:
        html_path = out_dir / f"report_{meta_ts}.html"
        make_html_report(html_path, env_lines=env_lines, notes=args.notes, results=results)
        print(f"[OK] HTML: {html_path.name}")

    # console summary
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