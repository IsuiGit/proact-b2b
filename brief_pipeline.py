#!/usr/bin/env python3
"""BRIEF pipeline — одностраничное досье менеджера перед встречей.

Берёт компанию (по имени или ключевому слову), подтягивает её
профиль из ANALYST, события из SCOUT, и генерирует компактный бриф:
- досье (кто, где, сколько)
- риск-резюме
- что предлагать (продукты + аргументация)
- красные флаги
- suggested agenda для звонка

Usage:
    python3 brief_pipeline.py "ООО ВолгаТрейд"
    python3 brief_pipeline.py --company "ПАО МТС" --analyst-json profiles.json --scout-store store.json
    python3 brief_pipeline.py --list                    # показать все доступные компании
    python3 brief_pipeline.py --format json             # JSON-результат
"""
import argparse
import json
import os
import sys
from typing import Any

# ── Resolve paths ──────────────────────────────────────────────────────
_DELIVERABLES = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_DELIVERABLES)
_STORE_FILE = os.path.join(_REPO_ROOT, "data", "sberbank_pipeline", "pipeline_store.json")

# ── Constants ──────────────────────────────────────────────────────────
PRODUCT_RU = {
    "rko": "РКО",
    "lending": "Кредитование",
    "leasing": "Лизинг",
    "salary_project": "Зарплатный проект",
    "ved": "ВЭД / валютный контроль",
    "bank_guarantee": "Банковские гарантии",
    "acquiring": "Эквайринг",
}

RISK_ICONS = {
    "very_low": "✅",
    "low": "🟢",
    "moderate": "🟡",
    "neutral": "⚪",
    "high": "🟠",
    "very_high": "🔴",
}

STRATEGY_LABELS = {
    "warm_lead": "🔥 Тёплый — звонить немедленно",
    "nurture": "📋 Наблюдать — в дайджест",
    "approach_carefully": "⚠️ Осторожно — риски превышают потенциал",
    "avoid": "🚫 Избегать — контрагент опасен",
}


def _fmt_money(amount: float | None) -> str:
    """Human-readable rouble amount."""
    if amount is None or amount <= 0:
        return "—"
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.1f} млрд ₽"
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.0f} млн ₽"
    return f"{amount:,.0f} ₽"


def _company_matches(name: str, query: str) -> bool:
    """Fuzzy-ish match: query can be substring, partial legal form, etc."""
    if not name or not query:
        return False
    n = name.lower().strip()
    q = query.lower().strip()
    # Direct substring
    if q in n:
        return True
    # Strip legal form for matching
    for prefix in ["ооо ", "зао ", "оао ", "пао ", "ао ", "ип ", 'ооо "', 'зао "', 'пао "', 'оао "', 'ао "']:
        n_stripped = n.replace(prefix, "")
        if q in n_stripped or q.strip('"') in n_stripped:
            return True
    return False


def _load_profiles(path: str) -> list[dict]:
    """Load ANALYST profiles."""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("profiles", [])


def _load_scout_events(path: str) -> list[dict]:
    """Load SCOUT events from pipeline_store.json."""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("last_result", {}).get("events", [])


def _find_company(company_query: str, profiles: list[dict], scout_events: list[dict]) -> dict[str, Any] | None:
    """Find a company across profiles and scout events."""
    # Try profiles first
    for p in profiles:
        name = p.get("company_name", "")
        if _company_matches(name, company_query):
            return {
                "found_in": "analyst",
                "profile": p,
                "company_name": name,
            }

    # Fallback: find in scout events
    matched_events = [
        ev for ev in scout_events
        if _company_matches(ev.get("company_name", ""), company_query)
    ]
    if matched_events:
        first = matched_events[0]
        return {
            "found_in": "scout",
            "profile": None,
            "company_name": first.get("company_name", "Неизвестная"),
            "scout_events": matched_events,
        }

    return None


def _generate_event_summary(events: list[dict]) -> list[str]:
    """Create human-readable event summaries for the brief."""
    lines = []
    type_labels = {
        "new_procurement": "📝 Закупка",
        "capital_change": "💰 Изменение капитала",
        "new_registration": "🏢 Новая регистрация",
        "expansion": "📈 Расширение",
        "court_case": "⚖️ Судебное дело",
        "bankruptcy": "💔 Банкротство",
        "liquidation": "🚫 Ликвидация",
        "news_mention": "📰 Упоминание в СМИ",
        "new_company": "🆕 Новая компания",
    }
    for ev in events:
        etype = ev.get("event_type", "")
        label = type_labels.get(etype, etype)
        amount = ev.get("potential_revenue", ev.get("amount"))
        src = ev.get("source", ev.get("source_name", ""))
        line = f"• **{label}**" 
        if amount and float(amount or 0) > 0:
            line += f" — {_fmt_money(float(amount))}"
        if src:
            line += f" ({src})"
        lines.append(line)
    return lines


def _build_brief(result: dict[str, Any], fmt: str = "text") -> str:
    """Render the brief as Markdown or JSON."""
    name = result["company_name"]
    profile = result.get("profile")
    
    if fmt == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)

    lines = []
    lines.append(f"## 📋 BRIEF: {name}")
    lines.append("")

    # ── Source ──
    found_in = result.get("found_in", "unknown")
    lines.append(f"**Источник:** {'ANALYST профиль' if found_in == 'analyst' else 'SCOUT события'} (данных {'много' if profile else 'мало'})")
    lines.append("")

    # ── Risk Summary ──
    if profile:
        risk = profile.get("risk_profile", {})
        scenario = profile.get("entry_scenario", {})
        heatmap = profile.get("product_heatmap", [])
        overall = profile.get("overall_score", 0)

        level = risk.get("level", "neutral")
        icon = RISK_ICONS.get(level, "❓")
        label = risk.get("label", "—")
        strategy = scenario.get("approach", "nurture")
        strategy_text = STRATEGY_LABELS.get(strategy, strategy)

        lines.append("### Риск-резюме")
        lines.append("| Параметр | Значение |")
        lines.append("|---|---|")
        lines.append(f"| Риск | {icon} {label} |")
        lines.append(f"| Общий скор | {overall}/10 |")
        lines.append(f"| Стратегия | {strategy_text} |")
        lines.append("")

        # Revenue summary
        pos_rev = risk.get("positive_revenue", 0)
        neg_exp = risk.get("negative_exposure", 0)
        lines.append(f"- **Позитивный сигнал:** {_fmt_money(pos_rev)}")
        lines.append(f"- **Негативная экспозиция:** {_fmt_money(neg_exp)}")
        lines.append(f"- **Судебных дел:** {risk.get('court_count', 0)}")
        lines.append("")

        # Product recommendations
        if heatmap:
            lines.append("### Рекомендуемые продукты")
            lines.append("")
            lines.append("| # | Продукт | Уверенность | Потенциал |")
            lines.append("|---|---------|-------------|-----------|")
            for i, pr in enumerate(heatmap[:5], 1):
                prod_name = PRODUCT_RU.get(pr["product"], pr["product"])
                confidence = f"{pr['score']*100:.0f}%"
                rev = _fmt_money(pr.get("estimated_revenue"))
                lines.append(f"| {i} | {prod_name} | {confidence} | {rev} |")
            lines.append("")

        # Opener / agenda
        opener = scenario.get("opener")
        if opener:
            lines.append("### Ключевой аргумент")
            lines.append(f"> {opener}")
            lines.append("")

        # Red flags
        flags = risk.get("flags", [])
        if flags:
            lines.append("### 🚩 Красные флаги")
            for flag in flags:
                lines.append(f"- {flag}")
            lines.append("")

        # Agenda
        lines.append("### Рекомендуемая agenda для звонка")
        lines.append("1. **Представление** — менеджер Сбербанка, курирует отрасль")
        if strategy == "warm_lead":
            lines.append("2. **Инфоповод** — сослаться на конкретное событие (закупка/рост)")
            lines.append("3. **Предложение** — конкретный продукт с условиями")
        elif strategy == "nurture":
            lines.append("2. **Знакомство** — предложить обмен контактами на будущее")
            lines.append("3. **Информация** — отправить обзор услуг без давления")
        else:
            lines.append("2. **Осторожный зондаж** — не раскрывать что видим их риски")
            lines.append("3. **Общие условия** — только стандартные продукты")
        lines.append("4. **Follow-up** — назначить следующий шаг (звонок / встреча / email)")
        lines.append("")

    # ── SCOUT Events ──
    events = result.get("scout_events", [])
    if not events and profile:
        events = profile.get("_scout_events", [])
    if events:
        lines.append("### Инфоповоды по компании")
        lines.append("")
        for line in _generate_event_summary(events):
            lines.append(line)
        lines.append("")

    if not profile and not events:
        lines.append("⚠️ **Недостаточно данных** — компания найдена, но без аналитического профиля.")
        lines.append("")

    return "\n".join(lines)


def run_brief(
    company_query: str,
    analyst_path: str | None = None,
    scout_path: str | None = None,
    fmt: str = "text",
) -> str:
    """Main entry point: find company → build brief → return string."""
    # Default paths
    if analyst_path is None:
        analyst_path = os.path.join(_DELIVERABLES, "analyst_output.json")
        if not os.path.isfile(analyst_path):
            analyst_path = None  # Will try None downstream
    
    if scout_path is None:
        scout_path = _STORE_FILE

    profiles = _load_profiles(analyst_path) if analyst_path else []
    scout_events = _load_scout_events(scout_path)

    result = _find_company(company_query, profiles, scout_events)
    if not result:
        return f"[BRIEF] Компания '{company_query}' не найдена. Попробуйте `--list` для списка доступных."

    # Enrich with scout events
    if result.get("scout_events"):
        pass  # Already has scout events
    elif result.get("profile"):
        # Find scout events for this company
        name = result["company_name"]
        result["scout_events"] = [
            ev for ev in scout_events
            if _company_matches(ev.get("company_name", ""), name)
        ]

    return _build_brief(result, fmt=fmt)


def _list_companies(profiles: list[dict], scout_events: list[dict]) -> str:
    """List all discoverable companies."""
    seen: set[str] = set()
    companies: list[tuple[str, str]] = []

    for p in profiles:
        name = p.get("company_name", "")
        if name and name not in seen and name != "Неизвестная компания":
            seen.add(name)
            score = p.get("overall_score", 0)
            companies.append((name, f"score={score}"))

    for ev in scout_events:
        name = ev.get("company_name", "")
        if name and name not in seen and name != "Неизвестная компания":
            seen.add(name)
            companies.append((name, "scout only"))

    if not companies:
        return "[BRIEF] Нет данных о компаниях. Запустите SCOUT → ANALYST сначала."

    lines = ["## Доступные компании для briefing\n"]
    for i, (name, meta) in enumerate(companies, 1):
        lines.append(f"{i}. **{name}** ({meta})")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BRIEF: one-page dossier before client meetings")
    parser.add_argument("company", nargs="?", help="Company name or substring to search")
    parser.add_argument("--analyst-json", type=str, default=None, help="ANALYST output JSON file")
    parser.add_argument("--scout-store", type=str, default=None, help="SCOUT pipeline_store.json")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--list", action="store_true", help="List all available companies")
    args = parser.parse_args()

    scout_path = args.scout_store or _STORE_FILE
    profiles = _load_profiles(args.analyst_json) if args.analyst_json else []
    scout_events = _load_scout_events(scout_path)

    if args.list:
        print(_list_companies(profiles, scout_events))
    elif args.company:
        result = run_brief(
            company_query=args.company,
            analyst_path=args.analyst_json,
            scout_path=scout_path,
            fmt=args.format,
        )
        print(result)
    else:
        parser.print_help()
