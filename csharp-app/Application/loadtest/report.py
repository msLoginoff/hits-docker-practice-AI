#!/usr/bin/env python3
import argparse
import json
import math
import pathlib
from datetime import datetime
from html import escape

# ---------- helpers ----------
def ms(v):
    if v is None:
        return None
    return float(v)

def fmt_ms(v):
    if v is None:
        return "-"
    return f"{v:.2f} ms"

def fmt_rate(v):
    if v is None:
        return "-"
    return f"{v:.2f}/s"

def fmt_pct(v):
    if v is None:
        return "-"
    return f"{v*100:.2f}%"

def fmt_int(v):
    if v is None:
        return "-"
    try:
        return f"{int(v)}"
    except:
        return str(v)

def fmt_bytes(n):
    if n is None:
        return "-"
    n = float(n)
    units = ["B", "KB", "MB", "GB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.2f} {units[i]}"

def get_metric(metrics, name):
    return metrics.get(name, {})

def get_thresholds(metric_obj):
    # In k6 summary-export, threshold value is usually "breached" boolean:
    # false => OK (not breached), true => FAIL (breached)
    th = metric_obj.get("thresholds")
    if not isinstance(th, dict):
        return []
    out = []
    for expr, breached in th.items():
        out.append((expr, bool(breached)))
    return out

def walk_checks(group, acc):
    checks = group.get("checks") or {}
    for chk_name, chk in checks.items():
        acc.append({
            "name": chk.get("name", chk_name),
            "path": chk.get("path", ""),
            "passes": chk.get("passes", 0),
            "fails": chk.get("fails", 0),
        })
    groups = group.get("groups") or {}
    for _, g in groups.items():
        walk_checks(g, acc)

def summarize(summary):
    metrics = summary.get("metrics", {})
    root = summary.get("root_group", {})

    checks = []
    walk_checks(root, checks)
    total_pass = sum(c["passes"] for c in checks)
    total_fail = sum(c["fails"] for c in checks)
    checks_total = total_pass + total_fail
    checks_pass_rate = (total_pass / checks_total) if checks_total else None

    # Key metrics
    http_reqs = get_metric(metrics, "http_reqs")
    http_failed = get_metric(metrics, "http_req_failed")
    http_dur = get_metric(metrics, "http_req_duration")
    http_wait = get_metric(metrics, "http_req_waiting")
    iter_rate = get_metric(metrics, "iterations")
    iter_dur = get_metric(metrics, "iteration_duration")
    vus_max = get_metric(metrics, "vus_max")
    vus = get_metric(metrics, "vus")
    data_in = get_metric(metrics, "data_received")
    data_out = get_metric(metrics, "data_sent")

    # Thresholds summary across all metrics that have thresholds
    thresholds = []
    for mname, mobj in metrics.items():
        for expr, breached in get_thresholds(mobj):
            thresholds.append({
                "metric": mname,
                "expr": expr,
                "breached": breached,  # true => FAIL
            })

    return {
        "checks_total": checks_total,
        "checks_pass_rate": checks_pass_rate,
        "checks_fail_count": total_fail,
        "checks_pass_count": total_pass,
        "checks_details": sorted(checks, key=lambda x: (x["fails"], x["name"]), reverse=True),

        "thresholds": thresholds,

        "http_reqs_count": http_reqs.get("count"),
        "http_reqs_rate": http_reqs.get("rate"),
        "http_failed_rate": http_failed.get("value"),
        "http_dur_avg": http_dur.get("avg"),
        "http_dur_p95": http_dur.get("p(95)"),
        "http_dur_p90": http_dur.get("p(90)"),
        "http_dur_max": http_dur.get("max"),
        "http_wait_avg": http_wait.get("avg"),
        "http_wait_p95": http_wait.get("p(95)"),

        "iter_count": iter_rate.get("count"),
        "iter_rate": iter_rate.get("rate"),
        "iter_dur_avg": iter_dur.get("avg"),
        "iter_dur_p95": iter_dur.get("p(95)"),
        "vus": vus.get("value"),
        "vus_max": vus_max.get("value"),

        "data_in": data_in.get("count"),
        "data_in_rate": data_in.get("rate"),
        "data_out": data_out.get("count"),
        "data_out_rate": data_out.get("rate"),
    }

def build_auto_findings(env, s):
    findings = []

    # 1) Validity via checks
    if s["checks_pass_rate"] is not None and s["checks_pass_rate"] < 1.0:
        findings.append(
            f"❌ Checks pass rate {fmt_pct(s['checks_pass_rate'])} — сценарий частично невалиден (логика/парсинг/ожидания не совпали). "
            f"Это НЕ HTTP error rate, а именно провал check-условий."
        )
    else:
        findings.append("✅ Все checks прошли (functional flow валиден).")

    # 2) Thresholds
    breached = [t for t in s["thresholds"] if t["breached"]]
    if breached:
        top = ", ".join([f"{t['metric']}:{t['expr']}" for t in breached[:6]])
        findings.append(f"❌ Есть breached thresholds: {top}")
    else:
        if s["thresholds"]:
            findings.append("✅ Thresholds не breached (пороги выдержаны).")
        else:
            findings.append("ℹ️ Thresholds не заданы в отчёте (можно добавить/усилить).")

    # 3) Error rate heuristic
    er = s["http_failed_rate"]
    if er is not None:
        if er > 0.01:
            findings.append(f"❌ HTTP error rate высокий: {fmt_pct(er)}")
        elif er > 0:
            findings.append(f"⚠️ HTTP error rate ненулевой: {fmt_pct(er)}")
        else:
            findings.append("✅ HTTP error rate = 0%")

    # 4) Latency heuristic (soft)
    p95 = s["http_dur_p95"]
    if p95 is not None:
        if p95 > 800:
            findings.append(f"⚠️ p95 latency {fmt_ms(p95)} — высоковато (для локального стенда это уже подозрительно).")
        else:
            findings.append(f"✅ p95 latency {fmt_ms(p95)}")

    # 5) RPS context
    rps = s["http_reqs_rate"]
    if rps is not None:
        findings.append(f"ℹ️ Наблюдаемый RPS: {rps:.2f}/s (зависит от VUs и 'think time' в сценарии).")

    # 6) Environment note
    engine = env.get("engine", "")
    base = env.get("base_url", "")
    if engine == "docker" and "localhost" in base:
        findings.append("⚠️ Base URL содержит localhost при ENGINE=docker — это обычно ошибка (в docker localhost ≠ хост).")

    return findings

def md_report(env, s, summary_path, env_path):
    lines = []
    lines.append(f"# Load test report — {env.get('scenario','')} ({env.get('mode','')})")
    lines.append("")
    lines.append(f"- Timestamp: {env.get('timestamp','')}")
    lines.append(f"- Base URL: {env.get('base_url','')}")
    lines.append(f"- Engine: {env.get('engine','')}")
    lines.append(f"- VUs: {env.get('vus','')}  Duration: {env.get('duration','')}")
    lines.append(f"- OS: {env.get('os',{}).get('name','')} {env.get('os',{}).get('version','')}")
    lines.append(f"- .NET: {env.get('dotnet_version','')}")
    if env.get("git"):
        lines.append(f"- Git: {env['git']}")
    if env.get("db_container"):
        lines.append(f"- DB container: {env['db_container']}")
    lines.append("")
    lines.append("## Key results")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| HTTP RPS | {s['http_reqs_rate']:.2f}/s |" if s["http_reqs_rate"] is not None else "| HTTP RPS | - |")
    lines.append(f"| HTTP count | {fmt_int(s['http_reqs_count'])} |")
    lines.append(f"| http_req_duration avg | {fmt_ms(s['http_dur_avg'])} |")
    lines.append(f"| http_req_duration p95 | {fmt_ms(s['http_dur_p95'])} |")
    lines.append(f"| http_req_duration max | {fmt_ms(s['http_dur_max'])} |")
    lines.append(f"| http_req_failed (rate) | {fmt_pct(s['http_failed_rate'])} |")
    lines.append(f"| checks pass rate | {fmt_pct(s['checks_pass_rate'])} |")
    lines.append(f"| iterations rate | {fmt_rate(s['iter_rate'])} |")
    lines.append(f"| vus / vus_max | {fmt_int(s['vus'])} / {fmt_int(s['vus_max'])} |")
    lines.append(f"| data received | {fmt_bytes(s['data_in'])} ({fmt_bytes(s['data_in_rate'])}/s) |")
    lines.append(f"| data sent | {fmt_bytes(s['data_out'])} ({fmt_bytes(s['data_out_rate'])}/s) |")
    lines.append("")

    lines.append("## Auto findings")
    lines.append("")
    for f in build_auto_findings(env, s):
        lines.append(f"- {f}")
    lines.append("")

    lines.append("## Thresholds")
    lines.append("")
    if not s["thresholds"]:
        lines.append("- (none)")
    else:
        lines.append("| Metric | Threshold | Status |")
        lines.append("|---|---|---|")
        for t in s["thresholds"]:
            status = "FAIL (breached)" if t["breached"] else "OK"
            lines.append(f"| {t['metric']} | {t['expr']} | {status} |")
    lines.append("")

    lines.append("## Checks (top by failures)")
    lines.append("")
    lines.append("| Check | Pass | Fail |")
    lines.append("|---|---:|---:|")
    for c in s["checks_details"][:20]:
        lines.append(f"| {c['path'] or c['name']} | {c['passes']} | {c['fails']} |")
    lines.append("")
    lines.append("## Raw files")
    lines.append("")
    lines.append(f"- Summary JSON: {summary_path}")
    lines.append(f"- Env JSON: {env_path}")
    lines.append("")
    return "\n".join(lines)

def html_report(env, s, summary_path, env_path):
    def badge(ok, text_ok="OK", text_fail="FAIL"):
        return f"<span style='padding:2px 8px;border-radius:999px;background:{'#d1fae5' if ok else '#fee2e2'}'>{escape(text_ok if ok else text_fail)}</span>"

    findings = build_auto_findings(env, s)
    breached = [t for t in s["thresholds"] if t["breached"]]
    checks_ok = (s["checks_pass_rate"] is None) or (s["checks_pass_rate"] >= 1.0)

    return f"""<!doctype html>
<meta charset="utf-8">
<title>Load test report</title>
<style>
  body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial; margin:40px; color:#111}}
  h1{{margin-bottom:6px}}
  .muted{{color:#666}}
  .grid{{display:grid; grid-template-columns: 1fr 1fr; gap:16px;}}
  .card{{border:1px solid #e5e7eb; border-radius:14px; padding:16px}}
  table{{border-collapse:collapse; width:100%}}
  th,td{{border:1px solid #e5e7eb; padding:8px; text-align:left}}
  th{{background:#f9fafb}}
  .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}}
</style>

<h1>Load test report — {escape(env.get('scenario',''))} <span class="muted">({escape(env.get('mode',''))})</span></h1>
<div class="muted">Timestamp: {escape(env.get('timestamp',''))}</div>

<div class="grid" style="margin-top:16px">
  <div class="card">
    <h2 style="margin-top:0">Environment</h2>
    <ul>
      <li>OS: {escape(env.get('os',{}).get('name',''))} {escape(env.get('os',{}).get('version',''))}</li>
      <li>.NET: {escape(env.get('dotnet_version',''))}</li>
      <li>Base URL: <span class="mono">{escape(env.get('base_url',''))}</span></li>
      <li>Engine: {escape(env.get('engine',''))}</li>
      <li>VUs: {escape(str(env.get('vus','')))} Duration: {escape(str(env.get('duration','')))}</li>
      <li>DB container: <span class="mono">{escape(env.get('db_container',''))}</span></li>
      <li>Git: <span class="mono">{escape(env.get('git',''))}</span></li>
    </ul>
  </div>

  <div class="card">
    <h2 style="margin-top:0">Status</h2>
    <ul>
      <li>Checks: {badge(checks_ok, "OK", "FAIL")} pass rate: <b>{escape(fmt_pct(s['checks_pass_rate']))}</b></li>
      <li>Thresholds: {badge(len(breached)==0, "OK", "FAIL")} breached: <b>{len(breached)}</b></li>
      <li>HTTP error rate: <b>{escape(fmt_pct(s['http_failed_rate']))}</b></li>
      <li>RPS: <b>{escape(f"{s['http_reqs_rate']:.2f}/s" if s['http_reqs_rate'] is not None else "-")}</b></li>
      <li>Latency p95: <b>{escape(fmt_ms(s['http_dur_p95']))}</b></li>
    </ul>
  </div>
</div>

<div class="card" style="margin-top:16px">
  <h2 style="margin-top:0">Key results</h2>
  <table>
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>HTTP RPS</td><td>{escape(f"{s['http_reqs_rate']:.2f}/s" if s['http_reqs_rate'] is not None else "-")}</td></tr>
    <tr><td>HTTP count</td><td>{escape(fmt_int(s['http_reqs_count']))}</td></tr>
    <tr><td>http_req_duration avg</td><td>{escape(fmt_ms(s['http_dur_avg']))}</td></tr>
    <tr><td>http_req_duration p95</td><td>{escape(fmt_ms(s['http_dur_p95']))}</td></tr>
    <tr><td>http_req_duration max</td><td>{escape(fmt_ms(s['http_dur_max']))}</td></tr>
    <tr><td>http_req_waiting avg</td><td>{escape(fmt_ms(s['http_wait_avg']))}</td></tr>
    <tr><td>http_req_waiting p95</td><td>{escape(fmt_ms(s['http_wait_p95']))}</td></tr>
    <tr><td>iterations rate</td><td>{escape(fmt_rate(s['iter_rate']))}</td></tr>
    <tr><td>iteration_duration avg</td><td>{escape(fmt_ms(s['iter_dur_avg']))}</td></tr>
    <tr><td>iteration_duration p95</td><td>{escape(fmt_ms(s['iter_dur_p95']))}</td></tr>
    <tr><td>vus / vus_max</td><td>{escape(fmt_int(s['vus']))} / {escape(fmt_int(s['vus_max']))}</td></tr>
    <tr><td>data received</td><td>{escape(fmt_bytes(s['data_in']))} ({escape(fmt_bytes(s['data_in_rate']))}/s)</td></tr>
    <tr><td>data sent</td><td>{escape(fmt_bytes(s['data_out']))} ({escape(fmt_bytes(s['data_out_rate']))}/s)</td></tr>
  </table>
</div>

<div class="card" style="margin-top:16px">
  <h2 style="margin-top:0">Auto findings</h2>
  <ul>
    {''.join(f"<li>{escape(x)}</li>" for x in findings)}
  </ul>
</div>

<div class="grid" style="margin-top:16px">
  <div class="card">
    <h2 style="margin-top:0">Thresholds</h2>
    {"<div class='muted'>(none)</div>" if not s["thresholds"] else ""}
    {"" if not s["thresholds"] else "<table><tr><th>Metric</th><th>Threshold</th><th>Status</th></tr>" + "".join(
      f"<tr><td class='mono'>{escape(t['metric'])}</td><td class='mono'>{escape(t['expr'])}</td><td>{badge(not t['breached'], 'OK', 'FAIL')}</td></tr>"
      for t in s["thresholds"]
    ) + "</table>"}
  </div>

  <div class="card">
    <h2 style="margin-top:0">Checks (top by failures)</h2>
    <table>
      <tr><th>Check</th><th>Pass</th><th>Fail</th></tr>
      {''.join(
        f"<tr><td class='mono'>{escape((c['path'] or c['name']))}</td><td>{c['passes']}</td><td>{c['fails']}</td></tr>"
        for c in s["checks_details"][:20]
      )}
    </table>
  </div>
</div>

<div class="card" style="margin-top:16px">
  <h2 style="margin-top:0">Raw files</h2>
  <div>Summary JSON: <span class="mono">{escape(str(summary_path))}</span></div>
  <div>Env JSON: <span class="mono">{escape(str(env_path))}</span></div>
</div>
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", required=True)
    ap.add_argument("--env", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-html", required=True)
    args = ap.parse_args()

    summary_path = pathlib.Path(args.summary)
    env_path = pathlib.Path(args.env)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    env = json.loads(env_path.read_text(encoding="utf-8"))

    s = summarize(summary)

    pathlib.Path(args.out_md).write_text(md_report(env, s, summary_path, env_path), encoding="utf-8")
    pathlib.Path(args.out_html).write_text(html_report(env, s, summary_path, env_path), encoding="utf-8")

if __name__ == "__main__":
    main()