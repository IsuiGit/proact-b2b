#!/usr/bin/env python3
"""FEEDBACK pipeline — обратная связь по результатам WARMUP.

After each pipeline run, record qualitative / quantitative feedback about
companies, letters, and products so the data can be used later for
re-training / tuning.

Usage:
    python3 feedback_pipeline.py --record --company "ООО Ромашка" --product lending --outcome "ответили, интерес есть" --rating 4
    python3 feedback_pipeline.py --record --company "ООО Ромашка" --product rko --outcome "не ответили" --rating 1
    python3 feedback_pipeline.py --list                          # show all feedback
    python3 feedback_pipeline.py --list --company "ООО Ромашка   # filter by company
    python3 feedback_pipeline.py --stats                         # aggregate stats
    python3 feedback_pipeline.py --export-json                   # raw JSON dump
"""
import argparse
import json
import os
from datetime import datetime, timezone

# ── Paths ──────────────────────────────────────────────────────────────
_FEEDBACK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feedback_store.json")


def _load_store() -> list[dict]:
    """Load feedback entries or return empty list."""
    if not os.path.isfile(_FEEDBACK_FILE):
        return []
    try:
        with open(_FEEDBACK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("feedback", [])
    except (json.JSONDecodeError, KeyError):
        return []


def _save_store(entries: list[dict]) -> None:
    """Persist feedback entries atomically."""
    tmp = _FEEDBACK_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"feedback": entries}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _FEEDBACK_FILE)


def record_feedback(
    company: str,
    product: str = "",
    outcome: str = "",
    rating: int = 0,
    notes: str = "",
) -> dict:
    """Add one feedback entry and return it."""
    entries = _load_store()
    entry = {
        "id": len(entries) + 1,
        "company": company.strip(),
        "product": product.strip(),
        "outcome": outcome.strip(),
        "rating": max(0, min(5, int(rating))),  # 1-5 scale, clamp to 0-5
        "notes": notes.strip(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(entry)
    _save_store(entries)
    return entry


def list_feedback(company_filter: str | None = None, limit: int = 50) -> str:
    """Render feedback entries as Markdown."""
    entries = _load_store()
    if company_filter:
        norm = company_filter.strip().lower().replace("ооо ", "").replace('""', "")
        entries = [e for e in entries if company_filter.lower() in e["company"].lower()]
    if not entries:
        return "📭 Обратная связь пуста — записей пока нет."

    limited = entries[-limit:]
    lines = [f"## 📋 Обратная связь ({len(limited)} записей)"]
    lines.append("")
    lines.append("| # | Компания | Продукт | Оценка | Результат | Заметки | Дата |")
    lines.append("|---|----------|---------|--------|-----------|---------|------|")
    for e in limited:
        rating_stars = "⭐" * max(0, e["rating"]) or "—"
        date_short = e["recorded_at"][:10] if e.get("recorded_at") else "—"
        lines.append(
            f"| {e['id']} | {e['company']} | {e['product'] or '—'} | {rating_stars} | "
            f"{e['outcome'] or '—'} | {e['notes'][:40] or '—'} | {date_short} |"
        )
    return "\n".join(lines)


def compute_stats() -> str:
    """Aggregate feedback statistics — useful for re-training signals."""
    entries = _load_store()
    if not entries:
        return "📊 Нет данных для статистики."

    # Overall rating distribution
    rated = [e for e in entries if e.get("rating", 0) > 0]
    avg_rating = sum(e["rating"] for e in rated) / len(rated) if rated else 0

    # Outcome categories
    outcomes: dict[str, int] = {}
    for e in entries:
        key = (e.get("outcome", "—") or "—").strip().lower() or "—"
        outcomes[key] = outcomes.get(key, 0) + 1

    # Product performance
    product_ratings: dict[str, list[int]] = {}
    for e in entries:
        prod = e.get("product") or "—"
        if e.get("rating", 0) > 0:
            product_ratings.setdefault(prod, []).append(e["rating"])

    lines = ["## 📊 Статистика обратной связи", ""]
    lines.append(f"**Всего записей:** {len(entries)}")
    lines.append(f"**Средняя оценка:** {avg_rating:.1f}/5 ({len(rated)} с оценкой)")
    lines.append("")

    lines.append("### Оценки по продуктам")
    lines.append("| Продукт | Сред. оценка | Кол-во |")
    lines.append("|---------|-------------|--------|")
    for prod, scores in sorted(product_ratings.items(), key=lambda x: sum(x[1])/len(x[1]), reverse=True):
        avg = sum(scores) / len(scores)
        lines.append(f"| {prod} | {avg:.1f} | {len(scores)} |")
    lines.append("")

    lines.append("### Распределение результатов")
    for outcome, count in sorted(outcomes.items(), key=lambda x: -x[1]):
        lines.append(f"- **{outcome}:** {count}")
    lines.append("")

    # Re-training signals: low-rated products, unresponsive companies
    low_rated = [e for e in entries if e.get("rating", 0) <= 2]
    if low_rated:
        lines.append("### ⚠️ Точки развития / переобучения")
        lines.append("")
        lines.append("**Низкие оценки (≤2) — стоит уточнить scoring или текст письма:**")
        for e in low_rated:
            lines.append(
                f"- {e['company']} / {e['product'] or 'общее'}: "
                f"оценка {e['rating']}/5 — \"{e['outcome'] or 'нет комментария'}\""
            )
            if e.get("notes"):
                lines.append(f"  → Заметка: {e['notes']}")
        lines.append("")

    return "\n".join(lines)


def export_json() -> str:
    """Dump raw feedback as JSON."""
    entries = _load_store()
    return json.dumps({"feedback": entries, "count": len(entries)}, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FEEDBACK: pipeline results feedback")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--record", action="store_true", help="record new feedback")
    group.add_argument("--list", action="store_true", help="list feedback entries")
    group.add_argument("--stats", action="store_true", help="show aggregate stats")
    group.add_argument("--export-json", action="store_true", help="dump raw JSON")

    parser.add_argument("--company", type=str, default=None, help="company name")
    parser.add_argument("--product", type=str, default=None, help="product key (lending, rko, etc.)")
    parser.add_argument("--outcome", type=str, default=None, help="outcome text")
    parser.add_argument("--rating", type=int, default=0, help="1-5 rating")
    parser.add_argument("--notes", type=str, default=None, help="free-form notes")
    parser.add_argument("--limit", type=int, default=50, help="max entries to show")
    args = parser.parse_args()

    if args.record:
        if not args.company:
            print("❌ --company is required for --record")
            exit(1)
        entry = record_feedback(
            company=args.company,
            product=args.product or "",
            outcome=args.outcome or "",
            rating=args.rating,
            notes=args.notes or "",
        )
        print(f"✅ Feedback #{entry['id']} recorded: {entry['company']} / {entry['product'] or '—'} — rating {entry['rating']}/5")
    elif args.list:
        print(list_feedback(company_filter=args.company, limit=args.limit))
    elif args.stats:
        print(compute_stats())
    elif args.export_json:
        print(export_json())
