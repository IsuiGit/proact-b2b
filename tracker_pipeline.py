#!/usr/bin/env python3
"""TRACKER pipeline — фиксация результатов контактов и воронка продаж.

Хранит историю interactions, фильтрует повторные контакты WARMUP,
показывает конверсионную воронку SCOUT → ANALYST → WARMUP → TRACKER.

Использование:
    # Показать воронку
    python3 tracker_pipeline.py

    # Зафиксировать результат контакта
    python3 tracker_pipeline.py --result "ООО ВолгаТрейд" contacted
    python3 tracker_pipeline.py --result "ПАО Татнефть" declined
    python3 tracker_pipeline.py --result "ООО СтройМастер" in_progress
    python3 tracker_pipeline.py --result "ЗАО ФармДистрибьюшен" closed

    # JSON-вывод
    python3 tracker_pipeline.py --format json

    # Использовать в pipeline (фильтрация + воронка)
    python3 tracker_pipeline.py --warmup-targets company1,company2 --format text
"""
import argparse
import json
import os
import sys
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PIPELINE_STORE = os.path.join(_SCRIPT_DIR, "pipeline_store.json")

_TRACKER_STORE = os.path.join(_SCRIPT_DIR, "tracker_store.json")

# ── Status constants ───────────────────────────────────────────────
STATUS_CONTACTED = "contacted"      # Связались, ждём ответ
STATUS_INTERESTED = "interested"    # Проявили интерес
STATUS_NOT_INTERESTED = "not_interested"  # Не интересно / отказ
STATUS_DEAL = "deal"                # Сделка закрыта
STATUS_NO_RESPONSE = "no_response"  # Нет ответа

_STATUS_LABELS = {
    STATUS_CONTACTED: "связались",
    STATUS_INTERESTED: "заинтересованы",
    STATUS_NOT_INTERESTED: "отказ",
    STATUS_DEAL: "сделка",
    STATUS_NO_RESPONSE: "нет ответа",
}


def _load_tracker() -> dict:
    """Загрузить историю контактов."""
    if os.path.exists(_TRACKER_STORE):
        with open(_TRACKER_STORE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"contacts": {}}


def _save_tracker(store: dict) -> None:
    """Сохранить историю контактов."""
    with open(_TRACKER_STORE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def _clean_name(name: str) -> str:
    """Нормализовать имя компании — убрать кавычки, пробелы, привести к единому виду."""
    name = name.strip()
    name = name.replace('\u00ab"', '\u00ab').replace('"\u00bb', '\u00bb').replace('""', '')
    return name


def record_contact(company: str, status: str, product: str = None, analyst_info: dict = None) -> dict:
    """Зафиксировать результат контакта с компанией."""
    store = _load_tracker()
    company = _clean_name(company)
    
    entry = store["contacts"].get(company, {
        "company": company,
        "history": [],
        "last_status": None,
        "product": product,
        "analyst_info": analyst_info or {},
    })
    
    entry["history"].append({
        "status": status,
        "timestamp": datetime.now().isoformat(),
    })
    entry["last_status"] = status
    
    if product:
        entry["product"] = product
    
    store["contacts"][company] = entry
    _save_tracker(store)
    
    return entry


def should_warmup(company: str) -> bool:
    """Проверить — нужно ли прогревать компанию (нет ли уже контакта)."""
    store = _load_tracker()
    company = _clean_name(company)
    return company not in store["contacts"]


def get_filtered_warmup_targets(analyst_profiles: list) -> list:
    """Отфильтровать компании для WARMUP — убрать уже контактированные."""
    store = _load_tracker()
    contacted = set(store["contacts"].keys())
    
    return [p for p in analyst_profiles if _clean_name(p.get("company_name", "")) not in contacted]


def format_funnel(top_n: int = 50) -> str:
    """Сформировать Markdown-воронку контактов."""
    store = _load_tracker()
    contacts = store["contacts"]
    
    if not contacts:
        return "Зарегистрированных контактов пока нет\n"
    
    # Группировка по статусам
    by_status = {}
    for entry in contacts.values():
        status = entry.get("last_status", "unknown")
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(entry)
    
    lines = []
    lines.append("## TRACKER — воронка контактов")
    lines.append("")
    
    # Сводка
    lines.append(f"**Всего компаний в работе:** {len(contacts)}")
    lines.append("")
    
    lines.append("| Статус | Кол-во |")
    lines.append("|--------|--------|")
    for status, label in _STATUS_LABELS.items():
        count = len(by_status.get(status, []))
        lines.append(f"| {label} | {count} |")
    
    unknown = by_status.get("unknown", [])
    if unknown:
        lines.append(f"| неизвестно | {len(unknown)} |")
    lines.append("")
    
    # Таблица всех контактов (топ-N)
    all_entries = list(contacts.values())
    all_entries.sort(key=lambda x: x["history"][-1]["timestamp"] if x["history"] else "", reverse=True)
    all_entries = all_entries[:top_n]
    
    lines.append("| # | Компания | Последний статус | Продукт | Дата |")
    lines.append("|---|----------|-----------------|---------|------|")
    
    for i, entry in enumerate(all_entries, 1):
        company = entry["company"]
        last_status = entry.get("last_status", "\u2014")
        status_label = _STATUS_LABELS.get(last_status, last_status)
        product = entry.get("product", "\u2014")
        
        last_date = "\u2014"
        if entry["history"]:
            ts = entry["history"][-1].get("timestamp", "")
            if ts:
                last_date = datetime.fromisoformat(ts).strftime("%d.%m.%Y %H:%M")
        
        lines.append(f"| {i} | {company} | {status_label} | {product} | {last_date} |")
    
    lines.append("")
    return "\n".join(lines)


def format_as_json() -> str:
    """JSON-вывод воронки."""
    store = _load_tracker()
    result = {
        "total_contacts": len(store["contacts"]),
        "by_status": {},
        "recent_contacts": [],
    }
    
    # by_status
    by_status = {}
    for entry in store["contacts"].values():
        status = entry.get("last_status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1
    result["by_status"] = by_status
    
    # recent (last 10)
    all_entries = sorted(
        store["contacts"].values(),
        key=lambda x: x["history"][-1]["timestamp"] if x["history"] else "",
        reverse=True
    )[:10]
    
    for entry in all_entries:
        result["recent_contacts"].append({
            "company": entry["company"],
            "last_status": entry.get("last_status"),
            "product": entry.get("product"),
            "last_contact_date": entry["history"][-1]["timestamp"] if entry["history"] else None,
            "contact_count": len(entry["history"]),
        })
    
    return json.dumps(result, ensure_ascii=False, indent=2)


def process_warmup_results(warmup_targets: list) -> dict:
    """Обработать результаты WARMUP — фильтровать уже контактированных.
    
    Args:
        warmup_targets: Список компаний, прошедших WARMUP-фильтр (100% уверенность).
    
    Returns:
        dict с filtered_targets (новые) и skipped (уже контактированные).
    """
    store = _load_tracker()
    contacted = set(store["contacts"].keys())
    
    filtered = []
    skipped = []
    
    for target in warmup_targets:
        company_name = target.get("company_name", target.get("company", ""))
        company_name = _clean_name(company_name)
        
        if company_name in contacted:
            skipped.append(target)
        else:
            filtered.append(target)
    
    return {
        "filtered": filtered,
        "skipped": skipped,
        "new_count": len(filtered),
        "skipped_count": len(skipped),
    }


def run(warmup_targets: list = None, format_type: str = "text", top_n: int = 50) -> str:
    """Запустить TRACKER — воронку и/или фильтрацию WARMUP.
    
    Args:
        warmup_targets: Если переданы — отфильтровать уже контактированных.
        format_type: "text" или "json".
        top_n: Максимальное число записей в таблице.
    
    Returns:
        Markdown или JSON строка.
    """
    if warmup_targets is not None:
        result = process_warmup_results(warmup_targets)
        lines = []
        lines.append("## TRACKER — фильтрация WARMUP")
        lines.append("")
        lines.append(f"**{result['new_count']}** новых компаний для прогрева, "
                      f"**{result['skipped_count']}** уже в работе (пропускаем).")
        lines.append("")
        
        if result["new_count"] > 0:
            lines.append("**Новые (прогреваем):**")
            for t in result["filtered"]:
                company = t.get("company_name", t.get("company", "\u2014"))
                product = t.get("product", "\u2014")
                lines.append(f"- {company} \u2192 {product}")
            lines.append("")
        
        if result["skipped_count"] > 0:
            lines.append("**В работе (пропускаем):**")
            for t in result["skipped"]:
                company = t.get("company_name", t.get("company", "\u2014"))
                store = _load_tracker()
                last_status = store["contacts"].get(company, {}).get("last_status", "\u2014")
                status_label = _STATUS_LABELS.get(last_status, last_status)
                lines.append(f"- {company} ({status_label})")
            lines.append("")
    
    # Всегда показываем воронку
    if format_type == "json":
        return format_as_json()
    else:
        return format_funnel(top_n=top_n)


def main():
    parser = argparse.ArgumentParser(description="TRACKER pipeline — воронка контактов")
    parser.add_argument("--result", nargs=2, metavar=("COMPANY", "STATUS"),
                        help="Зафиксировать результат: <company> <status>")
    parser.add_argument("--warmup-targets", type=str,
                        help="Список компаний для фильтрации (через запятую)")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--top-n", type=int, default=50, help="Максимум записей в таблице")
    args = parser.parse_args()
    
    # Режим: зафиксировать результат контакта
    if args.result:
        company, status = args.result
        product = args.product if hasattr(args, 'product') else None
        entry = record_contact(company, status, product)
        label = _STATUS_LABELS.get(status, status)
        print(f"Зафиксировано: {company} \u2192 {label}")
        print(f"Всего контактов: {len(entry['history'])}")
        return
    
    # Режим: фильтрация WARMUP
    if args.warmup_targets:
        companies = [c.strip() for c in args.warmup_targets.split(",")]
        targets = [{"company_name": c, "product": "", "analyst_info": {}} for c in companies]
        result = run(warmup_targets=targets, format_type=args.format, top_n=args.top_n)
        print(result)
        return
    
    # Режим: воронка
    result = run(format_type=args.format, top_n=args.top_n)
    print(result)


if __name__ == "__main__":
    main()