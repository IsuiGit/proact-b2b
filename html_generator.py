#!/usr/bin/env python3
"""HTML report generator for /pipeline --smart --file.

Reads 5 markdown stage files, converts to a single styled HTML page,
saves to Deliverables/reports/report_YYYY-MM-DD.html.
"""
import os
import re
import html
from datetime import datetime, timezone

_DELIVERABLES = os.path.dirname(os.path.abspath(__file__))
_OUTPUT = os.path.join(_DELIVERABLES, "pipeline_output")
_REPORTS = os.path.join(_DELIVERABLES, "reports")

_STAGES = [
    ("SCOUT", "scout.md"),
    ("ANALYST", "analyst.md"),
    ("WARMUP", "warmup.md"),
    ("BRIEF", "brief.md"),
    ("TRACKER", "tracker.md"),
]

_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  background:#0d0b12;color:#e8e4ef;line-height:1.6;padding:0}
.container{max-width:1100px;margin:0 auto;padding:24px 20px 60px}
h1{font-size:2em;color:#c93545;margin-bottom:8px}
.meta{color:#8a8499;font-size:0.9em;margin-bottom:24px}
nav{position:sticky;top:0;z-index:10;background:rgba(13,11,18,0.92);
  backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,0.06);
  padding:12px 0;margin:0 -20px 24px;padding-left:20px;padding-right:20px}
nav a{color:#c93545;text-decoration:none;margin-right:18px;font-size:0.9em;
  font-weight:600;transition:color 0.2s}
nav a:hover{color:#e85d6f}
.section{margin-bottom:40px;scroll-margin-top:70px}
.section h2{font-size:1.5em;color:#c93545;margin-bottom:16px;
  padding-bottom:8px;border-bottom:1px solid rgba(255,255,255,0.06)}
.section h3{font-size:1.2em;color:#e85d6f;margin:20px 0 10px}
.section p{margin:8px 0}
table{border-collapse:collapse;width:100%;margin:16px 0;font-size:0.88em;
  overflow-x:auto;display:block}
th{background:rgba(201,53,69,0.12);color:#e85d6f;font-weight:600;
  text-align:left;padding:10px 12px;border-bottom:2px solid rgba(201,53,69,0.2)}
td{padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.04);
  vertical-align:top}
tr:hover td{background:rgba(255,255,255,0.02)}
strong{color:#e8e4ef;font-weight:600}
em{color:#8a8499;font-style:italic}
hr{border:none;border-top:1px solid rgba(255,255,255,0.06);margin:24px 0}
code{background:rgba(255,255,255,0.06);padding:2px 6px;border-radius:4px;
  font-size:0.88em;color:#e85d6f}
blockquote{border-left:3px solid #c93545;padding-left:16px;margin:12px 0;
  color:#8a8499}
.footer{text-align:center;color:#4a4458;font-size:0.8em;margin-top:40px}
"""


def _inline(text):
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


def _md_to_html(text):
    lines = text.split("\n")
    result = []
    i = 0
    table_rows = []

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        html_rows = []
        for idx, row in enumerate(table_rows):
            cells = [c.strip() for c in row.split("|")[1:-1]]
            if idx == 1 and all(set(c) <= set("-: ") for c in cells):
                continue
            tag = "th" if idx == 0 else "td"
            cell_html = "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells)
            html_rows.append(f"<tr>{cell_html}</tr>")
        if html_rows:
            result.append("<table>" + "".join(html_rows) + "</table>")
        table_rows = []

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("|") and line.strip().endswith("|"):
            table_rows.append(line.strip())
            i += 1
            continue
        if table_rows:
            flush_table()
        s = line.strip()
        if not s:
            result.append("")
            i += 1
            continue
        if s.startswith("#### "):
            result.append(f"<h4>{_inline(s[5:])}</h4>")
        elif s.startswith("### "):
            result.append(f"<h3>{_inline(s[4:])}</h3>")
        elif s.startswith("## "):
            result.append(f"<h2>{_inline(s[3:])}</h2>")
        elif s.startswith("# "):
            result.append(f"<h2>{_inline(s[2:])}</h2>")
        elif s == "---":
            result.append("<hr>")
        elif s.startswith("> "):
            result.append(f"<blockquote>{_inline(s[2:])}</blockquote>")
        elif s.startswith("- ") or s.startswith("* "):
            items = []
            while i < len(lines) and (lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")):
                items.append(f"<li>{_inline(lines[i].strip()[2:])}</li>")
                i += 1
            result.append("<ul>" + "".join(items) + "</ul>")
            continue
        else:
            result.append(f"<p>{_inline(s)}</p>")
        i += 1
    if table_rows:
        flush_table()
    return "\n".join(result)


def generate_report(output_dir=None):
    src = output_dir or _OUTPUT
    os.makedirs(_REPORTS, exist_ok=True)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M UTC")
    nav_parts = []
    section_parts = []
    for stage_name, filename in _STAGES:
        fp = os.path.join(src, filename)
        if not os.path.exists(fp):
            continue
        with open(fp, "r", encoding="utf-8") as f:
            md = f.read()
        if not md.strip():
            continue
        body = _md_to_html(md)
        nav_parts.append(f'<a href="#{stage_name}">{stage_name}</a>')
        section_parts.append(f'<div class="section" id="{stage_name}">{body}</div>')
    nav_html = '<nav>' + " ".join(nav_parts) + "</nav>"
    sections_html = "\n".join(section_parts)
    full = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pipeline Report — {date_str}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="container">
<h1>B2B Pipeline Report</h1>
<div class="meta">Сгенерировано: {date_str} {time_str}</div>
{nav_html}
{sections_html}
<div class="footer">Ouroboros /pipeline --smart — {date_str}</div>
</div>
</body>
</html>"""
    fn = f"report_{date_str}.html"
    fpath = os.path.join(_REPORTS, fn)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(full)
    return fpath


if __name__ == "__main__":
    p = generate_report()
    print(f"HTML_REPORT_READY:{p}")
