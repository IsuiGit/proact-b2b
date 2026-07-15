#!/usr/bin/env python3
"""SCOUT → ANALYST → WARMUP pipeline orchestrator.

Runs the full B2B discovery chain:
  1. SCOUT scans sources, scores events, writes to pipeline_store.json
  2. ANALYST reads store, builds risk profiles, product heatmaps, entry scenarios
  3. WARMUP generates outreach templates for 100%-confidence companies

Usage:
    python3 pipeline_runner.py                  # all three stages, Markdown
    python3 pipeline_runner.py --format json    # all as JSON
    python3 pipeline_runner.py --top-n 20       # limit rows
    python3 pipeline_runner.py --extra-info     # add scan summaries
    python3 pipeline_runner.py --skip-warmup    # skip WARMUP stage
"""
import argparse
import json
import os
import sys
import tempfile

# ── Resolve paths ──────────────────────────────────────────────────────
_DELIVERABLES = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_DELIVERABLES)
_SKILL_DIR = os.path.join(_REPO_ROOT, "data", "skills", "external", "scout")
_STORE_FILE = os.path.join(_REPO_ROOT, "data", "sberbank_pipeline", "pipeline_store.json")

if _SKILL_DIR not in sys.path:
    sys.path.insert(0, _SKILL_DIR)
if _DELIVERABLES not in sys.path:
    sys.path.insert(0, _DELIVERABLES)

# ── Imports ────────────────────────────────────────────────────────────
from scout_pipeline import run as scout_run
from analyst_pipeline import run_analyst
from warmup_pipeline import run as warmup_run


def main() -> None:
    parser = argparse.ArgumentParser(description="SCOUT → ANALYST → WARMUP pipeline")
    parser.add_argument("--limit", type=int, default=1000, help="max events per source")
    parser.add_argument("--top-n", type=int, default=50, help="rows per table")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--extra-info", action="store_true", help="include scan summaries")
    parser.add_argument("--dry-run", action="store_true", help="skip store writes")
    parser.add_argument("--skip-warmup", action="store_true", help="skip WARMUP stage")
    args = parser.parse_args()

    # ── Step 1: SCOUT ──────────────────────────────────────────────
    scout_result = scout_run(
        limit=args.limit,
        top_n=args.top_n,
        fmt=args.format,
        extra_info=args.extra_info,
        dry_run=args.dry_run,
    )

    # SCOUT returns a string — parse for chaining
    if args.format == "json":
        scout_json = json.loads(scout_result) if isinstance(scout_result, str) else scout_result
    else:
        scout_json = None  # scout_result is the markdown table string

    # Write scout events to store for analyst
    if args.format == "json":
        events = scout_json.get("events", scout_json) if isinstance(scout_json, dict) else scout_json
    else:
        events = None  # scout_run already saved to store internally
        scout_for_input = _STORE_FILE

    if args.format == "json" and events:
        analyst_input_data = {"last_result": {"events": events}}
        if not args.dry_run:
            os.makedirs(os.path.dirname(_STORE_FILE), exist_ok=True)
            with open(_STORE_FILE, "w", encoding="utf-8") as f:
                json.dump(analyst_input_data, f, ensure_ascii=False, indent=2)
        analyst_input_path = _STORE_FILE
    else:
        analyst_input_path = _STORE_FILE

    # ── Step 2: ANALYST ────────────────────────────────────────────
    analyst_result = run_analyst(
        input_path=analyst_input_path,
        top_n=args.top_n,
        fmt="json",  # Always get JSON so WARMUP can use it
    )
    analyst_json = json.loads(analyst_result) if isinstance(analyst_result, str) else analyst_result
    # Save analyst JSON for WARMUP
    analyst_tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8", dir=_DELIVERABLES)
    json.dump(analyst_json, analyst_tmp, ensure_ascii=False, indent=2)
    analyst_tmp.close()

    # ── Step 3: WARMUP (only 100%-confidence companies) ───────────
    warmup_result = None
    if not args.skip_warmup:
        warmup_result = warmup_run(
            input_json=analyst_tmp.name,
            scout_store=_STORE_FILE,
            top_n=args.top_n,
            fmt=args.format,
        )

    # ── Step 4: Combined output ────────────────────────────────────
    if args.format == "json":
        output = {
            "scout": scout_json if isinstance(scout_json, dict) else {"events": scout_json},
            "analyst": analyst_json,
        }
        if warmup_result:
            output["warmup"] = json.loads(warmup_result) if isinstance(warmup_result, str) else warmup_result
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        parts = []
        parts.append("## SCOUT — найденные инфоповоды")
        parts.append(scout_result)
        parts.append("")
        parts.append("## ANALYST — профили компаний")
        # Render analyst markdown ourselves from JSON
        analyst_markdown = _analyst_to_markdown(analyst_json.get("profiles", []), args.top_n)
        parts.append(analyst_markdown)
        if warmup_result and "нет компаний с уверенностью 100%" not in warmup_result:
            parts.append("")
            parts.append(warmup_result)
        print("\n".join(parts))

    # Cleanup temp
    try:
        os.unlink(analyst_tmp.name)
    except OSError:
        pass


def _analyst_to_markdown(profiles: list[dict], top_n: int) -> str:
    _RISK_MAP = {
        "very_low": "✅", "low": "🟢", "neutral": "⚪",
        "moderate": "🟡", "high": "🟠", "very_high": "🔴",
    }
    _STRATEGY_MAP = {
        "warm_lead": "тёплый", "approach_carefully": "осмотрительно",
        "nurture": "наблюдать", "avoid": "избегать",
    }
    _PRODUCT_NAMES = {
        "rko": "РКО", "lending": "Кредитование", "leasing": "Лизинг",
        "salary_project": "Зарплатный проект", "ved": "ВЭД/FX",
        "bank_guarantee": "Банковские гарантии", "acquiring": "Эквайринг",
    }
    lines = [
        "| # | Компания | Риск | Стратегия | Топ-продукт | Уверенность |",
        "|---|----------|------|-----------| -------------|-------------|",
    ]
    sorted_profiles = sorted(profiles, key=lambda x: x.get("overall_score", 0), reverse=True)[:top_n]
    for i, p in enumerate(sorted_profiles, 1):
        risk = _RISK_MAP.get(p.get("risk_profile", {}).get("level", "moderate"), "❓")
        strategy = _STRATEGY_MAP.get(p.get("entry_scenario", {}).get("approach", "nurture"), "—")
        heatmap = p.get("product_heatmap", [])
        if heatmap:
            best = max(heatmap, key=lambda x: x.get("score", 0))
            product = _PRODUCT_NAMES.get(best.get("product", ""), best.get("product", "—"))
            confidence = f"{best.get('score', 0)*100:.0f}%"
        else:
            product = "—"
            confidence = "—"
        lines.append(f"| {i} | {p.get('company_name', '—')} | {risk} | {strategy} | {product} | {confidence} |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
