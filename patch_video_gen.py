#!/usr/bin/env python3
"""Patch proact_video_generator.py with 5 user-requested fixes."""
import sys

path = "Deliverables/proact_video_generator.py"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()

changes = 0

# ── Fix 5a: TTS rate — slow down by 10% ──
old = 'await edge_tts.Communicate(text, VOICE).save(out)'
new = 'await edge_tts.Communicate(text, VOICE, rate="-10%").save(out)'
if old in c:
    c = c.replace(old, new); changes += 1; print("OK 5a: TTS rate -10%")
else:
    print("FAIL 5a: TTS rate string not found")

# ── Fix 5b: Duration formula — scene = max(5s, TTS + 1.5s) ──
old = "dur = max(min_dur, tts_dur + 0.5)"
new = "dur = max(5.0, tts_dur + 1.5)"
if old in c:
    c = c.replace(old, new); changes += 1; print("OK 5b: duration = max(5.0, tts_dur + 1.5)")
else:
    print("FAIL 5b: duration formula not found")

# ── Fix 1a: ANALYST — reduce font sizes ──
old = '    f_row = _font(20, bold=False)\n    f_sm = _font(18, bold=False)\n\n    _text_centered(draw, "ANALYST"'
new = '    f_row = _font(16, bold=False)\n    f_sm = _font(13, bold=False)\n\n    _text_centered(draw, "ANALYST"'
if old in c:
    c = c.replace(old, new); changes += 1; print("OK 1a: ANALYST fonts 20->16, 18->13")
else:
    print("FAIL 1a: ANALYST font line not found")

# ── Fix 1b: ANALYST — reduce row height ──
old = "    tw, rh = 1160, 62\n    # Header\n    draw.rounded_rectangle([tx, ty, tx + tw, ty + 36]"
new = "    tw, rh = 1160, 52\n    # Header\n    draw.rounded_rectangle([tx, ty, tx + tw, ty + 32]"
if old in c:
    c = c.replace(old, new); changes += 1; print("OK 1b: ANALYST row 62->52, header 36->32")
else:
    print("FAIL 1b: ANALYST row height not found")

# ── Fix 1c: ANALYST — adjust row text y-offset for smaller rows ──
old = "        draw.text((cx, ry + 18), name, font=f_row, fill=WHITE); cx += 220\n        # Risk badge\n        risk_color = GREEN if \"Низкий\" in risk and \"Ср\" not in risk else (GOLD if \"Ср\" in risk else ACCENT_LT)\n        _pill(draw, cx, ry + 14, risk, _font(16), risk_color, (25, 25, 40)); cx += 120\n        # Confidence bar\n        _bar(draw, cx, ry + 22, 180, 16, conf / 100, ACCENT_LT)\n        draw.text((cx + 190, ry + 18), f\"{conf}%\", font=f_row, fill=WHITE); cx += 220\n        draw.text((cx, ry + 18), products, font=f_sm, fill=GREY)"
new = "        draw.text((cx, ry + 14), name, font=f_row, fill=WHITE); cx += 220\n        # Risk badge\n        risk_color = GREEN if \"Низкий\" in risk and \"Ср\" not in risk else (GOLD if \"Ср\" in risk else ACCENT_LT)\n        _pill(draw, cx, ry + 10, risk, _font(14), risk_color, (25, 25, 40)); cx += 120\n        # Confidence bar\n        _bar(draw, cx, ry + 18, 160, 14, conf / 100, ACCENT_LT)\n        draw.text((cx + 170, ry + 14), f\"{conf}%\", font=f_row, fill=WHITE); cx += 220\n        draw.text((cx, ry + 14), products, font=f_sm, fill=GREY)"
if old in c:
    c = c.replace(old, new); changes += 1; print("OK 1c: ANALYST row offsets adjusted")
else:
    print("FAIL 1c: ANALYST row offsets not found")

# ── Fix 4a: ANALYST callout — remove emoji + /pipeline --learn ──
old = "⚙ Система учится: Аэрофлот отклонил аргумент → /pipeline --learn → новый подход"
new = "Система учится: Аэрофлот отклонил аргумент → корректировка → новый подход"
if old in c:
    c = c.replace(old, new); changes += 1; print("OK 4a: ANALYST callout cleaned")
else:
    print("FAIL 4a: ANALYST callout not found")

# ── Fix 3: BRIEF callout — move below card, remove emoji ──
old = '    # Bottom: plan callout\n    py = dy + dh - 70\n    _rounded_card(draw, dx + 30, py, dw - 60, 50, radius=10, fill=(30, 20, 28), border=ACCENT)\n    draw.text((dx + 50, py + 14), "📋 План звонка: 5 шагов · ответы на возражения", font=f_row, fill=ACCENT_LT)'
new = '    # Bottom: plan callout (below the document card)\n    py = dy + dh + 15\n    _rounded_card(draw, dx + 30, py, dw - 60, 50, radius=10, fill=(30, 20, 28), border=ACCENT)\n    draw.text((dx + 50, py + 14), "План звонка: 5 шагов и ответы на возражения", font=f_row, fill=ACCENT_LT)'
if old in c:
    c = c.replace(old, new); changes += 1; print("OK 3: BRIEF callout moved below card, emoji removed")
else:
    print("FAIL 3: BRIEF callout not found")

# ── Fix 4b: Solution scene — remove /pipeline --smart command card ──
old = '    f_cmd = _font(32, bold=False)\n    _text_centered(draw, "PROACT", W//2, 160, f_big, WHITE)\n    # Command in a card\n    bbox = draw.textbbox((0, 0), "/pipeline --smart", font=f_cmd)\n    tw = bbox[2] - bbox[0]\n    _rounded_card(draw, W//2 - tw//2 - 30, 280, tw + 60, 60, radius=30, fill=(25, 25, 40))\n    draw.text((W//2 - tw//2, 290), "/pipeline --smart", font=f_cmd, fill=ACCENT_LT)\n    _text_centered(draw, "От хаоса — к готовым клиентам", W//2, 400, f_mid, GREY)\n    _text_centered(draw, "5 стадий · 1 команда", W//2, 470, _font(28), (90, 90, 110))'
new = '    _text_centered(draw, "PROACT", W//2, 180, f_big, WHITE)\n    _text_centered(draw, "От хаоса — к готовым клиентам", W//2, 300, f_mid, GREY)\n    _text_centered(draw, "5 стадий — 1 команда", W//2, 380, _font(28), (90, 90, 110))\n    _text_centered(draw, "Разведка, анализ, разогрев, досье, отслеживание", W//2, 450, _font(22, bold=False), DARK_GREY)'
if old in c:
    c = c.replace(old, new); changes += 1; print("OK 4b: Solution scene command removed")
else:
    print("FAIL 4b: Solution scene not found")

# ── Fix 4c: Tracker callout — remove /pipeline --learn ──
old = '"/pipeline --learn → корректировка аргументов"'
new = '"Самообучение — корректировка аргументов"'
if old in c:
    c = c.replace(old, new); changes += 1; print("OK 4c: Tracker callout cleaned")
else:
    print("FAIL 4c: Tracker callout not found")

# ── Fix 2: Narrations — replace ALL English with Russian ──
narration_replacements = [
    ('"PROACT. Одна команда — весь конвейер."',
     '"ПРОАКТ. Одна команда — весь конвейер."'),
    ('"SCOUT: десять источников, пятьсот восемьдесят восемь событий, топ пятьдесят компаний."',
     '"Разведка: десять источников, пятьсот восемьдесят восемь событий, топ пятьдесят компаний."'),
    ('"ANALYST: риск-профили, confidence, продуктовая матрица. И система учится на отказах."',
     '"Анализ: риск-профили, достоверность, продуктовая матрица. И система учится на отказах."'),
    ('"WARMUP: ставка ниже на ноль три процента — но это пакет, а не скидка."',
     '"Разогрев: ставка ниже на ноль три процента — но это пакет, а не скидка."'),
    ('"BRIEF: досье на каждую компанию. План звонка и ответы на возражения."',
     '"Досье: на каждую компанию. План звонка и ответы на возражения."'),
    ('"TRACKER: воронка контактов. Отказ — это данные для следующего подхода."',
     '"Отслеживание: воронка контактов. Отказ — это данные для следующего подхода."'),
]
for old_n, new_n in narration_replacements:
    if old_n in c:
        c = c.replace(old_n, new_n); changes += 1
        print(f"OK 2: narration -> {new_n[:40]}...")
    else:
        print(f"FAIL 2: narration not found: {old_n[:40]}...")

with open(path, "w", encoding="utf-8") as f:
    f.write(c)

print(f"\n=== {changes} changes applied ===")
