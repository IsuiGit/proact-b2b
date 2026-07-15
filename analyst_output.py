"""
ANALYST pipeline — output formatter.

Outputs:
  --format json   → machine-readable JSON for chaining
  --format text   → human-readable Markdown table for chat
"""
import json
from typing import Any


def format_as_json(profiles: list[dict[str, Any]]) -> str:
    """Full profiles as indented JSON."""
    return json.dumps({"count": len(profiles), "profiles": profiles}, ensure_ascii=False, indent=2)


def format_as_markdown(profiles: list[dict[str, Any]], top_n: int = 50) -> str:
    """Top-N profiles as Markdown table for chat display."""
    lines = [
        "| # | Компания | Риск | Стратегия | Топ-продукт | Уверенность |",
        "|---|----------|------|-----------|-------------|-------------|",
    ]
    for i, p in enumerate(sorted(profiles, key=lambda x: x.get("overall_score", 0), reverse=True)[:top_n], 1):
        risk = _risk_emoji(p.get("risk_profile", {}))
        strategy = _strategy_brief(p.get("entry_scenario", {}))
        top_product = _top_product(p.get("product_heatmap", []))
        confidence = f"{top_product['confidence']:.0%}" if top_product else "—"
        product_name = top_product["product"] if top_product else "—"
        lines.append(f"| {i} | {p['company_name']} | {risk} | {strategy} | {product_name} | {confidence} |")
    return "\n".join(lines)


# --- internals ---

_RISK_MAP = {
    "very_low": "✅",
    "low": "🟢",
    "neutral": "⚪",
    "moderate": "🟡",
    "high": "🟠",
    "very_high": "🔴",
}

_STRATEGY_MAP = {
    "warm_lead": "тёплый",
    "approach_carefully": "осмотрительно",
    "nurture": "наблюдать",
    "avoid": "избегать",
}

_PRODUCT_NAMES = {
    "rko": "РКО",
    "lending": "Кредитование",
    "leasing": "Лизинг",
    "salary_project": "Зарплатный проект",
    "ved": "ВЭД/FX",
    "bank_guarantee": "Банковские гарантии",
    "acquiring": "Эквайринг",
}


def _risk_emoji(profile: dict[str, Any]) -> str:
    level = profile.get("level", "moderate")
    return _RISK_MAP.get(level, "❓")


def _strategy_brief(scenario: dict[str, Any]) -> str:
    key = scenario.get("approach", "nurture")
    return _STRATEGY_MAP.get(key, "—")


def _top_product(heatmap: list[dict[str, Any]]) -> dict[str, Any]:
    if not heatmap:
        return {}
    best = max(heatmap, key=lambda x: x.get("score", 0))
    slug = best.get("product", "")
    return {"product": _PRODUCT_NAMES.get(slug, slug), "confidence": best.get("score", 0)}
