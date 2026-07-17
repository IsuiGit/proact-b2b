#!/usr/bin/env python3
"""SCOUT B2B Pipeline — raw event collector.

No scoring, no weights, no rationale. Just collects events from sources,
deduplicates, and outputs raw JSON for LLM analysis.

Usage:
    python scout_pipeline.py              # text output
    python scout_pipeline.py --format json # JSON output
    python scout_pipeline.py --top-n 20    # limit results
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Locate the SCOUT skill directory ──────────────────────────────────
_SKILL_DIR = Path(__file__).resolve().parent.parent / "data" / "skills" / "external" / "scout"
if not _SKILL_DIR.is_dir():
    _alt = Path.home() / "ouroboros" / "data" / "skills" / "external" / "scout"
    if _alt.is_dir():
        _SKILL_DIR = _alt
    else:
        print(f"[ERROR] Cannot find scout skill directory.", file=sys.stderr)
        sys.exit(1)

if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

# ── Pipeline store ────────────────────────────────────────────────────
_STORE_DIR = Path(__file__).resolve().parent.parent / "data" / "sberbank_pipeline"

# ── Import SCOUT fetchers ─────────────────────────────────────────────
from sources.base import BaseFetcher
from sources.zakupki import ZakupkiFetcher
from sources.kad_arbitr import KadArbitrFetcher
from sources.fedresurs import FedresursFetcher
from sources.e_disclosure import EDisclosureFetcher
from sources.kontur_zakupki import KonturZakupkiFetcher
from sources.news_rss import NewsRSSFetcher
from sources.egrul_changes import EgrulChangesFetcher
from sources.mock_egrul import MockEgrulFetcher
from sources.mock_fns import MockFnsFetcher
from sources.mock_hh import MockHHFetcher
from sources.mock_nashdom_rf import MockNashdomRFFetcher
from sources.mock_project_registry import MockProjectRegistryFetcher


def get_fetchers() -> list[BaseFetcher]:
    return [
        ZakupkiFetcher(),
        KadArbitrFetcher(),
        FedresursFetcher(),
        EDisclosureFetcher(),
        KonturZakupkiFetcher(),
        NewsRSSFetcher(),
        EgrulChangesFetcher(),
        MockEgrulFetcher(),
        MockFnsFetcher(),
        MockHHFetcher(),
        MockNashdomRFFetcher(),
        MockProjectRegistryFetcher(),
    ]


def generate_id(event: dict) -> str:
    content = f"{event['company_name']}:{event['event_type']}:{event.get('raw_snippet', '')}"
    return hashlib.md5(content.encode()).hexdigest()[:8]


def _make_company_id(company_name: str, inn: str | None = None) -> str:
    if inn and str(inn).strip():
        return f"inn_{inn.strip()}"
    safe = company_name.lower().strip()[:50]
    safe = "".join(c if c.isalnum() else "_" for c in safe)
    return f"co_{safe}"


def _event_description(event: dict) -> str:
    return (
        event.get("raw_snippet", "")
        or event.get("description", "")
        or f"{event.get('company_name', '—')}: {event.get('event_type', '')}"
    )


def _potential_revenue(event: dict) -> int:
    metrics = event.get("metrics", {})
    return int(
        metrics.get("amount_rub", 0)
        or metrics.get("claim_amount_rub", 0)
        or metrics.get("investment_rub", 0)
        or metrics.get("capital_rub", 0)
        or 0
    )


def normalize_event(event: dict) -> dict:
    """Convert raw fetcher event to clean output format. No scoring."""
    company_name = event.get("company_name", "—")
    inn = event.get("metrics", {}).get("inn")
    return {
        "id": generate_id(event),
        "company_name": company_name,
        "inn": inn,
        "source": event.get("source", ""),
        "event_type": event.get("event_type", ""),
        "event_description": _event_description(event),
        "amount": _potential_revenue(event),
        "detected_at": event.get("detected_at", datetime.now(timezone.utc).isoformat()),
    }


def dedup_events(events: list[dict]) -> list[dict]:
    seen = {}
    for event in events:
        key = f"{event['company_name']}:{event['event_type']}"
        if key not in seen:
            seen[key] = event
    return list(seen.values())


def _read_store() -> dict:
    store_file = _STORE_DIR / "pipeline_store.json"
    if not store_file.exists():
        return {"last_result": None, "companies": {}}
    with open(store_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_store(data: dict) -> None:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    store_file = _STORE_DIR / "pipeline_store.json"
    tmp = store_file.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    tmp.replace(store_file)


def save_last_result(raw_count: int, unique_count: int, events: list[dict], source_stats: list[dict]) -> None:
    data = _read_store()
    for ev in events:
        cid = ev["company_id"]
        if cid not in data.setdefault("companies", {}):
            data["companies"][cid] = {"name": ev["company_name"], "inn": ev.get("inn"), "interactions": []}
        data["companies"][cid]["interactions"].append({
            "type": "discovered",
            "detail": ev["event_description"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    data["last_result"] = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "raw_count": raw_count,
        "unique_count": unique_count,
        "events": events,
        "source_stats": source_stats,
    }
    _write_store(data)


def run(limit: int = 1000, top_n: int = 50, fmt: str = "text", extra_info: bool = False, dry_run: bool = False) -> str:
    # 1. Fetch
    fetchers = get_fetchers()
    raw_events = []
    source_stats = []
    for fetcher in fetchers:
        available = fetcher.is_available()
        source_type = "real" if available else "mock"
        try:
            events = fetcher.fetch(limit=limit)
            raw_events.extend(events)
            source_stats.append({"name": fetcher.name, "mode": source_type, "count": len(events)})
            print(f"[SCOUT] {fetcher.name} ({source_type}): {len(events)} events", file=sys.stderr)
        except Exception as e:
            print(f"[SCOUT] {fetcher.name} FAILED: {e}", file=sys.stderr)
            source_stats.append({"name": fetcher.name, "mode": "error", "count": 0})

    print(f"[SCOUT] Total raw events: {len(raw_events)}", file=sys.stderr)

    # 2. Normalize (no scoring)
    normalized = [normalize_event(e) for e in raw_events]

    # 3. Dedup
    unique_events = dedup_events(normalized)
    print(f"[SCOUT] Unique after dedup: {len(unique_events)}", file=sys.stderr)

    # 4. Top-N (by amount descending)
    unique_events.sort(key=lambda e: e.get("amount", 0), reverse=True)
    top_events = unique_events[:top_n]

    # 5. Add company_id for store
    for ev in top_events:
        ev["company_id"] = _make_company_id(ev["company_name"], ev.get("inn"))

    # 6. Store
    if not dry_run:
        try:
            save_last_result(
                raw_count=len(raw_events),
                unique_count=len(unique_events),
                events=top_events,
                source_stats=source_stats,
            )
            print(f"[SCOUT] Saved to pipeline_store.json", file=sys.stderr)
        except Exception as e:
            print(f"[SCOUT] Store write failed: {e}", file=sys.stderr)

    # 7. Format output
    if fmt == "json":
        return json.dumps({
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "raw_count": len(raw_events),
            "unique_count": len(unique_events),
            "source_stats": source_stats,
            "events": top_events,
        }, ensure_ascii=False, indent=2, default=str)
    else:
        lines = [
            f"**{len(source_stats)} источников** → {len(raw_events)} сырых → {len(unique_events)} уникальных → **Топ-{len(top_events)}**",
            "",
            "| # | Компания | Источник | Событие | Сумма |",
            "|---|----------|----------|---------|-------|",
        ]
        for i, ev in enumerate(top_events, 1):
            amt = ev.get("amount", 0)
            if amt >= 1e6:
                amt_str = f"{amt/1e6:.1f} млн ₽"
            elif amt >= 1e3:
                amt_str = f"{amt/1e3:.0f} тыс ₽"
            else:
                amt_str = "—"
            lines.append(f"| {i} | {ev['company_name']} | {ev['source']} | {ev['event_type']} | {amt_str} |")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="SCOUT B2B Pipeline — raw collector")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument("--format", type=str, choices=["text", "json"], default="text")
    parser.add_argument("--extra-info", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run(limit=args.limit, top_n=args.top_n, fmt=args.format, extra_info=args.extra_info, dry_run=args.dry_run)
    print(result)


if __name__ == "__main__":
    main()
