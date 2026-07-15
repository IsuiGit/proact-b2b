"""
ANALYST pipeline — standalone script (no skill, no review gates).

Takes SCOUT JSON output and produces company risk profiles, product
heat-maps, and entry scenarios.

Usage:
    python3 analyst_pipeline.py                   # reads pipeline_store.json, outputs Markdown
    python3 analyst_pipeline.py --format json     # outputs JSON for chaining
    python3 analyst_pipeline.py --input file.json # read from file instead of pipeline_store.json
    python3 analyst_pipeline.py --top-n 10        # limit output to top N
"""
import argparse
import json
import os
import sys
from typing import Any

# Ensure Deliverables dir is on path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyst_output import format_as_json, format_as_markdown

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_INPUT = os.path.join(_REPO_ROOT, "data", "sberbank_pipeline", "pipeline_store.json")

PRODUCTS = [
    "rko",            "lending",        "leasing",
    "salary_project", "ved",            "bank_guarantee",
    "acquiring",
]

# Event type → (product_slug, base_score, bank_margin_bps)
# margin_bps = estimated bank margin in basis points on the deal
EVENT_PRODUCT_MAP = {
    "new_procurement": [
        ("bank_guarantee", 0.85, 150),
        ("lending",        0.60, 250),
        ("rko",            0.30,  50),
    ],
    "capital_change": [
        ("lending",        0.70, 250),
        ("rko",            0.50,  50),
        ("leasing",        0.40, 120),
    ],
    "new_registration": [
        ("rko",            0.90,  50),
        ("salary_project", 0.30,  30),
        ("acquiring",      0.20,  25),
    ],
    "expansion": [
        ("lending",        0.75, 250),
        ("salary_project", 0.60,  30),
        ("leasing",        0.50, 120),
        ("rko",            0.30,  50),
    ],
    "ipo_announcement": [
        ("ved",            0.60, 200),
        ("rko",            0.50,  50),
        ("lending",        0.40, 250),
    ],
    "investment": [
        ("lending",        0.65, 250),
        ("rko",            0.40,  50),
        ("ved",            0.30, 200),
    ],
    "merger_acquisition": [
        ("lending",        0.80, 250),
        ("ved",            0.60, 200),
        ("rko",            0.40,  50),
    ],
    "contract_signed": [
        ("bank_guarantee", 0.70, 150),
        ("lending",        0.50, 250),
        ("rko",            0.30,  50),
    ],
    "court_case": [],
    "bankruptcy": [],
    "liquidation": [],
    "news_mention": [
        ("rko", 0.10, 50),
    ],
}

POSITIVE_EVENTS = {
    "new_procurement", "capital_change", "new_registration",
    "expansion", "ipo_announcement", "investment", "merger_acquisition",
    "contract_signed",
}
NEGATIVE_EVENTS = {"court_case", "bankruptcy", "liquidation"}

# ---------------------------------------------------------------------------
# Risk profile — revenue-weighted, event-type aware
# ---------------------------------------------------------------------------
def compute_risk_profile(events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Revenue-weighted risk profile.

    Positive revenue (procurements, capital increases) and negative exposure
    (court claims, bankruptcy risks) are summed separately, then compared.
    A company with 1 court on 500M of procurements ≠ a company with 10
    courts and nothing else.
    """
    positive_revenue = 0.0
    negative_exposure = 0.0
    court_amounts: list[float] = []
    flags: list[str] = []
    event_types: list[str] = []
    positive_count = 0
    negative_count = 0

    for ev in events:
        et = ev.get("event_type", "")
        rev = float(ev.get("potential_revenue", 0) or 0)
        weight = float(ev.get("weight", 1.0) or 1.0)
        event_types.append(et)

        if et in POSITIVE_EVENTS:
            positive_revenue += rev * (weight / 7.0)
            positive_count += 1
        elif et == "court_case":
            court_amounts.append(rev)
            negative_exposure += rev * 1.5   # courts × 1.5 — потенциальная ответственность
            negative_count += 1
        elif et in ("bankruptcy", "liquidation"):
            negative_exposure += rev * 2.0   # банкротство/ликвидация — максимальный риск
            negative_count += 1
        else:
            # news_mention, capital_change и т.д. без суммы
            if et not in NEGATIVE_EVENTS:
                positive_count += 1

    # Net signal = weighted positive minus weighted negative
    total = positive_revenue + negative_exposure
    if total > 0:
        health_ratio = (positive_revenue - negative_exposure) / total
    else:
        health_ratio = 0.0  # no data

    if health_ratio >= 0.6:
        level, label = "low", "Низкий риск"
    elif health_ratio >= 0.2:
        level, label = "moderate", "Умеренный риск"
    elif health_ratio >= -0.2:
        # Neutral: no negative exposure, just weak/no signal
        if negative_exposure == 0 and positive_revenue == 0:
            level, label = "neutral", "Нет данных"
        else:
            level, label = "high", "Высокий риск"
    else:
        level, label = "very_high", "Критический риск"

    # Flags
    if court_amounts:
        flags.append(f"Судебные дела: {len(court_amounts)}, сумма ~{int(sum(court_amounts)):,} ₽")
    if any(e == "bankruptcy" for e in event_types):
        flags.append("Признаки банкротства")
    if any(e == "liquidation" for e in event_types):
        flags.append("Ликвидация")

    return {
        "level": level,
        "label": label,
        "health_ratio": round(health_ratio, 2),
        "positive_revenue": round(positive_revenue),
        "negative_exposure": round(negative_exposure),
        "court_count": len(court_amounts),
        "negative_signals": negative_count,
        "positive_signals": positive_count,
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# Product heatmap — revenue-scaled with bank margin estimation
# ---------------------------------------------------------------------------
def compute_product_heatmap(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Map events to bank products.

    Score = sum(base_score × weight/7 × log(revenue_scale)) per event.
    Also estimates potential_bank_revenue (₽) for prioritization.
    """
    product_scores: dict[str, float] = {p: 0.0 for p in PRODUCTS}
    product_revenue: dict[str, float] = {p: 0.0 for p in PRODUCTS}

    for ev in events:
        et = ev.get("event_type", "news_mention")
        weight = float(ev.get("weight", 1.0) or 1.0)
        rev = float(ev.get("potential_revenue", 0) or 0)
        signals = EVENT_PRODUCT_MAP.get(et, [])

        revenue_scale = 1.0
        if rev > 0:
            # log scale: 1M→1, 100M→1.5, 1B→2
            import math
            revenue_scale = 1.0 + 0.5 * math.log10(max(rev / 1_000_000, 1.0))

        for product_slug, base, margin_bps in signals:
            scaled = base * (weight / 7.0) * revenue_scale
            product_scores[product_slug] = min(1.0, product_scores[product_slug] + scaled)
            if rev > 0:
                product_revenue[product_slug] += rev * (margin_bps / 10_000)

    heatmap = []
    for p in PRODUCTS:
        score = product_scores[p]
        if score < 0.05:
            continue
        entry: dict[str, Any] = {"product": p, "score": round(score, 2)}
        if product_revenue[p] > 0:
            entry["estimated_revenue"] = round(product_revenue[p])
        heatmap.append(entry)

    heatmap.sort(key=lambda x: x["score"], reverse=True)
    return heatmap


# ---------------------------------------------------------------------------
# Entry scenario — event-driven openers with hooks
# ---------------------------------------------------------------------------
_OPENERS = {
    "new_procurement": (
        "Компания участвует в закупках на {amount:,} ₽ — предложить тендерные гарантии "
        "и оборотное кредитование под контракт"
    ),
    "capital_change": (
        "Компания меняет уставный капитал ({amount:,} ₽) — обсудить расширение кредитной линии "
        "и условия РКО"
    ),
    "expansion": (
        "Компания расширяется — предложить кредит на развитие, лизинг и зарплатный проект"
    ),
    "ipo_announcement": (
        "Компания готовится к IPO — предложить ВЭД-сопровождение и инвестиционное обслуживание"
    ),
    "new_registration": (
        "Новая компания — предложить пакет РКО + зарплатный проект для старта"
    ),
    "investment": (
        "Привлечение инвестиций ({amount:,} ₽) — предложить обслуживание расчётного счёта "
        "и кредитную линию"
    ),
    "merger_acquisition": (
        "Слияние/поглощение — предложить финансирование сделки и ВЭД-сопровождение"
    ),
    "contract_signed": (
        "Подписан контракт на {amount:,} ₽ — предложить гарантию исполнения и факторинг"
    ),
}

def _gen_opener(top_product: str, events: list[dict], risk_label: str) -> str:
    """Generate opener tied to the highest-signal event."""
    # Find the best event to hook onto (positive, with amount if possible)
    best_ev = None
    for ev in events:
        if ev.get("event_type") in POSITIVE_EVENTS:
            if best_ev is None or ev.get("potential_revenue", 0) > best_ev.get("potential_revenue", 0):
                best_ev = ev

    if best_ev:
        et = best_ev["event_type"]
        amount = float(best_ev.get("potential_revenue", 0) or 0)
        template = _OPENERS.get(et)
        if template:
            return template.format(amount=amount)

    # Fallback: product-based opener
    product_openers = {
        "rko": "Предложить выгодные условия РКО",
        "lending": "Обсудить кредитную линию под текущие проекты",
        "leasing": "Предложить лизинг оборудования с субсидированной ставкой",
        "salary_project": "Рассказать о зарплатном проекте с кэшбэком",
        "ved": "Предложить ВЭД-сопровождение и аккредитивы",
        "bank_guarantee": "Предложить тендерные гарантии на выгодных условиях",
        "acquiring": "Обсудить эквайринг с пониженной комиссией",
    }
    return product_openers.get(top_product, "Предложить общее банковское обслуживание")


def compute_entry_scenario(risk: dict, heatmap: list[dict], events: list[dict]) -> dict[str, Any]:
    """Generate approach strategy with rationale and event-driven opener."""
    level = risk.get("level", "moderate")
    risk_label = risk.get("label", "Умеренный риск")
    top_product = heatmap[0]["product"] if heatmap else ""

    # Too much negative — avoid
    if level == "very_high" and risk.get("court_count", 0) > 2:
        return {
            "approach": "avoid",
            "rationale": f"Много судебных дел (risk: {risk_label}) — высокий риск контрагента",
            "opener": None,
        }

    # Very risky but not yet critical — approach with caution
    if level in ("very_high", "high"):
        flags_text = "; ".join(risk.get("flags", [])) or risk_label
        return {
            "approach": "approach_carefully",
            "rationale": f"Риски перевешивают позитив ({flags_text})",
            "opener": None,
        }

    # Neutral — no data yet, just watch
    if level == "neutral":
        return {
            "approach": "nurture",
            "rationale": "Событий без денежного сигнала — наблюдать",
            "opener": None,
        }

    # Low risk with clear product fit — warm lead
    if level in ("low", "moderate") and heatmap:
        total_revenue = risk.get("positive_revenue", 0)
        if total_revenue > 100_000_000:
            approach = "warm_lead"
            rationale = (
                f"Компания растёт, позитив {int(total_revenue):,} ₽ — "
                f"подходит {_product_name(top_product)} с уверенностью {heatmap[0]['score']:.0%}"
            )
        else:
            approach = "nurture"
            rationale = (
                f"Компания активна, но суммы небольшие — {_product_name(top_product)} "
                f"возможен при дальнейшем росте"
            )
        return {
            "approach": approach,
            "rationale": rationale,
            "opener": _gen_opener(top_product, events, risk_label),
        }

    return {
        "approach": "nurture",
        "rationale": "Недостаточно данных для активного захода",
        "opener": None,
    }


def _product_name(slug: str) -> str:
    names = {
        "rko": "РКО", "lending": "Кредитование", "leasing": "Лизинг",
        "salary_project": "Зарплатный проект", "ved": "ВЭД/FX",
        "bank_garantee": "Банковские гарантии", "acquiring": "Эквайринг",
    }
    return names.get(slug, slug)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_analyst(input_path: str, top_n: int, fmt: str) -> str:
    """Load SCOUT data → analyze → format → return string."""
    if not os.path.isfile(input_path):
        return f"[ANALYST] Input file not found: {input_path}"

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "last_result" in data and isinstance(data["last_result"], dict):
        events = data["last_result"].get("events", [])
    else:
        events = data.get("events", [])
    if not events:
        return "[ANALYST] No events to analyze."

    # Group events by company
    companies: dict[str, list[dict]] = {}
    for ev in events:
        cid = ev.get("company_id", "unknown")
        companies.setdefault(cid, []).append(ev)

    profiles = []
    for cid, c_events in companies.items():
        name = c_events[0].get("company_name", "Неизвестная компания")
        if cid == "unknown" or name == "Неизвестная компания":
            continue

        risk = compute_risk_profile(c_events)
        heatmap = compute_product_heatmap(c_events)
        scenario = compute_entry_scenario(risk, heatmap, c_events)

        # Overall score: revenue-scaled signal minus risk penalty, 0-10
        pos_rev = risk["positive_revenue"]
        neg_exp = risk["negative_exposure"]
        # 100M+ → base 7, 10M → 4, 1M → 2, scaled logarithmically
        import math
        if pos_rev > 0:
            base = 2.0 + 5.0 * math.log10(max(pos_rev / 1_000_000, 1.0))
        else:
            base = 1.0
        # Penalty proportional to negative exposure
        if neg_exp > 0:
            penalty = min(5, neg_exp / 50_000_000)
        else:
            penalty = 0
        raw = base - penalty
        overall = min(10, max(0, round(raw)))

        profiles.append({
            "company_id": cid,
            "company_name": name,
            "risk_profile": risk,
            "product_heatmap": heatmap,
            "entry_scenario": scenario,
            "overall_score": overall,
            "event_count": len(c_events),
        })

    # Sort by overall_score desc, "Неизвестная компания" always last
    profiles.sort(key=lambda p: (
        0 if p["company_name"] != "Неизвестная компания" else -1,
        p["overall_score"],
    ), reverse=True)

    if fmt == "json":
        return format_as_json(profiles)
    return format_as_markdown(profiles, top_n=top_n)


def main() -> None:
    parser = argparse.ArgumentParser(description="ANALYST pipeline")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--top-n", type=int, default=50)
    args = parser.parse_args()
    result = run_analyst(args.input, args.top_n, args.format)
    print(result)


if __name__ == "__main__":
    main()
