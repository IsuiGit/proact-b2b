#!/usr/bin/env python3
"""FEEDBACK APPLIER — корректировка пайплайна по обратной связи.

Reads feedback_store.json, filters entries from last 24h (or all for manual
--learn), groups by signal type, and applies weight/tone adjustments to the
pipeline configuration.

Usage:
    python3 feedback_applier.py               # auto: last 24h only
    python3 feedback_applier.py --learn       # manual: all pending entries
    python3 feedback_applier.py --dry-run     # preview without applying
    python3 feedback_applier.py --reset       # revert to defaults
    python3 feedback_applier.py --status      # show current adjustments
"""
import argparse
import json
import os
import secrets
from datetime import datetime, timezone, timedelta
from copy import deepcopy

# ── Paths ──────────────────────────────────────────────────────────────
_FEEDBACK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feedback_store.json")
_ADJUSTMENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feedback_adjustments.json")

# ── Default weights (match analyst_pipeline defaults) ─────────────────
_DEFAULT_PRODUCT_WEIGHTS = {
    "rko": 1.0,
    "lending": 1.0,
    "bank_guarantee": 1.0,
    "leasing": 1.0,
    "salary_project": 1.0,
    "ved": 1.0,
    "acquiring": 1.0,
}
_DEFAULT_LITIGATION_PENALTY = 0.3   # multiplies score for companies with court cases
_DEFAULT_WARMUP_TONE = "professional"  # professional | casual | formal

# ── Tuning step sizes ─────────────────────────────────────────────────
_STEP_DOWN = 0.15   # product weight decrease for low-rated feedback
_STEP_UP = 0.10     # product weight increase for high-rated feedback
_LITIGATION_ADJUST = 0.05  # penalty adjustment for "судебное дело" feedback
_MAX_WEIGHT = 2.0
_MIN_WEIGHT = 0.2


def _load_feedback() -> list[dict]:
    if not os.path.isfile(_FEEDBACK_FILE):
        return []
    with open(_FEEDBACK_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("feedback", [])


def _load_adjustments() -> dict:
    if not os.path.isfile(_ADJUSTMENTS_FILE):
        return {
            "version": 1,
            "product_weights": deepcopy(_DEFAULT_PRODUCT_WEIGHTS),
            "litigation_penalty": _DEFAULT_LITIGATION_PENALTY,
            "warmup_tone": _DEFAULT_WARMUP_TONE,
            "history": [],
        }
    with open(_ADJUSTMENTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_adjustments(adj: dict) -> None:
    tmp = _ADJUSTMENTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(adj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _ADJUSTMENTS_FILE)


def _classify_feedback(entry: dict) -> list[str]:
    """Classify a feedback entry into signal types.
    Returns list of signal tags. Entries with no actionable signal are ignored.
    """
    signals = []
    outcome = (entry.get("outcome") or "").lower()
    notes = (entry.get("notes") or "").lower()
    text = outcome + " " + notes
    rating = entry.get("rating", 0)
    product = (entry.get("product") or "").lower()

    # Low rating on a specific product → product weight adjustment
    if product and rating <= 2:
        signals.append(f"product_down:{product}")
    elif product and rating >= 4:
        signals.append(f"product_up:{product}")

    # Outcome mentions litigation sensitivity
    if any(w in text for w in ["суд", "иск", "разбирательств", "проблем", "риск", "осторожн"]):
        signals.append("litigation_sensitive")
    elif any(w in text for w in ["не ответили", "игнор", "спам", "холодн", "не интерес"]):
        signals.append("low_engagement")
    elif any(w in text for w in ["ответили", "интерес", "хорош", "нравит", "подходит"]):
        signals.append("high_engagement")

    # Explicit tone request
    if any(w in text for w in ["слишком формальн", "сух", "официоз"]):
        signals.append("tone_more_casual")
    elif any(w in text for w in ["слишком прост", "фамильярн", "не серьёзн"]):
        signals.append("tone_more_formal")

    # Generic low quality request (not product-specific) → not actionable
    # Skip entries with no signals — they lack actionable structure
    return signals


def _apply_signals_to_adjustments(signals: list[str], adj: dict, entry: dict, dry_run: bool) -> list[str]:
    """Apply classified signals to the adjustments. Returns log lines."""
    logs = []
    for sig in signals:
        if sig.startswith("product_down:"):
            prod = sig.split(":", 1)[1]
            key = _normalize_product_key(prod)
            if key in adj["product_weights"]:
                old = adj["product_weights"][key]
                adj["product_weights"][key] = max(_MIN_WEIGHT, old - _STEP_DOWN)
                logs.append(
                    f"  ⬇ {key}: {old:.2f} → {adj['product_weights'][key]:.2f} "
                    f"(низкая оценка для {entry.get('company', '?')})"
                )
        elif sig.startswith("product_up:"):
            prod = sig.split(":", 1)[1]
            key = _normalize_product_key(prod)
            if key in adj["product_weights"]:
                old = adj["product_weights"][key]
                adj["product_weights"][key] = min(_MAX_WEIGHT, old + _STEP_UP)
                logs.append(
                    f"  ⬆ {key}: {old:.2f} → {adj['product_weights'][key]:.2f} "
                    f"(высокая оценка для {entry.get('company', '?')})"
                )
        elif sig == "litigation_sensitive":
            old = adj["litigation_penalty"]
            adj["litigation_penalty"] = min(0.95, old + _LITIGATION_ADJUST)
            logs.append(
                f"  ⬆ litigation_penalty: {old:.2f} → {adj['litigation_penalty']:.2f} "
                f"(чувствительность к судебным делам)"
            )
        elif sig == "low_engagement":
            # Slightly reduce overall confidence — make warmup more conservative
            adj["litigation_penalty"] = min(0.95, adj["litigation_penalty"] + _LITIGATION_ADJUST * 0.5)
            logs.append(
                f"  ~ litigation_penalty +{ _LITIGATION_ADJUST * 0.5:.2f} (низкая вовлечённость)"
            )
        elif sig == "high_engagement":
            # Slight positive signal — reward the product if known
            if entry.get("product"):
                key = _normalize_product_key(entry["product"])
                if key in adj["product_weights"]:
                    old = adj["product_weights"][key]
                    adj["product_weights"][key] = min(_MAX_WEIGHT, old + _STEP_UP * 0.5)
                    logs.append(
                        f"  ⬆ {key}: {old:.2f} → {adj['product_weights'][key]:.2f} (подтверждённый интерес)"
                    )
        elif sig == "tone_more_casual":
            if adj["warmup_tone"] == "formal":
                adj["warmup_tone"] = "professional"
                logs.append("  🔀 tone: formal → professional")
            elif adj["warmup_tone"] == "professional":
                adj["warmup_tone"] = "casual"
                logs.append("  🔀 tone: professional → casual")
            else:
                logs.append("  ~ tone: уже casual, не менять")
        elif sig == "tone_more_formal":
            if adj["warmup_tone"] == "casual":
                adj["warmup_tone"] = "professional"
                logs.append("  🔀 tone: casual → professional")
            elif adj["warmup_tone"] == "professional":
                adj["warmup_tone"] = "formal"
                logs.append("  🔀 tone: professional → formal")
            else:
                logs.append("  ~ tone: уже formal, не менять")
    return logs


def _normalize_product_key(product: str) -> str:
    """Map human product names to internal keys."""
    mapping = {
        "рко": "rko", "расчётный": "rko", "расчетный": "rko",
        "кредит": "lending", "кредитование": "lending", " loan": "lending",
        "гарант": "bank_guarantee", "тендерн": "bank_guarantee",
        "лизинг": "leasing", "аренда": "leasing",
        "зарплат": "salary_project", "зарплата": "salary_project",
        "вэд": "ved", "fx": "ved", "валют": "ved",
        "эквайринг": "acquiring", "карт": "acquiring",
    }
    product = product.lower().strip()
    for keyword, key in mapping.items():
        if keyword in product:
            return key
    return product  # unknown pass-through


def apply_feedback(time_window_hours: int = 24, dry_run: bool = False) -> str:
    """Main entry: read feedback, apply, save adjustments."""
    entries = _load_feedback()
    if not entries:
        return "📭 Нет записей обратной связи — нечего применять."

    # Filter by time window
    cutoff = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)
    if time_window_hours > 9999:  # --learn: all entries
        pending = entries
    else:
        pending = [
            e for e in entries
            if e.get("recorded_at") and datetime.fromisoformat(e["recorded_at"]) >= cutoff
        ]

    if not pending:
        return f"📭 Нет новых записей за последние {time_window_hours}ч."

    adj = _load_adjustments()
    all_logs = []
    applied_ids = []
    skipped = 0

    for entry in pending:
        signals = _classify_feedback(entry)
        if not signals:
            skipped += 1
            continue

        logs = _apply_signals_to_adjustments(signals, adj, entry, dry_run)
        if logs:
            all_logs.append(f"#{entry['id']} ({entry.get('company', '?')}):")
            all_logs.extend(logs)
            applied_ids.append(entry["id"])

    if not applied_ids:
        return f"📭 {len(pending)} записей, но ни одна не содержит actionable сигналов ({skipped} пропущено)."

    # Record history entry
    run_id = secrets.token_hex(6)
    adj["history"].append({
        "run_id": run_id,
        "applied_ids": applied_ids,
        "skipped": skipped,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "product_weights": deepcopy(adj["product_weights"]),
        "litigation_penalty": adj["litigation_penalty"],
        "warmup_tone": adj["warmup_tone"],
    })

    # Keep only last 20 history entries
    adj["history"] = adj["history"][-20:]

    if not dry_run:
        _save_adjustments(adj)

    lines = [f"## 🔧 Применено корректировок: {len(applied_ids)} из {len(pending)}"]
    lines.append("")
    lines.extend(all_logs)
    lines.append("")
    lines.append(f"Пропущено (нет actionable сигнала): {skipped}")
    lines.append("")
    lines.append("### Текущее состояние:")
    lines.append(f"- **Product weights:** {json.dumps(adj['product_weights'], ensure_ascii=False)}")
    lines.append(f"- **Litigation penalty:** {adj['litigation_penalty']:.2f}")
    lines.append(f"- **WARMUP tone:** {adj['warmup_tone']}")
    if dry_run:
        lines.append("")
        lines.append("⚠️ DRY RUN — изменения НЕ сохранены.")
    return "\n".join(lines)


def has_pending_feedback() -> bool:
    """Check if there are unapplied feedback entries."""
    entries = _load_feedback()
    adj = _load_adjustments()
    applied_ids = set()
    for run in adj.get("history", []):
        applied_ids.update(run.get("applied_ids", []))
    for e in entries:
        if e.get("id") not in applied_ids:
            return True
    return False


def get_status() -> str:
    """Show current adjustments."""
    adj = _load_adjustments()
    product_adj = {
        k: v for k, v in adj["product_weights"].items()
        if abs(v - _DEFAULT_PRODUCT_WEIGHTS.get(k, 1.0)) > 0.01
    }
    lit_adj = abs(adj["litigation_penalty"] - _DEFAULT_LITIGATION_PENALTY) > 0.01
    tone_adj = adj["warmup_tone"] != _DEFAULT_WARMUP_TONE

    lines = ["## 📊 Текущие корректировки пайплайна", ""]
    if not product_adj and not lit_adj and not tone_adj:
        lines.append("Нет отклонений от значений по умолчанию.")
    else:
        if product_adj:
            lines.append("**Product weights:**")
            lines.append("| Продукт | Дефолт | Текущий | Δ |")
            lines.append("|---------|--------|---------|---|")
            for k, v in product_adj.items():
                d = _DEFAULT_PRODUCT_WEIGHTS.get(k, 1.0)
                delta = v - d
                sign = "+" if delta > 0 else ""
                lines.append(f"| {k} | {d:.2f} | {v:.2f} | {sign}{delta:.2f} |")
            lines.append("")
        if lit_adj:
            lines.append(f"**Litigation penalty:** {_DEFAULT_LITIGATION_PENALTY:.2f} → {adj['litigation_penalty']:.2f}")
            lines.append("")
        if tone_adj:
            lines.append(f"**WARMUP tone:** {_DEFAULT_WARMUP_TONE} → {adj['warmup_tone']}")
            lines.append("")

    # History summary
    history = adj.get("history", [])
    if history:
        lines.append(f"**Применено корректировок:** {len(history)} запусков")
        last = history[-1]
        lines.append(f"**Последний:** {last['timestamp'][:16].replace('T', ' ')} UTC — {len(last['applied_ids'])} записей")
    else:
        lines.append("Корректировок ещё не применялось.")
    return "\n".join(lines)


def reset_adjustments() -> str:
    """Reset to defaults (keep history)."""
    adj = _load_adjustments()
    adj["product_weights"] = deepcopy(_DEFAULT_PRODUCT_WEIGHTS)
    adj["litigation_penalty"] = _DEFAULT_LITIGATION_PENALTY
    adj["warmup_tone"] = _DEFAULT_WARMUP_TONE
    adj["history"].append({
        "run_id": secrets.token_hex(6),
        "applied_ids": [],
        "skipped": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "reset_to_defaults",
    })
    _save_adjustments(adj)
    return "✅ Сброс к значениям по умолчанию (история сохранена)."


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FEEDBACK APPLIER: adjust pipeline from feedback")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--learn", action="store_true", help="manual: apply ALL pending entries")
    group.add_argument("--dry-run", action="store_true", help="preview adjustments without saving")
    group.add_argument("--status", action="store_true", help="show current adjustments")
    group.add_argument("--reset", action="store_true", help="reset to defaults")
    args = parser.parse_args()

    if args.status:
        print(get_status())
    elif args.reset:
        print(reset_adjustments())
    elif args.learn:
        print(apply_feedback(time_window_hours=99999, dry_run=args.dry_run))
    else:
        print(apply_feedback(time_window_hours=24, dry_run=args.dry_run))
