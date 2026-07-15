# Sberbank B2B Pipeline — Run & Delivery Guide

## Что это

Пять стадий: SCOUT → ANALYST → WARMUP → BRIEF → TRACKER.
Одна команда: `python3 pipeline_runner.py`.

## Как запускать

```bash
# Полный прогон
python3 pipeline_runner.py

# Применить накопленную обратную связь (обновить веса и тон рассылок)
python3 pipeline_runner.py --learn

# Порог WARMUP по умолчанию: 90%
python3 pipeline_runner.py --threshold 0.95
```

## Как ВЫВОДИТЬ результаты (ПРОТОКОЛ — не забыть И нельзя обойти!)

Один turn агента = одно сообщение в чате. Это фундаментальное ограничение.  
Поэтому каждая стадия ДОСТАВЛЯЕТСЯ через `send_user_message` — 6 отдельных сообщений:

1. **SCOUT** → `read_file(data/task_drive/pipeline_output/scout.md)` → `send_user_message(content)` — полная таблица, без сокращений
2. **ANALYST** → `read_file(analyst.md)` → `send_user_message` — полные профили
3. **WARMUP** → `read_file(warmup.md)` → `send_user_message` — все письма целиком
4. **BRIEF** → `read_file(brief.md)` → `send_user_message` — все досье целиком
5. **TRACKER** → `read_file(tracker.md)` → `send_user_message` — воронка (или "Зарегистрированных контактов пока нет" без объяснений)
6. **Feedback** → `send_user_message("📝 Жду обратную связь по результатам...")` — блок с инструкциями

**ПРАВИЛА (без исключений):**
- НИКАКИХ комментариев между блоками
- НИКАКИХ сокращений — содержимое файла выводится целиком
- НИКАКИХ объединений в одно сообщение
- `send_user_message` — ЕДИНСТВЕННЫЙ механизм, дающий видимые отдельные сообщения в чате (subagents, print, один большой ответ = один пузырь = ОШИБКА)
- TRACKER пустой: вывести "Зарегистрированных контактов пока нет" — без пояснений почему

## Требования

Python 3.8+, `requests` (для SCOUT fetchers).

## Архитектура

| Файл | Роль |
|------|------|
| `scout_pipeline.py` | Агрегатор лидов (7+ источников, моки+реальные API) |
| `analyst_pipeline.py` | Risk-scoring, product heat-map |
| `warmup_pipeline.py` | Персонализированные email-шаблоны |
| `brief_pipeline.py` | Досье перед встречей |
| `tracker_pipeline.py` | Журнал контактов + воронка |
| `feedback_pipeline.py` | Хранилище обратной связи |
| `feedback_applier.py` | Модуль корректировки весов/тона |
| `pipeline_runner.py` | Оркестратор (цепочка + двойной формат: JSON + Markdown) |
| `analyst_output.py` | Markdown-таблицы и JSON-экспорт для аналитика |

## Источники SCOUT

Реальные (требуют сетевой доступ): zakupki.gov.ru, kad.arbitr.ru, RSS-ленты.  
Моки (fallback): hh.ru, fns.ru, e-disclosure, контур.закупки, изменения ЕГРЮЛ.

## Внешнее репо

Код пушится в: https://github.com/IsuiGit/proact-b2b

При сбросе workspace — клонировать этот репо заново и запустить.