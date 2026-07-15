#!/usr/bin/env python3
"""WARMUP pipeline — персонализированные письма прогрева для компаний с 100% уверенностью.

Берёт JSON-выход ANALYST, фильтрует только тех у кого хотя бы один продукт >= 1.0,
и генерит деловые письма для outbound-прогрева.

Usage:
    python3 warmup_pipeline.py --input-json <analyst.json>
    python3 warmup_pipeline.py --format json                 # JSON-результат
    python3 warmup_pipeline.py --top-n 5                     # ограничить число
"""
import argparse
import json
import os
import sys
from datetime import datetime

# ── Product name map ───────────────────────────────────────────────────
PRODUCT_RU = {
    "lending": "кредитование",
    "rko": "РКО",
    "leasing": "лизинг",
    "salary_project": "зарплатный проект",
    "bank_guarantee": "банковские гарантии",
    "acquiring": "эквайринг",
    "ved": "ВЭД / валютный контроль",
}

STRATEGY_META = {
    "warm_lead": {
        "label": "тёплый",
        "urgency": "24ч",
        "channel": "Звонок + email",
    },
    "nurture": {
        "label": "наблюдать",
        "urgency": "дайджест",
        "channel": "Email-кампания",
    },
    "approach_carefully": {
        "label": "осторожно",
        "urgency": "по инициативе компании",
        "channel": "Пассивное наблюдение",
    },
    "avoid": {
        "label": "избегать",
        "urgency": "—",
        "channel": "—",
    },
}


def _fmt_amount(amount) -> str:
    """Format amount as human-readable roubles string."""
    if amount is None:
        return None
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return None
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.0f} млрд ₽"
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.0f} млн ₽"
    return f"{amount:,.0f} ₽"


def _company_name_ru(name: str) -> str:
    """Format company name for letter body — add quotes for LLC/JSC."""
    name = name.strip()
    upper = name.upper()
    if upper.startswith(("ООО ", "ЗАО ", "ОАО ", "АО ", "ПАО ")):
        parts = name.split(" ", 1)
        if len(parts) == 2:
            return f"{parts[0]} «{parts[1]}»"
    return name


def _generate_subject(company: str, product_ru: str, strategy: str) -> str:
    # Use nominative for product to avoid dative/prenominal case issues.
    # "Предложим {product} для {company}" — always grammatically correct.
    cap_product = product_ru[0].upper() + product_ru[1:] if product_ru else "Сотрудничество"
    if strategy == "warm_lead":
        return f"Предложим {cap_product} для {company}"
    return f"Сотрудничество с {company} — {cap_product}"


def _build_event_sentence(event_desc: str, amount, event_type: str = "") -> str:
    """Turn raw event data into a natural sentence a manager would say.

    event_type is authoritative — when available it drives the template,
    and event_desc is only a fallback for unknown types.
    """
    amt = _fmt_amount(amount)
    etype = (event_type or "").strip().lower()

    # Known event types — always override raw description, use plural "закупках"
    if etype == "new_procurement":
        if amt:
            return f"Мы видим, что компания участвует в закупках на сумму {amt}. Это открывает возможности для сотрудничества — можем помочь с финансированием контракта и банковскими гарантиями."
        return f"Мы заметили, что компания участвует в закупочных процедурах. Хотели бы обсудить, как Сбербанк может помочь в работе с госзаказом."

    if etype == "capital_change":
        if amt:
            return f"Мы зафиксировали, что компания изменила уставный капитал — сейчас он составляет порядка {amt}. Это сигнал о росте, и мы хотели бы предложить сервисы, которые помогут масштабировать бизнес."
        return f"Мы заметили изменения в уставном капитале компании. Хотели бы обсудить, как Сбербанк может поддержать этот рост."

    if etype == "new_company":
        return f"Компания недавно зарегистрирована — поздравляем с началом бизнеса! Сбербанк предлагает пакет для новых компаний: быстрое открытие счёта, бесплатное обслуживание первые три месяца и персональный менеджер."

    if etype == "leadership_change":
        return f"Мы заметили смену руководства. Новый управленческий цикл — хороший момент, чтобы пересмотреть условия банковского обслуживания и обсудить, что мы можем предложить."

    if etype == "hiring_surge":
        return f"Мы видим, что компания активно набирает сотрудников. Это может быть хорошим моментом, чтобы обсудить зарплатный проект — автоматизация выплат плюс бонусы для вашей команды."

    if etype == "news_mention":
        return f"Компания упоминается в деловых новостях — это признак растущей узнаваемости. Хотели бы обсудить, как Сбербанк может поддержать расширение."

    # No known event_type — fall back to raw description from _load_scout_hints
    # desc from hints is already human-readable: "участвует в закупке на сумму X"
    raw = (event_desc or "").strip()
    if not raw and not amt:
        return "Мы выделили вашу компанию как перспективного партнёра для сотрудничества со Сбербанком."
    if amt and not raw:
        return f"Мы заметили, что компания работает с контрактами на сумму порядка {amt} — это хороший сигнал для начала диалога о банковском обслуживании."
    if amt and raw:
        return f"Мы обратили внимание: {raw} (сумма контрактов — порядка {amt}). Это открывает возможности для сотрудничества со Сбербанком."
    if raw:
        return f"Мы обратили внимание: {raw}."
    return "Мы выделили вашу компанию как перспективного партнёра для сотрудничества со Сбербанком."


def _build_value_paragraph(product_key: str, company_ru: str, event_type: str = "", amount=None) -> str:
    """Build a specific value proposition — concrete product conditions."""
    amt = _fmt_amount(amount)

    if product_key == "lending":
        if event_type == "new_procurement" and amt:
            return (
                f"При объёме контрактов в {amt} компании может понадобиться "
                f"оборотное финансирование. Мы готовы предложить кредитную линию "
                f"под обеспечение будущего контракта — без залога, рассмотрение за 3 рабочих дня."
            )
        if event_type == "capital_change" and amt:
            return (
                f"Рост капитала — хороший момент для расширения кредитных линий. "
                f"Предложим ставку ниже рыночной для компаний вашего масштаба "
                f"с объёмом операций в {amt}."
            )
        return (
            f"Для {company_ru} мы можем подготовить индивидуальное предложение "
            f"по кредитованию: ставка ниже рыночной, гибкий график, рассмотрение за 3 дня."
        )

    if product_key == "rko":
        if amt:
            return (
                f"При таких объёмах стандартный тариф невыгоден. Предложим "
                f"корпоративный пакет: ноль за первые 100 платежей, бесплатное "
                f"обслуживание первые три месяца и выделенный менеджер."
            )
        return (
            f"Предложим пакет РКО с нулевой комиссией за первые 100 платежей "
            f"и персональным менеджером."
        )

    if product_key == "bank_guarantee":
        if event_type == "new_procurement":
            return (
                f"Для участия в закупках оформим тендерные и контрактные гарантии "
                f"за 2–3 рабочих дня — без залога, минимальная комиссия."
            )
        return (
            f"Оформим банковские гарантии за 2–3 дня — "
            f"без залога, с минимальной комиссией."
        )

    if product_key == "leasing":
        return (
            f"Лизинг будет на 20–30% выгоднее прямой покупки техники. "
            f"Подготовим расчёт за один рабочий день — просто скажите, какое оборудование нужно."
        )

    if product_key == "ved":
        return (
            f"Если компания работает с иностранными контрагентами, "
            f"наш ВЭД-блок возьмёт на себя валютный контроль и документооборот."
        )

    if product_key == "salary_project":
        return (
            f"Зарплатный проект — это автоматизация выплат, "
            f"бонусы для сотрудников и бесплатное обслуживание карт."
        )

    if product_key == "acquiring":
        return (
            f"Подберём эквайринговое решение под ваш оборот — "
            f"экономия до 0,5% на комиссиях."
        )

    return f"Предложим {PRODUCT_RU.get(product_key, product_key)} на индивидуальных условиях."


def _build_closing(strategy: str) -> str:
    closings = {
        "warm_lead": (
            "Буду рад обсудить детали — предлагаю короткий звонок на 15 минут на этой неделе. "
            "Подскажите, когда вам удобно?"
        ),
        "nurture": (
            "Если тема интересна — пришлю детальную информацию по условиям. "
            "Всегда на связи!"
        ),
        "approach_carefully": (
            "Будем на связи. Если появится потребность в банковских продуктах — обращайтесь."
        ),
        "avoid": "",
    }
    return closings.get(strategy, "Давайте обсудим детали.")


def _build_justification(event_type: str, product_key: str, amount: float) -> str:
    """Concrete reason WHY we're reaching out with THIS product NOW."""
    reasons = {
        "new_procurement": {
            "bank_guarantee": f"Компания участвует в закупках на {amount:,.0f} ₽ — для обеспечения контракта нужны тендерные гарантии",
            "lending": f"Закупки на {amount:,.0f} ₽ требуют оборотного финансирования — предложим кредит под контракт",
            "rko": f"Активные закупки ({amount:,.0f} ₽) — нужен расчётный счёт с выгодными условиями для тендеров",
        },
        "capital_change": {
            "rko": f"Увеличение капитала до {amount:,.0f} ₽ — стандартный тариф РКО невыгоден, предложим корпоративный пакет",
            "lending": f"Капитал {amount:,.0f} ₽ — хороший момент для расширения кредитной линии",
        },
        "hiring_surge": {
            "salary_project": f"Штат растёт — зарплатный проект упростит payroll и привлечёт сотрудников",
            "lending": f"Рост персонала говорит об expansion — нужно финансирование масштабирования",
        },
        "investment": {
            "lending": f"Инвестиции в компанию — нужно финансирование для освоения вложений",
            "rko": f"Новые инвестиции ({amount:,.0f} ₽) — требуется управление увеличенным cashflow",
        },
        "expansion": {
            "lending": f"Компания расширяется — нужно оборотное финансирование для новых направлений",
            "leasing": f"Расширение → потребность в оборудовании/технике, предложим лизинг",
        },
    }
    type_reasons = reasons.get(event_type, {})
    return type_reasons.get(product_key, f"Компания показала позитивный сигнал ({event_type}) — {product_key} поможет в развитии")


def _build_letter(company: str, product_key: str, product_ru: str,
                  strategy: str, event_desc: str = "", amount=None, event_type: str = "",
                  rationale: str = "") -> dict:
    """Build a complete manager-ready email with justification."""
    strategy_meta = STRATEGY_META.get(strategy, STRATEGY_META["nurture"])
    company_ru = _company_name_ru(company)
    subject = _generate_subject(company_ru, product_ru, strategy)
    event_sentence = _build_event_sentence(event_desc, amount, event_type)
    value = _build_value_paragraph(product_key, company_ru, event_type=event_type, amount=amount)
    closing = _build_closing(strategy)

    # Build email body — justification paragraph comes FIRST
    body_lines = []
    if rationale:
        body_lines.append(f"**Почему мы обращаемся:** {rationale}")
        body_lines.append("")
    body_lines.extend([
        f"Добрый день!",
        "",
        f"Меня зовут [Имя Фамилия], я курирую корпоративных клиентов в Сбербанке.",
        "",
        event_sentence,
    ])
    if value:
        body_lines.append("")
        body_lines.append(value)
    if closing:
        body_lines.append("")
        body_lines.append(closing)
    body_lines.append("")
    body_lines.append("С уважением,")
    body_lines.append("[Имя Фамилия]")
    body_lines.append("Корпоративный блок • Сбербанк для бизнеса")
    body_lines.append("[телефон] • [email]")

    return {
        "subject": subject,
        "body": "\n".join(body_lines),
        "rationale": rationale,
        "strategy_label": strategy_meta["label"],
        "urgency": strategy_meta["urgency"],
        "channel": strategy_meta["channel"],
        "product_ru": product_ru,
        "product_key": product_key,
    }


def _load_profiles(input_json_path: str | None = None) -> list[dict]:
    """Load ANALYST profiles from a JSON file."""
    if not input_json_path or not os.path.isfile(input_json_path):
        return []
    with open(input_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "profiles" in data:
        return data["profiles"]
    return []


WARMUP_THRESHOLD = 0.9  # 90% confidence — lowered from 1.0 (was 100% gate)


def _filter_qualified(profiles: list[dict], threshold: float = WARMUP_THRESHOLD) -> list[dict]:
    """Keep only profiles with at least one product at score >= threshold (default 0.9 = 90%)."""
    result = []
    for p in profiles:
        heatmap = p.get("product_heatmap", [])
        top_products = [pr for pr in heatmap if pr.get("score", 0) >= threshold]
        if top_products:
            p["_top_products_qualified"] = top_products
            result.append(p)
    return result


def _normalize_company_key(name: str) -> str:
    """Normalize company name for matching — strip quotes, extra spaces, legal forms."""
    name = name.strip().strip('"').strip("'")
    # Remove common legal suffixes for fuzzy matching
    for suffix in [' ООО', ' ОАО', ' ЗАО', ' ПАО', ' АО', ' ИП']:
        name = name.replace(suffix, '')
    return name.strip()


def _load_scout_hints(store_path: str | None = None) -> dict[str, dict]:
    """Load raw scout events and create lookup by company name."""
    if not store_path or not os.path.isfile(store_path):
        return {}
    try:
        with open(store_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        events = data.get("last_result", {}).get("events", [])
        hints: dict[str, dict] = {}
        norm_map: dict[str, str] = {}  # normalized -> original name
        for ev in events:
            name = ev.get("company_name") or ev.get("company", "")
            if not name:
                continue
            norm = _normalize_company_key(name)
            if norm in norm_map:
                continue  # already have this company
            norm_map[norm] = name
            event_type = ev.get("event_type", "")
            amount = ev.get("amount") or ev.get("potential_revenue")

            # Translate machine event_type into human-readable Russian
            type_labels = {
                "new_procurement": "участвует в закупке",
                "capital_change": "изменила уставный капитал",
                "new_company": "зарегистрирована",
                "court_case": "участвует в судебном деле",
                "news_mention": "упоминается в СМИ",
                "leadership_change": "сменила руководство",
                "hiring_surge": "массово набирает сотрудников",
            }
            label = type_labels.get(event_type, event_type)

            amt_str = _fmt_amount(amount)
            if amt_str:
                desc = f"{label} на сумму {amt_str}"
            else:
                desc = label.lower() if label else ""

            hints[name] = {
                "description": desc,
                "amount": amount,
                "max_amount": amount,
                "event_type": event_type,
            }
        return hints
    except (json.JSONDecodeError, KeyError):
        return {}


def run(
    input_json: str | None = None,
    scout_store: str | None = None,
    top_n: int = 50,
    fmt: str = "text",
    threshold: float = WARMUP_THRESHOLD,
) -> str:
    """Main WARMUP entry point."""
    profiles = _load_profiles(input_json)
    qualified = _filter_qualified(profiles, threshold=threshold)

    if not qualified:
        pct = int(threshold * 100)
        return f"WARMUP: нет компаний с уверенностью ≥{pct}% — пропуск шага."

    scout_hints = _load_scout_hints(scout_store)
    limited = qualified[:top_n]

    if fmt == "json":
        out_profiles = []
        for p in limited:
            company = p["company_name"]
            top = p["_top_products_qualified"][0]
            product_key = top["product"]
            product_ru = PRODUCT_RU.get(product_key, product_key)
            strategy = p.get("entry_scenario", {}).get("approach", "nurture")
            # Try exact match first, then normalized
            hint = scout_hints.get(company, {})
            if not hint:
                norm = _normalize_company_key(company)
                for scout_name, scout_hint in scout_hints.items():
                    if _normalize_company_key(scout_name) == norm:
                        hint = scout_hint
                        break
            rationale = p.get("entry_scenario", {}).get("rationale", "")
            letter = _build_letter(
                company=company,
                product_key=product_key,
                product_ru=product_ru,
                strategy=strategy,
                event_desc=hint.get("description", ""),
                amount=hint.get("amount") or hint.get("max_amount"),
                event_type=hint.get("event_type", ""),
                rationale=rationale,
            )
            out_profiles.append({
                "company_name": company,
                "company_id": p.get("company_id"),
                "top_products_qualified": [
                    {"product": pr["product"], "product_ru": PRODUCT_RU.get(pr["product"], pr["product"]),
                     "score": pr["score"], "estimated_revenue": pr.get("estimated_revenue")}
                    for pr in p["_top_products_qualified"]
                ],
                "strategy": strategy,
                "letter": letter,
            })
        return json.dumps({"count": len(out_profiles), "warmup_templates": out_profiles}, ensure_ascii=False, indent=2)

    # Text/Markdown output
    pct = int(threshold * 100)
    lines = []
    lines.append(f"## WARMUP — письма прогрева ({len(limited)} компаний с уверенностью ≥{pct}%)")
    lines.append("")
    lines.append("| # | Компания | Продукт | Уверенность | Стратегия | Срочность |")
    lines.append("|---|----------|---------|-------------|-----------|-----------|")

    for i, p in enumerate(limited, 1):
        company = p["company_name"]
        top_p = p["_top_products_qualified"][0]
        product_ru = PRODUCT_RU.get(top_p["product"], top_p["product"])
        strategy = p.get("entry_scenario", {}).get("approach", "nurture")
        meta = STRATEGY_META.get(strategy, STRATEGY_META["nurture"])
        lines.append(f"| {i} | {company} | {product_ru} | {top_p['score']*100:.0f}% | {meta['label']} | {meta['urgency']} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Render individual letters
    for p in limited:
        company = p["company_name"]
        top_p = p["_top_products_qualified"][0]
        product_key = top_p["product"]
        product_ru = PRODUCT_RU.get(product_key, product_key)
        strategy = p.get("entry_scenario", {}).get("approach", "nurture")
        # Try exact match first, then normalized
        hint = scout_hints.get(company, {})
        if not hint:
            norm = _normalize_company_key(company)
            for scout_name, scout_hint in scout_hints.items():
                if _normalize_company_key(scout_name) == norm:
                    hint = scout_hint
                    break

        letter = _build_letter(
            company=company,
            product_key=product_key,
            product_ru=product_ru,
            strategy=strategy,
            event_desc=hint.get("description", ""),
            amount=hint.get("amount") or hint.get("max_amount"),
            event_type=hint.get("event_type", ""),
        )

        lines.append(f"### 📩 {company}")
        lines.append(f"**Тема:** {letter['subject']}")
        lines.append("")
        lines.append("```")
        lines.append(letter["body"])
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WARMUP: outbound outreach letters")
    parser.add_argument("--input-json", type=str, default=None, help="JSON file from analyst run")
    parser.add_argument("--scout-store", type=str, default=None, help="pipeline_store.json for event hints")
    parser.add_argument("--top-n", type=int, default=50, help="max letters")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--threshold", type=float, default=WARMUP_THRESHOLD,
                        help=f"confidence threshold (default {WARMUP_THRESHOLD} = {int(WARMUP_THRESHOLD*100)}%)")
    args = parser.parse_args()

    result = run(
        input_json=args.input_json,
        scout_store=args.scout_store,
        top_n=args.top_n,
        fmt=args.format,
        threshold=args.threshold,
    )
    print(result)
