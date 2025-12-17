#!/usr/bin/env python3
import argparse
import json
import pathlib
import re
from datetime import datetime
from html import escape

from report import summarize as summarize_one, build_auto_findings

def latest_pair(folder: pathlib.Path):
    files = sorted(folder.glob("summary_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    summary = files[0]
    m = re.match(r"^summary_(.*)_([0-9]{8}_[0-9]{6})\.json$", summary.name)
    if not m:
        return None
    scenario, ts = m.group(1), m.group(2)
    env = folder / f"env_{scenario}_{ts}.json"
    if not env.exists():
        return None
    return summary, env, scenario, ts

def fmt_pct(v):
    if v is None:
        return "-"
    return f"{v*100:.2f}%"

def fmt_ms(v):
    if v is None:
        return "-"
    return f"{float(v):.2f} ms"

def fmt_rate(v):
    if v is None:
        return "-"
    return f"{float(v):.2f}/s"

def badge(ok):
    return f"<span style='padding:2px 8px;border-radius:999px;background:{'#d1fae5' if ok else '#fee2e2'}'>{'OK' if ok else 'FAIL'}</span>"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out_dir = pathlib.Path(args.out)
    scenario_dirs = [p for p in out_dir.iterdir() if p.is_dir()]

    rows = []
    env_any = None

    for d in sorted(scenario_dirs):
        pair = latest_pair(d)
        if not pair:
            continue

        summary_p, env_p, scenario, ts = pair
        summary = json.loads(summary_p.read_text(encoding="utf-8"))
        env = json.loads(env_p.read_text(encoding="utf-8"))
        env_any = env_any or env

        s = summarize_one(summary)
        breached = [t for t in s["thresholds"] if t["breached"]]
        checks_ok = (s["checks_pass_rate"] is None) or (s["checks_pass_rate"] >= 1.0)
        thresholds_ok = (len(breached) == 0)

        rows.append({
            "scenario": scenario,
            "ts": ts,
            "env": env,
            "summary_path": str(summary_p),
            "env_path": str(env_p),
            "rps": s["http_reqs_rate"],
            "avg": s["http_dur_avg"],
            "p95": s["http_dur_p95"],
            "err": s["http_failed_rate"],
            "checks_pass_rate": s["checks_pass_rate"],
            "checks_fail": s["checks_fail_count"],
            "thresholds_breached": len(breached),
            "checks_ok": checks_ok,
            "thresholds_ok": thresholds_ok,
            "details": s,
        })

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = out_dir / f"suite_report_{now}.md"
    html_path = out_dir / f"suite_report_{now}.html"

    # MD
    md = []
    md.append(f"# Load testing suite report — {now}\n")
    if env_any:
        md.append("## Environment (from latest run)\n")
        md.append(f"- OS: {env_any.get('os',{}).get('name','')} {env_any.get('os',{}).get('version','')}")
        md.append(f"- .NET: {env_any.get('dotnet_version','')}")
        md.append(f"- Base URL: {env_any.get('base_url','')}")
        md.append(f"- Engine: {env_any.get('engine','')}")
        if env_any.get("db_container"):
            md.append(f"- DB container: {env_any.get('db_container','')}")
        if env_any.get("git"):
            md.append(f"- Git: {env_any.get('git','')}")
        md.append("")

    md.append("## Scenario summary\n")
    md.append("| Scenario | Timestamp | Mode | VUs | Duration | RPS | avg ms | p95 ms | http err | checks pass | thresholds |")
    md.append("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        env = r["env"]
        md.append(
            f"| {r['scenario']} | {r['ts']} | {env.get('mode','')} | {env.get('vus','')} | {env.get('duration','')} | "
            f"{(r['rps'] or 0):.2f} | {(r['avg'] or 0):.2f} | {(r['p95'] or 0):.2f} | {fmt_pct(r['err'])} | "
            f"{fmt_pct(r['checks_pass_rate'])} | {'OK' if r['thresholds_ok'] else 'FAIL'} ({r['thresholds_breached']}) |"
        )
    md.append("")

    md.append("## Auto findings (suite)\n")
    for r in rows:
        md.append(f"### {r['scenario']}\n")
        for f in build_auto_findings(r["env"], r["details"]):
            md.append(f"- {f}")
        md.append(f"- Raw summary: {r['summary_path']}")
        md.append(f"- Raw env: {r['env_path']}\n")

    md_path.write_text("\n".join(md), encoding="utf-8")

    # HTML
    def tr(r):
        env = r["env"]
        return f"""
<tr>
  <td class="mono">{escape(r["scenario"])}</td>
  <td class="mono">{escape(r["ts"])}</td>
  <td>{escape(str(env.get("mode","")))}</td>
  <td>{escape(str(env.get("vus","")))}</td>
  <td class="mono">{escape(str(env.get("duration","")))}</td>
  <td>{(r["rps"] or 0):.2f}</td>
  <td>{(r["avg"] or 0):.2f}</td>
  <td>{(r["p95"] or 0):.2f}</td>
  <td>{escape(fmt_pct(r["err"]))}</td>
  <td>{escape(fmt_pct(r["checks_pass_rate"]))}</td>
  <td>{badge(r["thresholds_ok"])} ({r["thresholds_breached"]})</td>
</tr>
"""

    cards = []
    for r in rows:
        findings = build_auto_findings(r["env"], r["details"])
        checks_top = r["details"]["checks_details"][:8]
        thr = r["details"]["thresholds"][:12]

        cards.append(f"""
<div class="card">
  <h2 style="margin-top:0">{escape(r["scenario"])}</h2>
  <div class="muted mono">{escape(r["ts"])}</div>

  <p>
    Checks: {badge(r["checks_ok"])} ({escape(fmt_pct(r["checks_pass_rate"]))}) &nbsp;
    Thresholds: {badge(r["thresholds_ok"])} (breached: {r["thresholds_breached"]})
  </p>

  <h3>Auto findings</h3>
  <ul>{"".join(f"<li>{escape(x)}</li>" for x in findings)}</ul>

  <details>
    <summary>Details</summary>

    <h3>Top checks</h3>
    <table>
      <tr><th>Check</th><th>Pass</th><th>Fail</th></tr>
      {"".join(f"<tr><td class='mono'>{escape(c['path'] or c['name'])}</td><td>{c['passes']}</td><td>{c['fails']}</td></tr>" for c in checks_top)}
    </table>

    <h3>Thresholds</h3>
    <table>
      <tr><th>Metric</th><th>Expr</th><th>Status</th></tr>
      {"".join(f"<tr><td class='mono'>{escape(t['metric'])}</td><td class='mono'>{escape(t['expr'])}</td><td>{badge(not t['breached'])}</td></tr>" for t in thr)}
    </table>

    <div style="margin-top:10px">
      <div>Summary JSON: <span class="mono">{escape(r["summary_path"])}</span></div>
      <div>Env JSON: <span class="mono">{escape(r["env_path"])}</span></div>
    </div>
  </details>
</div>
""")

    html = f"""<!doctype html>
<meta charset="utf-8">
<title>Load testing suite report</title>
<style>
  body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial; margin:40px; color:#111}}
  h1{{margin-bottom:6px}}
  .muted{{color:#666}}
  .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}}
  .grid{{display:grid; grid-template-columns: 1fr 1fr; gap:16px;}}
  .card{{border:1px solid #e5e7eb; border-radius:14px; padding:16px; margin-top:16px}}
  table{{border-collapse:collapse; width:100%}}
  th,td{{border:1px solid #e5e7eb; padding:8px; text-align:left}}
  th{{background:#f9fafb}}
</style>

<h1>Load testing suite report — {now}</h1>
<div class="muted">Environment (from latest run)</div>

<ul>
  <li>OS: {escape(env_any.get('os',{}).get('name','') if env_any else '')} {escape(env_any.get('os',{}).get('version','') if env_any else '')}</li>
  <li>.NET: {escape(env_any.get('dotnet_version','') if env_any else '')}</li>
  <li>Base URL: <span class="mono">{escape(env_any.get('base_url','') if env_any else '')}</span></li>
  <li>Engine: {escape(env_any.get('engine','') if env_any else '')}</li>
  <li>DB container: <span class="mono">{escape(env_any.get('db_container','') if env_any else '')}</span></li>
  <li>Git: <span class="mono">{escape(env_any.get('git','') if env_any else '')}</span></li>
</ul>

<div class="card">
  <h2 style="margin-top:0">Scenario summary</h2>
  <table>
    <tr>
      <th>Scenario</th><th>Timestamp</th><th>Mode</th><th>VUs</th><th>Duration</th>
      <th>RPS</th><th>avg ms</th><th>p95 ms</th><th>http err</th><th>checks pass</th><th>thresholds</th>
    </tr>
    {''.join(tr(r) for r in rows)}
  </table>
</div>

{''.join(cards)}
"""
    html_path.write_text(html, encoding="utf-8")

    print("Generated:")
    print(" -", md_path)
    print(" -", html_path)

if __name__ == "__main__":
    main()