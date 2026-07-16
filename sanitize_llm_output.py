"""LLM output sanitizer — strips meta-commentary, code blocks, and artifacts
from subagent Markdown before delivery to user chat.

Usage:
    from sanitize_llm_output import sanitize
    clean_text = sanitize(raw_text)
"""
import re

# Patterns that indicate LLM meta-commentary (Russian + English)
_META_PATTERNS = [
    r'^Готовлю\s',
    r'^Моя задача',
    r'^Финализиру',
    r'^Непоглощённ',
    r'^Unabsorbed',
    r'^Мой deliverable',
    r'^Мой результат',
    r'^Проверка критериев',
    r'^Сводка по',
    r'^Итоговый ответ',
    r'^Best_effort',
    r'^Best effort',
    r'^solved\b',
    r'^Blocked',
    r'^Рекомендуемое действие',
    r'^FINAL ANSWER',
    r'^ИТОГОВЫЙ ОТВЕТ',
    r'^ФИНАЛЬНЫЙ ОТВЕТ',
    r'^Моя работа',
    r'^Мой предыдущий ответ',
    r'^Позвольте мне',
    r'^Blockers?:',
    r'^Evidence:',
    r'^Findings:',
    r'^Summary:',
    r'^Handoff:',
    r'^recommended_parent_action',
    r'^⚠️ NOTE:',
]

# Lines that look like code artifacts (JSON, Python, etc.)
_CODE_PATTERNS = [
    r'^\s*```',
    r'^\s*\{.*:.*\}',  # inline JSON
    r'^\s*\[.*\]',     # inline JSON array
    r'^\s*import\s',
    r'^\s*from\s+\w+\s+import',
    r'^\s*def\s',
    r'^\s*class\s',
    r'^\s*print\s*\(',
    r'^\s*return\s',
]

# Stray non-Russian/Cyrillic-adjacent characters that leak from LLM reasoning
_UNICODE_NOISE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')  # CJK chars


def _is_meta_line(line: str) -> bool:
    """Check if a line is LLM meta-commentary."""
    stripped = line.strip()
    if not stripped:
        return False
    for pattern in _META_PATTERNS:
        if re.match(pattern, stripped, re.IGNORECASE):
            return True
    return False


def _is_code_line(line: str) -> bool:
    """Check if a line looks like code artifact."""
    stripped = line.strip()
    if not stripped:
        return False
    for pattern in _CODE_PATTERNS:
        if re.match(pattern, stripped):
            return True
    return False


def _clean_unicode_noise(text: str) -> str:
    """Remove stray CJK characters that leak from LLM reasoning."""
    return _UNICODE_NOISE.sub('', text)


def sanitize(raw_text: str) -> str:
    """Strip meta-commentary, code artifacts, and unicode noise from LLM output.

    - Removes lines that are LLM self-talk (planning, finalization, status)
    - Removes code blocks and inline code artifacts
    - Removes stray CJK characters
    - Preserves all genuine Markdown content (tables, headers, lists, paragraphs)
    - Collapses excessive blank lines (3+ → 2)
    """
    if not raw_text:
        return ""

    lines = raw_text.split('\n')
    cleaned = []
    in_code_block = False

    for line in lines:
        # Toggle code block state
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            continue  # Skip the fence itself

        if in_code_block:
            continue  # Skip content inside code blocks

        if _is_meta_line(line):
            continue

        if _is_code_line(line):
            continue

        # Clean unicode noise
        line = _clean_unicode_noise(line)
        cleaned.append(line)

    result = '\n'.join(cleaned)

    # Collapse 3+ blank lines to 2
    result = re.sub(r'\n{3,}', '\n\n', result)

    # Strip leading/trailing whitespace
    result = result.strip()

    return result


if __name__ == '__main__':
    import sys
    raw = sys.stdin.read()
    print(sanitize(raw))
