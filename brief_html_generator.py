#!/usr/bin/env python3
"""Per-company HTML brief generator.

Takes a JSON file with structured company brief data,
renders a styled HTML page matching the PROACT brief template.

Usage:
    python3 brief_html_generator.py brief_data.json
    python3 brief_html_generator.py --dir reports/briefs/  # process all JSONs in dir
"""
import json
import os
import sys
import html
from datetime import datetime, timezone

_DELIVERABLES = os.path.dirname(os.path.abspath(__file__))
_REPORTS = os.path.join(_DELIVERABLES, "reports")
_BRIEFS_DIR = os.path.join(_REPORTS, "briefs")

_CSS = """
:root{--bg:#0d1117;--bg2:#161b22;--bg3:#1c2330;--border:rgba(255,255,255,0.07);
--border2:rgba(255,255,255,0.12);--text:#e6edf3;--text2:#8b949e;--text3:#6e7681;
--blue:#58a6ff;--blue-dim:rgba(88,166,255,0.10);--blue-border:rgba(88,166,255,0.22);
--green:#3fb950;--green-dim:rgba(63,185,80,0.08);--green-border:rgba(63,185,80,0.22);
--yellow:#d29922;--yellow-dim:rgba(210,153,34,0.09);--yellow-border:rgba(210,153,34,0.22);
--orange:#f0883e;--purple:#bc8cff;--teal:#39d3c3;--red:#f85149}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);
color:var(--text);font-size:13px;line-height:1.55}
.topbar{background:var(--bg2);border-bottom:1px solid var(--border);padding:9px 28px;
display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;gap:12px}
.logo{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;color:var(--blue);
background:var(--blue-dim);border:1px solid var(--blue-border);padding:2px 9px;border-radius:4px;letter-spacing:0.05em}
.topbar-left{display:flex;align-items:center;gap:10px}
.topbar-right{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.crumb{font-size:12px;color:var(--text3)}.crumb span{color:var(--text2)}
.badge{font-size:11px;font-weight:600;padding:2px 9px;border-radius:20px}
.badge-green{background:var(--green-dim);border:1px solid var(--green-border);color:var(--green)}
.badge-blue{background:var(--blue-dim);border:1px solid var(--blue-border);color:var(--blue)}
.badge-red{background:rgba(248,81,73,0.10);border:1px solid rgba(248,81,73,0.25);color:var(--red)}
.badge-yellow{background:rgba(210,153,34,0.12);border:1px solid rgba(210,153,34,0.30);color:#d29922}
.ts{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text3)}
.page{max-width:900px;margin:0 auto;padding:22px 28px 52px}
.hero{background:linear-gradient(135deg,#0d1f3c 0%,#1a0d2e 100%);border:1px solid var(--border2);
border-radius:10px;padding:18px 22px 16px;margin-bottom:14px}
.hero-top{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:12px}
.hero-name{font-size:20px;font-weight:700}
.hero-sub{font-size:12px;color:var(--text2);margin-top:3px}
.hero-sub span{color:var(--text3);margin:0 4px}
.score-pill{display:flex;align-items:center;gap:8px;background:var(--bg2);
border:1px solid var(--green-border);border-radius:7px;padding:5px 12px 5px 6px;flex-shrink:0}
.score-val{font-size:18px;font-weight:700;color:var(--green);font-family:'JetBrains Mono',monospace;line-height:1}
.score-lbl{font-size:10px;color:var(--text3)}
.chips{display:flex;flex-wrap:wrap;gap:7px}
.chip{font-size:11.5px;color:var(--text2);background:rgba(255,255,255,0.03);
border:1px solid var(--border);border-radius:5px;padding:3px 9px;display:flex;align-items:center;gap:5px}
.chip .dot{width:5px;height:5px;border-radius:50%;flex-shrink:0}
.chip strong{color:var(--text);font-weight:500}
.entry-banner{background:linear-gradient(135deg,rgba(88,166,255,0.07) 0%,transparent 100%);
border:1px solid var(--blue-border);border-left:3px solid var(--blue);border-radius:9px;
padding:11px 16px;margin-bottom:14px;font-size:12.5px}
.entry-banner-title{font-weight:700;color:var(--blue);margin-bottom:4px;font-size:13px}
.trigger{background:linear-gradient(135deg,rgba(63,185,80,0.06) 0%,transparent 100%);
border:1px solid var(--green-border);border-left:3px solid var(--green);border-radius:9px;
padding:13px 18px;margin-bottom:14px;display:flex;align-items:flex-start;gap:14px}
.trig-icon{font-size:22px;flex-shrink:0;margin-top:1px}
.trig-title{font-size:14px;font-weight:600;color:var(--text);margin-bottom:4px}
.trig-desc{font-size:12.5px;color:var(--text2);line-height:1.5}
.trig-src{font-size:11px;color:var(--text3);margin-top:6px;font-family:'JetBrains Mono',monospace}
.trig-score{text-align:center;flex-shrink:0}
.trig-score-val{font-size:22px;font-weight:700;color:var(--green);font-family:'JetBrains Mono',monospace;line-height:1}
.trig-score-lbl{font-size:10px;color:var(--text3);white-space:nowrap}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:9px;overflow:hidden}
.ch{font-size:11.5px;font-weight:600;letter-spacing:0.04em;padding:9px 14px 8px;
border-bottom:1px solid var(--border);text-transform:uppercase}
.cb{padding:12px 14px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.person{display:flex;gap:11px;padding:8px 0;border-bottom:1px solid var(--border)}
.person:last-child{border-bottom:none;padding-bottom:0}
.av{width:34px;height:34px;border-radius:8px;flex-shrink:0;background:linear-gradient(135deg,#1f6feb,#388bfd);
display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff}
.p-name{font-size:13px;font-weight:600}.p-role{font-size:11px;color:var(--text2);margin-top:1px}
.p-note{font-size:11.5px;color:var(--text3);margin-top:3px}
.tl{display:flex;flex-direction:column}
.tli{display:grid;grid-template-columns:68px 10px 1fr;align-items:start;padding:5px 0;gap:8px}
.tld{font-size:11px;color:var(--text3);font-family:'JetBrains Mono',monospace;padding-top:1px}
.tldot{width:8px;height:8px;border-radius:50%;margin-top:4px}
.tlt{font-size:12.5px;color:var(--text2)}.tlt strong{color:var(--text)}
.tl-tag{font-size:10px;font-weight:600;background:var(--green-dim);border:1px solid var(--green-border);
color:var(--green);padding:1px 6px;border-radius:3px;margin-left:6px;vertical-align:middle}
.rr{display:flex;align-items:center;justify-content:space-between;padding:5px 0;
border-bottom:1px solid var(--border);font-size:12px}
.rr:last-child{border-bottom:none}.rr-l{color:var(--text2)}
.ok{color:var(--green);font-weight:600}.warn{color:var(--yellow);font-weight:600}.bad{color:var(--red);font-weight:600}
.ft{width:100%;border-collapse:collapse;font-size:12.5px}
.ft th{color:var(--text3);font-weight:500;text-align:right;padding:4px 8px;border-bottom:1px solid var(--border)}
.ft th:first-child{text-align:left}
.ft td{padding:5px 8px;border-bottom:1px solid var(--border);text-align:right;color:var(--text2)}
.ft td:first-child{text-align:left;color:var(--text)}
.ft tr:last-child td{border-bottom:none}
.up{color:var(--green)}.dn{color:var(--red)}.nu{color:var(--text2)}
.note-box{margin-top:10px;background:var(--blue-dim);border:1px solid var(--blue-border);
border-radius:6px;padding:8px 12px;font-size:12px;color:var(--text2)}
.sdiv{font-size:11px;font-weight:700;letter-spacing:0.08em;color:var(--text3);
text-transform:uppercase;margin:18px 0 9px}
.prop{padding:12px 14px;border-bottom:1px solid var(--border)}
.prop:last-child{border-bottom:none}
.prop-1{background:rgba(63,185,80,0.03)}.prop-2{background:rgba(88,166,255,0.03)}.prop-3{background:rgba(210,153,34,0.03)}
.prop-h{display:flex;align-items:center;gap:8px;margin-bottom:7px}
.prop-medal{font-size:16px}.prop-title{font-size:13px;font-weight:600;color:var(--text)}
.prop-items{list-style:none;padding:0;display:flex;flex-direction:column;gap:4px}
.prop-items li{font-size:12.5px;color:var(--text2);padding-left:14px;position:relative}
.prop-items li::before{content:'·';position:absolute;left:4px;color:var(--text3)}
.prop-why{font-size:11.5px;color:var(--teal);margin-top:7px}
.gi{display:flex;gap:11px;padding:9px 0;border-bottom:1px solid var(--border);align-items:flex-start}
.gi:last-child{border-bottom:none}.gi-icon{font-size:20px;flex-shrink:0}
.gi-company{font-size:13px;font-weight:600}.gi-rel{font-size:12px;color:var(--text2);margin-top:2px}
.gi-tip{font-size:11.5px;color:var(--teal);margin-top:4px}
.sched{width:100%;border-collapse:collapse;font-size:12px}
.sched th{color:var(--text3);font-weight:500;padding:4px 8px;border-bottom:1px solid var(--border);text-align:left}
.sched td{padding:5px 8px;border-bottom:1px solid var(--border);color:var(--text2)}
.sched tr:last-child td{border-bottom:none}
.s-time{font-family:'JetBrains Mono',monospace;color:var(--text3)!important;white-space:nowrap}
.s-block{color:var(--text)!important;font-weight:500}.s-desc{color:var(--text2)!important}
.ql{list-style:none;padding:0;display:flex;flex-direction:column;gap:8px}
.ql li{display:flex;gap:9px;font-size:12.5px;color:var(--text2)}
.qn{flex-shrink:0;font-family:'JetBrains Mono',monospace;font-size:10.5px;font-weight:600;
color:var(--blue);background:var(--blue-dim);border:1px solid var(--blue-border);
padding:1px 5px;border-radius:3px;height:fit-content;margin-top:1px}
.obj{width:100%;border-collapse:collapse;font-size:12px}
.obj th{color:var(--text3);font-weight:500;padding:4px 8px;border-bottom:1px solid var(--border);text-align:left}
.obj td{padding:6px 8px;border-bottom:1px solid var(--border);vertical-align:top}
.obj tr:last-child td{border-bottom:none}
.obj-q{color:var(--yellow)!important;font-style:italic;width:42%}.obj-a{color:var(--text2)!important}
.cl{list-style:none;padding:0;display:flex;flex-direction:column;gap:8px}
.cl li{display:flex;gap:9px;font-size:12.5px;color:var(--text2);align-items:flex-start}
.cb-box{flex-shrink:0;width:14px;height:14px;border:1px solid var(--border2);border-radius:3px;margin-top:1px}
.wh{display:flex;flex-direction:column;gap:0}
.whi{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--border);align-items:flex-start}
.whi:last-child{border-bottom:none}
.wh-date{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text3);white-space:nowrap;padding-top:1px;min-width:70px}
.wh-type{font-size:11px;font-weight:600;padding:1px 7px;border-radius:3px;white-space:nowrap}
.wh-email{background:var(--blue-dim);border:1px solid var(--blue-border);color:var(--blue)}
.wh-call{background:var(--green-dim);border:1px solid var(--green-border);color:var(--green)}
.wh-noans{background:rgba(255,255,255,0.04);border:1px solid var(--border2);color:var(--text3)}
.wh-text{font-size:12px;color:var(--text2)}.wh-text strong{color:var(--text)}
.sfooter{margin-top:24px;padding:10px 14px;border:1px solid var(--border);border-radius:7px;
background:var(--bg2);display:flex;align-items:center;justify-content:space-between;gap:16px;font-size:11px;color:var(--text3)}
.sf-r{font-family:'JetBrains Mono',monospace;flex-shrink:0}
@media(max-width:640px){.g2{grid-template-columns:1fr}.hero-top{flex-direction:column}}
"""


def _esc(text: str) -> str:
    return html.escape(str(text)) if text else ""


def _render_chips(chips: list) -> str:
    if not chips:
        return ""
    parts = []
    for c in chips:
        color = c.get("color", "#3fb950")
        label = _esc(c.get("label", ""))
        value = _esc(c.get("value", ""))
        parts.append(
            f'<div class="chip"><span class="dot" style="background:{_esc(color)};"></span>'
            f"{label}: <strong>{value}</strong></div>"
        )
    return '<div class="chips">' + "".join(parts) + "</div>"


def _render_persons(persons: list) -> str:
    if not persons:
        return '<div class="cb"><p style="color:var(--text3);">Данные о контактах будут добавлены</p></div>'
    parts = []
    for p in persons:
        initials = _esc(p.get("initials", "??"))
        bg = p.get("avatar_bg", "linear-gradient(135deg,#1f6feb,#388bfd)")
        name = _esc(p.get("name", ""))
        role = _esc(p.get("role", ""))
        note = _esc(p.get("note", ""))
        confirmed = p.get("confirmed", False)
        ok_html = '<div class="p-ok">✓ Подтверждена</div>' if confirmed else ""
        parts.append(
            f'<div class="person"><div class="av" style="background:{_esc(bg)};">{initials}</div>'
            f'<div><div class="p-name">{name}</div><div class="p-role">{role}</div>'
            f'<div class="p-note">{note}</div>{ok_html}</div></div>'
        )
    return '<div class="cb">' + "".join(parts) + "</div>"


def _render_events(events: list) -> str:
    if not events:
        return ""
    parts = []
    for e in events:
        date = _esc(e.get("date", ""))
        color = e.get("color", "#58a6ff")
        text = e.get("text", "")
        tag = e.get("tag", "")
        tag_html = f'<span class="tl-tag">{_esc(tag)}</span>' if tag else ""
        parts.append(
            f'<div class="tli"><div class="tld">{date}</div>'
            f'<div class="tldot" style="background:{_esc(color)};"></div>'
            f'<div class="tlt">{text}{tag_html}</div></div>'
        )
    return '<div class="tl">' + "".join(parts) + "</div>"


def _render_risks(risks: list) -> str:
    if not risks:
        return ""
    parts = []
    for r in risks:
        label = _esc(r.get("label", ""))
        status = r.get("status", "ok")
        value = _esc(r.get("value", ""))
        cls = {"ok": "ok", "warn": "warn", "bad": "bad"}.get(status, "ok")
        icon = {"ok": "✓", "warn": "⚠", "bad": "✗"}.get(status, "✓")
        parts.append(
            f'<div class="rr"><span class="rr-l">{label}</span>'
            f'<span class="{cls}">{icon} {value}</span></div>'
        )
    return "".join(parts)


def _render_financials(fin: dict) -> str:
    if not fin or not fin.get("rows"):
        return ""
    rows_html = ""
    for row in fin.get("rows", []):
        label = _esc(row.get("label", ""))
        v1 = _esc(row.get("v1", ""))
        v2 = _esc(row.get("v2", ""))
        delta = row.get("delta", "")
        delta_cls = "nu"
        if delta.startswith("+"):
            delta_cls = "up"
        elif delta.startswith("-") or delta.startswith("↓"):
            delta_cls = "dn"
        warn_cls = " warn-row" if row.get("warn") else ""
        rows_html += (
            f'<tr class="{warn_cls}"><td>{label}</td><td>{v1}</td><td>{v2}</td>'
            f'<td><span class="{delta_cls}">{_esc(delta)}</span></td></tr>'
        )
    insight = fin.get("insight", "")
    insight_html = ""
    if insight:
        insight_html = f'<div class="note-box"><strong>💡 Инсайт:</strong> {_esc(insight)}</div>'
    return f"""<div class="card" style="margin-bottom:12px;">
<div class="ch" style="color:#3fb950;">📊 Финансовый профиль</div>
<div class="cb" style="padding:10px 14px;">
<table class="ft"><thead><tr><th>Показатель</th><th>2024</th><th>2025</th><th>Δ</th></tr></thead>
<tbody>{rows_html}</tbody></table>{insight_html}</div></div>"""


def _render_warmup(history: list) -> str:
    if not history:
        return ""
    parts = []
    for h in history:
        date = _esc(h.get("date", ""))
        htype = h.get("type", "email")
        text = h.get("text", "")
        cls = {"email": "wh-email", "call": "wh-call", "noans": "wh-noans"}.get(htype, "wh-email")
        label = {"email": "Email", "call": "Звонок", "noans": "Без ответа"}.get(htype, "Email")
        parts.append(
            f'<div class="whi"><div class="wh-date">{date}</div>'
            f'<span class="wh-type {cls}">{label}</span>'
            f'<div class="wh-text">{text}</div></div>'
        )
    return f"""<div class="card" style="margin-bottom:12px;">
<div class="ch" style="color:#bc8cff;">📨 История касаний</div><div class="cb">
<div class="wh">{"".join(parts)}</div></div></div>"""


def _render_products(products: list) -> str:
    if not products:
        return ""
    parts = []
    for i, p in enumerate(products):
        medal = p.get("medal", ["🥇", "🥈", "🥉"][min(i, 2)])
        title = _esc(p.get("title", ""))
        items = p.get("items", [])
        items_html = "".join(f"<li>{_esc(it)}</li>" for it in items)
        why = p.get("why", "")
        why_html = f'<div class="prop-why">{_esc(why)}</div>' if why else ""
        badge = p.get("badge", "")
        badge_html = f'<span class="badge badge-blue" style="margin-left:auto;font-size:10.5px;">{_esc(badge)}</span>' if badge else ""
        cls = f"prop-{min(i + 1, 3)}"
        parts.append(
            f'<div class="prop {cls}"><div class="prop-h"><div class="prop-medal">{medal}</div>'
            f'<div class="prop-title">{title}</div>{badge_html}</div>'
            f'<ul class="prop-items">{items_html}</ul>{why_html}</div>'
        )
    return f"""<div class="sdiv">💡 Продуктовое предложение</div>
<div class="card" style="margin-bottom:12px;"><div class="cb" style="padding:14px;">{"".join(parts)}</div></div>"""


def _render_connections(connections: list) -> str:
    if not connections:
        return ""
    parts = []
    for c in connections:
        icon = c.get("icon", "🔗")
        company = _esc(c.get("company", ""))
        relation = _esc(c.get("relation", ""))
        tip = c.get("tip", "")
        tip_html = f'<div class="gi-tip">💡 {_esc(tip)}</div>' if tip else ""
        parts.append(
            f'<div class="gi"><div class="gi-icon">{icon}</div><div>'
            f'<div class="gi-company">{company}</div><div class="gi-rel">{relation}</div>{tip_html}</div></div>'
        )
    return f"""<div class="card" style="margin-bottom:12px;">
<div class="ch" style="color:#39d3c3;">🕸 Связи с клиентами Сбера</div>
<div class="cb">{"".join(parts)}</div></div>"""


def _render_schedule(schedule: list) -> str:
    if not schedule:
        return ""
    rows = ""
    for s in schedule:
        time = _esc(s.get("time", ""))
        block = _esc(s.get("block", ""))
        focus = _esc(s.get("focus", ""))
        rows += f'<tr><td class="s-time">{time}</td><td class="s-block">{block}</td><td class="s-desc">{focus}</td></tr>'
    return f"""<div class="card"><div class="ch" style="color:#bc8cff;">🕐 Структура встречи</div>
<div class="cb" style="padding:10px 14px;"><table class="sched">
<thead><tr><th>Время</th><th>Блок</th><th>Фокус</th></tr></thead><tbody>{rows}</tbody></table></div></div>"""


def _render_questions(questions: list) -> str:
    if not questions:
        return ""
    parts = []
    for i, q in enumerate(questions):
        num = f"Q{i+1}"
        parts.append(f'<li><span class="qn">{num}</span>{_esc(q)}</li>')
    return f"""<div class="card"><div class="ch" style="color:#58a6ff;">❓ Рекомендуемые вопросы</div>
<div class="cb"><ul class="ql">{"".join(parts)}</ul></div></div>"""


def _render_objections(objections: list) -> str:
    if not objections:
        return ""
    rows = ""
    for o in objections:
        q = _esc(o.get("objection", ""))
        a = _esc(o.get("answer", ""))
        rows += f'<tr><td class="obj-q">{q}</td><td class="obj-a">{a}</td></tr>'
    return f"""<div class="card"><div class="ch" style="color:#d29922;">⚠️ Возражения и ответы</div>
<div class="cb" style="padding:10px 14px;"><table class="obj">
<thead><tr><th>Возражение</th><th>Контраргумент</th></tr></thead><tbody>{rows}</tbody></table></div></div>"""


def _render_checklist(checklist: list) -> str:
    if not checklist:
        return ""
    parts = [f'<li><div class="cb-box"></div>{_esc(item)}</li>' for item in checklist]
    return f"""<div class="card"><div class="ch" style="color:#3fb950;">📎 Рекомендации по проведению встречи</div>
<div class="cb"><ul class="cl">{"".join(parts)}</ul></div></div>"""


def render_brief(data: dict) -> str:
    """Render a company brief JSON dict into full HTML."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%d.%m.%Y · %H:%M")

    company_name = _esc(data.get("company_name", "Компания"))
    industry = _esc(data.get("industry", ""))
    inn = _esc(data.get("inn", ""))
    location = _esc(data.get("location", ""))
    score = data.get("score", 0)
    is_sber_client = data.get("is_sber_client", False)
    client_status = data.get("client_status", "non_client" if not is_sber_client else "client")
    website = data.get("website", "")
    phone = data.get("phone", "")
    years_on_market = data.get("years_on_market", "")
    personal_contacts = data.get("personal_contacts", "")

    # Score ring SVG
    circumference = 2 * 3.14159 * 13  # ~81.7
    dash = circumference * score / 100
    gap = circumference - dash
    score_color = "#3fb950" if score >= 70 else "#d29922" if score >= 50 else "#f85149"

    sub_parts = []
    if inn:
        sub_parts.append(f"ИНН {inn}")
    if industry:
        sub_parts.append(industry)
    if location:
        sub_parts.append(location)
    sub_html = " <span>·</span> ".join(_esc(s) for s in sub_parts)

    if client_status == "client":
        client_badge = '<span class="badge badge-green">✓ Клиент Сбера</span>'
    elif client_status == "partial_client":
        client_badge = '<span class="badge badge-yellow">🟡 Частично клиент Сбера</span>'
    else:
        client_badge = '<span class="badge badge-red">🔴 Не клиент Сбера</span>'

    # Client info card (website, phone, years on market)
    info_parts = []
    if website:
        info_parts.append(f'<div style="display:flex;align-items:center;gap:6px;color:var(--text2);font-size:13px;">🌐 <a href="{_esc(website)}" target="_blank" style="color:#58a6ff;text-decoration:none;">{_esc(website)}</a></div>')
    if phone:
        info_parts.append(f'<div style="display:flex;align-items:center;gap:6px;color:var(--text2);font-size:13px;">📞 {_esc(phone)}</div>')
    if years_on_market:
        info_parts.append(f'<div style="display:flex;align-items:center;gap:6px;color:var(--text2);font-size:13px;">🏢 На рынке: {_esc(years_on_market)}</div>')
    if personal_contacts:
        info_parts.append(f'<div style="display:flex;align-items:center;gap:6px;color:var(--text2);font-size:13px;">👤 {_esc(personal_contacts)}</div>')
    client_info_html = '<div style="display:flex;flex-direction:column;gap:4px;margin-top:8px;">' + "".join(info_parts) + '</div>' if info_parts else ""

    # Entry point
    entry = data.get("entry_point", {})
    entry_html = ""
    if entry.get("text"):
        entry_html = f"""<div class="entry-banner">
<div class="entry-banner-title">{_esc(entry.get("title", "🔗 Точка входа"))}</div>
<div style="color:var(--text2);">{entry.get("text", "")}</div></div>"""

    # Trigger
    trigger = data.get("trigger", {})
    trigger_html = ""
    if trigger.get("title"):
        trigger_html = f"""<div class="trigger">
<div class="trig-icon">{trigger.get("icon", "⚡")}</div>
<div style="flex:1;"><div class="trig-title">{_esc(trigger.get("title", ""))}</div>
<div class="trig-desc">{trigger.get("description", "")}</div>
<div class="trig-src">{_esc(trigger.get("source", ""))}</div></div>
<div class="trig-score"><div class="trig-score-val" style="color:{score_color};">{score}</div>
<div class="trig-score-lbl">скоринг лида</div></div></div>"""

    # Grid: contacts + events/risks
    contacts = data.get("contacts", [])
    events = data.get("events", [])
    risks = data.get("risks", [])

    events_html = _render_events(events)
    risks_html = _render_risks(risks)

    right_col = f"""<div style="display:flex;flex-direction:column;gap:12px;">
<div class="card" style="flex:1;"><div class="ch" style="color:#d29922;">📰 События</div>
<div class="cb">{events_html}</div></div>
<div class="card"><div class="ch" style="color:#f85149;">🛡 Риск-индикаторы</div>
<div class="cb">{risks_html}</div></div></div>"""

    left_col = f"""<div class="card"><div class="ch" style="color:#58a6ff;">👥 Ключевые контакты</div>
{_render_persons(contacts)}</div>"""

    grid1 = f'<div class="g2">{left_col}{right_col}</div>' if (contacts or events or risks) else ""

    # Financials
    fin_html = _render_financials(data.get("financials", {}))

    # Warmup history
    warmup_html = _render_warmup(data.get("warmup_history", []))

    # Touchpoint history stub (future EFS/OneKIB integration)
    touch_history = data.get("touchpoint_history", {})
    touch_html = ""
    if touch_history.get("items"):
        touch_items = "".join(
            f'<div style="display:flex;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
            f'<span style="color:var(--text2);font-size:12px;min-width:60px;">{_esc(it.get("date",""))}</span>'
            f'<span style="color:var(--text2);font-size:13px;">{_esc(it.get("text",""))}</span></div>'
            for it in touch_history.get("items", [])
        )
        touch_html = f"""<div class="card"><div class="ch" style="color:#bc8cff;">📋 История касаний (ЕФС/OneKIB)</div>
<div class="cb">{touch_items}</div></div>"""
    elif touch_history.get("placeholder"):
        touch_html = f"""<div class="card"><div class="ch" style="color:#bc8cff;">📋 История касаний (ЕФС/OneKIB)</div>
<div class="cb"><div style="color:var(--text2);font-size:13px;padding:8px 0;">⏳ {_esc(touch_history["placeholder"])}</div></div></div>"""

    # Products
    products_html = _render_products(data.get("products", []))

    # Connections
    connections_html = _render_connections(data.get("connections", []))

    # Schedule + Questions
    schedule_html = _render_schedule(data.get("schedule", []))
    questions_html = _render_questions(data.get("questions", []))
    grid2 = f'<div class="g2">{schedule_html}{questions_html}</div>' if (schedule_html or questions_html) else ""

    # Objections + Checklist
    objections_html = _render_objections(data.get("objections", []))
    checklist_html = _render_checklist(data.get("checklist", []))
    grid3 = f'<div class="g2" style="margin-top:12px;">{objections_html}{checklist_html}</div>' if (objections_html or checklist_html) else ""

    # Chips
    chips_html = _render_chips(data.get("chips", []))

    full_html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>PROACT · Бриф встречи · {company_name}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>{_CSS}</style></head><body>
<div class="topbar"><div class="topbar-left">
<span class="logo">PROACT</span>
<div class="crumb">Агент BRIEF <span>·</span> <span>Бриф встречи</span></div>
</div><div class="topbar-right">
<span class="badge badge-green">✓ Готов к использованию</span>
<span class="ts">{date_str}</span></div></div>
<div class="page">
<div class="hero"><div class="hero-top"><div>
<div class="hero-name">{company_name}</div>
<div class="hero-sub">{sub_html}</div></div>
<div style="display:flex;align-items:center;gap:8px;">
<div class="score-pill"><svg width="32" height="32" viewBox="0 0 32 32">
<circle cx="16" cy="16" r="13" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="2.5"/>
<circle cx="16" cy="16" r="13" fill="none" stroke="{score_color}" stroke-width="2.5"
stroke-dasharray="{dash:.1f} {gap:.1f}" stroke-dashoffset="20.4" stroke-linecap="round"
transform="rotate(-90 16 16)"/></svg>
<div><div class="score-val" style="color:{score_color};">{score}</div>
<div class="score-lbl">/ 100</div></div></div>
{client_badge}</div></div>{chips_html}
{client_info_html}</div>
{entry_html}{trigger_html}{grid1}{fin_html}{warmup_html}{touch_html}{products_html}{connections_html}{grid2}{grid3}
<div class="sfooter"><div class="sf-l">
<strong>🤖 PROACT (Ouroboros)</strong> · /pipeline --smart · {now.strftime("%Y-%m-%d")}</div>
<div class="sf-r">SCOUT → ANALYST → WARMUP → BRIEF</div></div>
</div></body></html>"""
    return full_html


def generate_brief_html(json_path: str, output_dir: str = None) -> str:
    """Read a JSON file, render HTML, save to output_dir."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    out = output_dir or _BRIEFS_DIR
    os.makedirs(out, exist_ok=True)

    company_name = data.get("company_name", "unknown")
    # Sanitize filename
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in company_name)
    filename = f"{safe_name}.html"
    filepath = os.path.join(out, filename)

    html_content = render_brief(data)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    return filepath


def generate_all_briefs(briefs_json_dir: str, output_dir: str = None) -> list:
    """Process all JSON files in a directory."""
    results = []
    if not os.path.isdir(briefs_json_dir):
        return results
    for fname in sorted(os.listdir(briefs_json_dir)):
        if fname.endswith(".json"):
            json_path = os.path.join(briefs_json_dir, fname)
            try:
                path = generate_brief_html(json_path, output_dir)
                results.append(path)
            except Exception as e:
                results.append(f"ERROR: {fname}: {e}")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: brief_html_generator.py <json_file | --dir <directory>>")
        sys.exit(1)
    if sys.argv[1] == "--dir":
        d = sys.argv[2] if len(sys.argv) > 2 else os.path.join(_REPORTS, "briefs_json")
        paths = generate_all_briefs(d)
        print(f"BRIEF_HTML_GENERATED:{len(paths)}")
        for p in paths:
            print(f"  {p}")
    else:
        path = generate_brief_html(sys.argv[1])
        print(f"BRIEF_HTML_READY:{path}")
