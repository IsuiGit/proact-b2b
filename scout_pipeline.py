#!/usr/bin/env python3
"""SCOUT B2B Pipeline — standalone runner.

No git, no skill-review gates, no commit_reviewed.

Usage:
    python ~/Ouroboros/Deliverables/scout_pipeline.py              # Markdown (chat)
    python ~/Ouroboros/Deliverables/scout_pipeline.py --format json # JSON (tools)
    python ~/Ouroboros/Deliverables/scout_pipeline.py --top-n 20    # top 20 results

Dependencies: lives in data/skills/external/scout/ (sources, significance, output).
This script just adds the skill directory to sys.path and calls the pipeline.

The store (pipeline_store.json) still writes to data/sberbank_pipeline/ —
it is a separate JSON file, not a git-tracked artifact.
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
    # Fallback: try relative to ~/ouroboros
    _alt = Path.home() / "ouroboros" / "data" / "skills" / "external" / "scout"
    if _alt.is_dir():
        _SKILL_DIR = _alt
    else:
        print(f"[ERROR] Cannot find scout skill directory.", file=sys.stderr)
        print(f"  Tried: {_SKILL_DIR}", file=sys.stderr)
        print(f"  Also:  {_alt}", file=sys.stderr)
        sys.exit(1)

if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

# ── Pipeline store ────────────────────────────────────────────────────
_STORE_DIR = Path(__file__).resolve().parent.parent / "data" / "sberbank_pipeline"

# ── Import SCOUT modules ─────────────────────────────────────────────
from significance import calc_weight
from output import format_top_events, format_as_json, format_scan_summary
from sources.base import BaseFetcher

# Source imports (all follow BaseFetcher contract)
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


def get_fetchers() -> list[BaseFetcher]:
    """Return all fetchers, ordered by priority."""
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
    ]


def generate_id(event: dict) -> str:
    content = f"{event['company_name']}:{event['event_type']}:{event.get('raw_snippet', '')}"
    return hashlib.md5(content.encode()).hexdigest()[:4]


def _make_company_id(company_name: str, inn: str | None = None) -> str:
    if inn and str(inn).strip():
        return f"inn_{inn.strip()}"
    safe = company_name.lower().strip()[:50]
    safe = "".join(c if c.isalnum() else "_" for c in safe)
    return f"co_{safe}"


def dedup_events(events: list[dict]) -> list[dict]:
    seen = {}
    for event in events:
        key = f"{event['company_name']}:{event['event_type']}"
        weight = event.get("weight", 0)
        if key not in seen or weight > seen[key].get("weight", 0):
            seen[key] = event
    return list(seen.values())


def _event_description(event: dict) -> str:
    name = event.get("company_name", "—")
    etype = event.get("event_type", "")
    return f"{name}: {etype}"


def _potential_revenue(event: dict) -> int:
    metrics = event.get("metrics", {})
    return int(
        metrics.get("amount_rub", 0)
        or metrics.get("claim_amount_rub", 0)
        or metrics.get("investment_rub", 0)
        or metrics.get("capital_rub", 0)
        or 0
    )


def enrich_event(event: dict) -> dict:
    weight, products, rationale = calc_weight(event)
    company_name = event.get("company_name", "—")
    inn = event.get("metrics", {}).get("inn")
    return {
        "id": generate_id(event),
        "company_id": _make_company_id(company_name, inn),
        "company_name": company_name,
        "inn": inn,
        "event_type": event.get("event_type", ""),
        "event_description": _event_description(event),
        "weight": weight,
        "potential_revenue": _potential_revenue(event),
        "detected_at": event.get("detected_at", datetime.now(timezone.utc).isoformat()),
        "recommended_products": products,
        "source": event.get("source", ""),
        "rationale": rationale,
    }


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

    # 2. Score
    scored_events = [enrich_event(e) for e in raw_events]

    # 3. Dedup
    unique_events = dedup_events(scored_events)
    print(f"[SCOUT] Unique after dedup: {len(unique_events)}", file=sys.stderr)

    # 4. Sort + top-N
    unique_events.sort(key=lambda e: e["weight"], reverse=True)
    top_events = unique_events[:top_n]

    # 5. Store (unless dry-run)
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

    # 6. Format
    if fmt == "json":
        return format_as_json(top_events, top_n=top_n)
    else:
        # --extra-info shows scan summary + table; default is bare table only
        table = format_top_events(top_events, top_n=top_n, header=False)
        if extra_info:
            summary = format_scan_summary(len(raw_events), len(unique_events), source_stats, top_n=top_n)
            return summary + "\n\n" + table
        return table


def main():
    parser = argparse.ArgumentParser(description="SCOUT B2B Pipeline — standalone")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument("--format", type=str, choices=["text", "json"], default="text")
    parser.add_argument("--extra-info", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run(limit=args.limit, top_n=args.top_n, fmt=args.format, extra_info=args.extra_info, dry_run=args.dry_run)
    # Always print raw text — let the chat renderer interpret markdown
    print(result)


if __name__ == "__main__":
    main()
