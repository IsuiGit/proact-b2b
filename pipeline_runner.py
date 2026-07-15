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
from brief_pipeline import run_brief
from tracker_pipeline import run as tracker_run, record_contact, should_warmup, format_funnel
from feedback_pipeline import list_feedback as fb_list, compute_stats as fb_stats
from feedback_applier import apply_feedback as fb_apply, get_status as fb_status


def _money(amount: float | None) -> str:
    """Human-readable rouble amount. Mirrors _fmt_money in brief_pipeline."""
    if amount is None or amount <= 0:
        return "—"
    for unit, threshold in [
        ("трлн ₽", 1e12),
        ("млрд ₽", 1e9),
        ("млн ₽", 1e6),
        ("₽", 1e3),
    ]:
        if amount >= threshold:
            val = amount / threshold
            return f"{val:.1f} {unit}" if val == int(val) else f"{val:.2f} {unit}"
    return f"{amount:.0f} ₽"


def main() -> None:
    parser = argparse.ArgumentParser(description="SCOUT → ANALYST → WARMUP pipeline")
    parser.add_argument("--limit", type=int, default=1000, help="max events per source")
    parser.add_argument("--top-n", type=int, default=50, help="rows per table")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--extra-info", action="store_true", help="include scan summaries")
    parser.add_argument("--dry-run", action="store_true", help="skip store writes")
    parser.add_argument("--skip-warmup", action="store_true", help="skip WARMUP stage")
    parser.add_argument("--skip-tracker", action="store_true", help="skip TRACKER filtering")
    parser.add_argument("--brief", type=str, default=None, help="company name/INN for BRIEF report")
    parser.add_argument("--result", nargs=2, metavar=("COMPANY", "STATUS"),
                        help="Record contact result: <company> <status>")
    parser.add_argument("--feedback-stats", action="store_true", help="show feedback stats after run")
    parser.add_argument("--feedback-list", action="store_true", help="show all feedback entries")
    parser.add_argument("--feedback-record", nargs=3, metavar=("COMPANY", "PRODUCT", "OUTCOME"),
                        help="Record feedback: <company> <product> <outcome>")
    parser.add_argument("--threshold", type=float, default=0.9,
                        help="WARMUP confidence threshold (default 0.9 = 90%%)")
    parser.add_argument("--learn", action="store_true",
                        help="Apply feedback adjustments before running pipeline (manual learn)")
    parser.add_argument("--feedback-general", type=str, default=None, metavar="TEXT",
                        help="Record free-form feedback after a pipeline run")
    args = parser.parse_args()

    # ── Handle --result (record contact and exit) ─────────────────
    if args.result:
        company, status = args.result
        record_contact(company, status)
        print(f"✅ Contact recorded: {company} → {status}")
        return

    # ── Handle --feedback-record (record feedback and exit) ───────
    if args.feedback_record:
        company, product, outcome = args.feedback_record
        from feedback_pipeline import record_feedback as fb_store
        entry = fb_store(company=company, product=product, outcome=outcome)
        print(f"✅ Feedback #{entry['id']} recorded: {entry['company']} / {entry['product']} — \"{entry['outcome']}\"")
        return

    # ── Handle --feedback-general (free-form feedback) ────────────
    if args.feedback_general:
        from feedback_pipeline import record_general_feedback as fb_general
        entries = fb_general(args.feedback_general)
        print(f"✅ Feedback recorded ({len(entries)} entries): \"{args.feedback_general}\"")
        return

    # ── Handle --learn standalone (apply feedback and exit) ───────
    if args.learn:
        # Check if there are pending feedback entries
        from feedback_applier import has_pending_feedback
        pending = has_pending_feedback()
        if pending:
            print(fb_apply(time_window_hours=99999))
            # After applying, show status
            print()
            print(fb_status())
        else:
            print("📭 Нет записей для обучения. Сначала соберите обратную связь через:")
            print('  python3 pipeline_runner.py --feedback-record "Компания" "Продукт" "Результат"')
        return

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
    # Load feedback adjustments (if any) for scoring
    adjustments = None
    try:
        from feedback_applier import load_adjustments
        adjustments, _ = load_adjustments()
    except Exception:
        pass

    analyst_json_str = run_analyst(
        input_path=analyst_input_path,
        top_n=args.top_n,
        fmt="json",
        adjustments=adjustments,
    )
    analyst_json = json.loads(analyst_json_str) if isinstance(analyst_json_str, str) else analyst_json_str
    # Also get markdown for display
    analyst_markdown = run_analyst(
        input_path=analyst_input_path,
        top_n=args.top_n,
        fmt="text",
        adjustments=adjustments,
    )
    # Save analyst JSON for WARMUP
    analyst_tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8", dir=_DELIVERABLES)
    json.dump(analyst_json, analyst_tmp, ensure_ascii=False, indent=2)
    analyst_tmp.close()

    # ── Step 3: WARMUP ─────────────────────────────────────────────
    warmup_result = None
    
    if not args.skip_warmup:
        warmup_result = warmup_run(
            input_json=analyst_tmp.name,
            scout_store=_STORE_FILE,
            top_n=args.top_n,
            fmt=args.format,
            threshold=args.threshold,
        )

    # ── Step 4: TRACKER funnel output ────────────────────────────
    tracker_markdown = None
    if not args.skip_tracker:
        tracker_markdown = format_funnel()

    # Extract warmup-passed companies from analyst data for BRIEF
    warmup_companies = []
    if not args.skip_warmup and warmup_result and "нет компаний с уверенностью" not in warmup_result:
        for p in analyst_json.get("profiles", []):
            if any(pr.get("score", 0) >= args.threshold for pr in p.get("product_heatmap", [])):
                warmup_companies.append(p["company_name"])

    # ── Step 5: Combined output ───────────────────────────────────
    if args.format == "json":
        output = {
            "scout": scout_json if isinstance(scout_json, dict) else {"events": scout_json},
            "analyst": analyst_json,
        }
        if warmup_result:
            output["warmup"] = json.loads(warmup_result) if isinstance(warmup_result, str) else warmup_result
        # Auto-BRIEF for WARMUP companies
        briefs = []
        for company_name in warmup_companies:
            brief_result = run_brief(
                company_query=company_name,
                analyst_path=analyst_tmp.name,
                scout_path=_STORE_FILE,
                fmt="json",
            )
            briefs.append(json.loads(brief_result) if isinstance(brief_result, str) else brief_result)
        if args.brief and args.brief not in warmup_companies:
            brief_result = run_brief(
                company_query=args.brief,
                analyst_path=analyst_tmp.name,
                scout_path=_STORE_FILE,
                fmt="json",
            )
            briefs.append(json.loads(brief_result) if isinstance(brief_result, str) else brief_result)
        if briefs:
            output["brief"] = briefs
        if tracker_markdown:
            output["tracker_funnel"] = format_funnel()
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        parts = []

        # ── SCOUT ──
        parts.append("## 1️⃣ SCOUT — найденные инфоповоды")
        parts.append(scout_result)
        parts.append("")

        # ── ANALYST ──
        parts.append("## 2️⃣ ANALYST — профили компаний")
        parts.append(analyst_markdown)
        parts.append("")

        # ── WARMUP ──
        if warmup_result and "нет компаний с уверенностью" not in warmup_result:
            parts.append(warmup_result)

        # ── BRIEF (полные досье) ──
        brief_targets = list(warmup_companies)
        if args.brief and args.brief not in warmup_companies:
            brief_targets.append(args.brief)
        if brief_targets:
            parts.append("## 📋 BRIEF — досье по целевым компаниям")
            for company_name in brief_targets:
                brief_result = run_brief(
                    company_query=company_name,
                    analyst_path=analyst_tmp.name,
                    scout_path=_STORE_FILE,
                    fmt="text",
                )
                parts.append(brief_result)
                parts.append("")

        # ── TRACKER ──
        if not args.skip_tracker:
            funnel = format_funnel(top_n=args.top_n)
            if funnel:
                parts.append("## 📊 TRACKER — воронка")
                parts.append(funnel)
        
        # FEEDBACK section
        if args.feedback_stats:
            parts.append("")
            parts.append(fb_stats())
        if args.feedback_list:
            parts.append("")
            parts.append(fb_list(limit=args.top_n))
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
