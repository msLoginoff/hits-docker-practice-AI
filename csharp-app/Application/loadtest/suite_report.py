#!/usr/bin/env python3
import argparse, json, pathlib, re
from datetime import datetime

def latest_pair(folder: pathlib.Path):
    # ищем самый новый summary_*.json
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

def pick(metrics, name, field):
    obj = metrics.get(name, {})
    return obj.get(field, None)

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

        metrics = summary.get("metrics", {})
        rps = pick(metrics, "http_reqs", "rate") or 0
        p95 = pick(metrics, "http_req_duration", "p(95)") or 0
        avg = pick(metrics, "http_req_duration", "avg") or 0
        err = pick(metrics, "http_req_failed", "value") or 0

        rows.append((scenario, ts, rps, avg, p95, err))

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = out_dir / f"suite_report_{now}.md"
    html_path = out_dir / f"suite_report_{now}.html"

    # markdown
    md = []
    md.append(f"# Load testing suite report — {now}\n")
    if env_any:
        md.append("## Environment (from latest run)\n")
        md.append(f"- OS: {env_any['os']['name']} {env_any['os']['version']}")
        md.append(f"- .NET: {env_any['dotnet_version']}")
        md.append(f"- Base URL: {env_any['base_url']}")
        md.append(f"- Engine: {env_any['engine']}")
        md.append(f"- DB container: {env_any.get('db_container','')}\n")

    md.append("## Scenario summary\n")
    md.append("| Scenario | Timestamp | RPS | avg ms | p95 ms | error rate |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for s, ts, rps, avg, p95, err in rows:
        md.append(f"| {s} | {ts} | {rps:.2f} | {avg:.2f} | {p95:.2f} | {err*100:.2f}% |")
    md.append("")
    md_path.write_text("\n".join(md), encoding="utf-8")

    # html (простая табличка)
    tr = "\n".join(
        f"<tr><td>{s}</td><td>{ts}</td><td>{rps:.2f}</td><td>{avg:.2f}</td><td>{p95:.2f}</td><td>{err*100:.2f}%</td></tr>"
        for s, ts, rps, avg, p95, err in rows
    )
    html = f"""<!doctype html><meta charset="utf-8">
    <style>body{{font-family:system-ui; margin:40px}}
    table{{border-collapse:collapse}} td,th{{border:1px solid #ddd; padding:8px}}</style>
    <h1>Load testing suite report — {now}</h1>
    <table>
      <thead><tr><th>Scenario</th><th>Timestamp</th><th>RPS</th><th>avg ms</th><th>p95 ms</th><th>error rate</th></tr></thead>
      <tbody>{tr}</tbody>
    </table>
    """
    html_path.write_text(html, encoding="utf-8")

    print("Generated:")
    print(" -", md_path)
    print(" -", html_path)

if __name__ == "__main__":
    main()