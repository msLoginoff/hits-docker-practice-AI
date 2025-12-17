#!/usr/bin/env python3
import argparse, json, pathlib, statistics, datetime

def get_metric(metrics, name):
    return metrics.get(name, {})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", required=True)
    ap.add_argument("--env", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-html", required=True)
    args = ap.parse_args()

    summary = json.loads(pathlib.Path(args.summary).read_text(encoding="utf-8"))
    env = json.loads(pathlib.Path(args.env).read_text(encoding="utf-8"))

    metrics = summary.get("metrics", {})

    http_reqs = get_metric(metrics, "http_reqs")
    rps = http_reqs.get("rate", 0)

    dur = get_metric(metrics, "http_req_duration")
    p95 = dur.get("p(95)", None)
    avg = dur.get("avg", None)

    failed = get_metric(metrics, "http_req_failed")
    err_rate = failed.get("value", 0)  # 0..1

    # простые выводы
    advice = []
    if err_rate > 0.01:
        advice.append("❗ Высокий error rate: проверьте БД/таймауты/валидацию antiforgery.")
    else:
        advice.append("✅ Error rate в норме (почти/ровно 0%).")

    if p95 is not None and p95 > 800:
        advice.append("⚠️ p95 latency выше 800ms: стоит смотреть медленные запросы и SQL.")
    else:
        advice.append("✅ p95 latency выглядит хорошо для локального окружения.")

    if rps < 10:
        advice.append("ℹ️ RPS низкий — возможно, в сценарии есть think-time (sleep) или тяжёлые шаги (что нормально для e2e).")
    else:
        advice.append("✅ RPS достаточный для демонстрации нагрузки.")

    md = []
    md.append(f"# Load testing report — {env['scenario']} — {env['timestamp']}\n")
    md.append("## Environment\n")
    md.append(f"- OS: {env['os']['name']} {env['os']['version']}")
    md.append(f"- .NET: {env['dotnet_version']}")
    md.append(f"- Git SHA: {env['git_sha']}")
    md.append(f"- Base URL: {env['base_url']}")
    md.append(f"- Engine: {env['engine']}")
    md.append(f"- DB container: {env.get('db_container','')}\n")

    md.append("## Key metrics\n")
    md.append(f"- RPS (http_reqs.rate): **{rps:.2f} req/s**")
    md.append(f"- Latency avg: **{avg:.2f} ms**" if avg is not None else "- Latency avg: n/a")
    md.append(f"- Latency p95: **{p95:.2f} ms**" if p95 is not None else "- Latency p95: n/a")
    md.append(f"- Error rate (http_req_failed): **{err_rate*100:.2f}%**\n")

    md.append("## Automated interpretation\n")
    for a in advice:
        md.append(f"- {a}")
    md.append("")

    out_md = "\n".join(md)
    pathlib.Path(args.out_md).write_text(out_md, encoding="utf-8")

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Loadtest report</title>
<style>
body{{font-family:system-ui, -apple-system, Segoe UI, Roboto, Arial; margin:40px;}}
.card{{border:1px solid #ddd; border-radius:12px; padding:16px; margin:12px 0;}}
.k{{color:#555}}
.v{{font-size:20px}}
</style></head>
<body>
<h1>Load testing report — {env['scenario']} — {env['timestamp']}</h1>

<div class="card">
  <h2>Environment</h2>
  <div><span class="k">OS:</span> {env['os']['name']} {env['os']['version']}</div>
  <div><span class="k">.NET:</span> {env['dotnet_version']}</div>
  <div><span class="k">Git:</span> {env['git_sha']}</div>
  <div><span class="k">Base URL:</span> {env['base_url']}</div>
  <div><span class="k">Engine:</span> {env['engine']}</div>
  <div><span class="k">DB container:</span> {env.get('db_container','')}</div>
</div>

<div class="card">
  <h2>Key metrics</h2>
  <div class="v">RPS: {rps:.2f} req/s</div>
  <div class="v">Latency p95: {p95:.2f} ms</div>
  <div class="v">Error rate: {err_rate*100:.2f}%</div>
</div>

<div class="card">
  <h2>Interpretation</h2>
  <ul>
    {''.join(f'<li>{x}</li>' for x in advice)}
  </ul>
</div>

<p class="k">Source files: {pathlib.Path(args.summary).name}, {pathlib.Path(args.env).name}</p>
</body></html>
"""
    pathlib.Path(args.out_html).write_text(html, encoding="utf-8")

    print("Generated:")
    print(" -", args.out_md)
    print(" -", args.out_html)

if __name__ == "__main__":
    main()