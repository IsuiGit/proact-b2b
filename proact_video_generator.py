#!/usr/bin/env python3
"""PROACT Video Generator v3 — clean infographic style.

Key improvements over v2:
- No zoompan (removes jitter) — static or slow scale
- Text shadows for readability on any background
- PIL-drawn data tables and charts with real pipeline data
- Shorter narration (1-2 sentences per scene)
- Cleaner backgrounds — less visual noise
- More on-screen infographic text, less voiceover
- Target duration: ~2:30

Usage:
  python3 proact_video_generator.py              # full video
  python3 proact_video_generator.py --test 3      # single scene test
"""

import asyncio, subprocess, tempfile, os, sys, math, random, json
from pathlib import Path

try:
    import edge_tts
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "edge-tts", "--quiet"], check=True)
    import edge_tts

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "Pillow", "--quiet"], check=True)
    from PIL import Image, ImageDraw, ImageFont

# ── Constants ──────────────────────────────────────────────
W, H, FPS = 1280, 720, 30
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
VOICE = "ru-RU-DmitryNeural"
BG = (10, 10, 18)
CARD_BG = (18, 18, 30)
CARD_BORDER = (40, 40, 60)
ACCENT = (201, 53, 69)
ACCENT_LT = (232, 93, 111)
GOLD = (212, 175, 55)
GREEN = (80, 200, 120)
WHITE = (245, 245, 250)
GREY = (140, 140, 160)
DARK_GREY = (60, 60, 80)

def _font(size, bold=True):
    return ImageFont.truetype(FONT if bold else FONT_REG, size)

# ── PIL Drawing Helpers ───────────────────────────────────

def _rounded_card(draw, x, y, w, h, radius=12, fill=CARD_BG, border=CARD_BORDER):
    """Draw a rounded card with border."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=border, width=2)

def _text_centered(draw, text, cx, y, font, fill):
    """Draw text centered at cx (accounts for font left-bearing)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2 - bbox[0], y), text, font=font, fill=fill)
    return tw

def _bar(draw, x, y, w, h, pct, color, bg_color=DARK_GREY):
    """Draw a progress bar."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=bg_color)
    fw = int(w * pct)
    if fw > 0:
        draw.rounded_rectangle([x, y, x + fw, y + h], radius=h // 2, fill=color)

def _pill(draw, x, y, text, font, color, bg):
    """Draw a pill/badge with text."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py, pw, ph = x, y, tw + 20, th + 10
    draw.rounded_rectangle([px, py, px + pw, py + ph], radius=ph // 2, fill=bg, outline=color, width=2)
    draw.text((px + 10, py + 4), text, font=font, fill=color)
    return pw

# ── Background Generators ─────────────────────────────────

def bg_problem(path):
    """Scene 1: Clean dark bg with subtle vignette."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    # Subtle radial darkening at edges
    for r in range(700, 400, -10):
        c = max(0, 10 - int((700 - r) / 300 * 3))
        draw.ellipse([W//2 - r, H//2 - r, W//2 + r, H//2 + r], outline=(c, c, c + 3))
    img.save(path)

def bg_solution(path):
    """Scene 2: Clean dark bg with single accent line."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([W//2 - 200, H//2 - 2, W//2 + 200, H//2 + 2], fill=(30, 30, 50))
    img.save(path)

def bg_scout(path):
    """Scene 3: Clean dark bg for table overlay."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    # Very subtle top gradient
    for y in range(80):
        c = int(10 + y * 0.08)
        draw.line([(0, y), (W, y)], fill=(c, c, c + 4))
    img.save(path)

def bg_analyst(path):
    """Scene 4: Clean dark bg for risk matrix."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    for y in range(80):
        c = int(10 + y * 0.08)
        draw.line([(0, y), (W, y)], fill=(c, c, c + 4))
    img.save(path)

def bg_warmup(path):
    """Scene 5: Clean dark bg for balance infographic."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    img.save(path)

def bg_brief(path):
    """Scene 6: Clean dark bg for document mockup."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    img.save(path)

def bg_tracker(path):
    """Scene 7: Clean dark bg for funnel."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    img.save(path)

def bg_final(path):
    """Scene 8: Clean dark bg with subtle glow."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    for r in range(300, 100, -5):
        i = int(3 * (1 - (r - 100) / 200))
        draw.ellipse([W//2 - r, H//2 - r, W//2 + r, H//2 + r], outline=(10 + i, 10 + i, 16 + i))
    img.save(path)

# ── Infographic Scene Builders ────────────────────────────
# These draw the FULL scene including data visualizations directly on the PIL image.

def scene_problem_full(path):
    """Scene 1: Problem — big stats."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    f_big = _font(72)
    f_mid = _font(40)
    f_sm = _font(28)
    # "10 000" with accent
    _text_centered(draw, "10 000", W//2, 120, f_big, WHITE)
    _text_centered(draw, "компаний на рынке", W//2, 200, f_mid, GREY)
    # Divider
    draw.rectangle([W//2 - 100, 270, W//2 + 100, 272], fill=DARK_GREY)
    # "588"
    _text_centered(draw, "588", W//2, 310, f_big, ACCENT_LT)
    _text_centered(draw, "сигналов каждый день", W//2, 390, f_mid, GREY)
    # Question
    _text_centered(draw, "Сколько из них — ваши клиенты?", W//2, 500, f_sm, ACCENT)
    img.save(path)

def scene_solution_full(path):
    """Scene 2: Solution — one command."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    f_big = _font(64)
    f_mid = _font(36)
    _text_centered(draw, "PROACT", W//2, 180, f_big, WHITE)
    _text_centered(draw, "От хаоса — к готовым клиентам", W//2, 300, f_mid, GREY)
    _text_centered(draw, "5 стадий — 1 команда", W//2, 380, _font(28), (90, 90, 110))
    _text_centered(draw, "Разведка, анализ, разогрев, досье, отслеживание", W//2, 450, _font(22, bold=False), DARK_GREY)
    img.save(path)

def scene_scout_full(path):
    """Scene 3: SCOUT — actual top-5 table + source breakdown."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    f_title = _font(48)
    f_hdr = _font(22)
    f_row = _font(20, bold=False)
    f_big = _font(36)

    # Title
    _text_centered(draw, "SCOUT", W//2, 25, f_title, WHITE)
    # Funnel stats
    _text_centered(draw, "588 событий → 139 уникальных → Top-50", W//2, 85, f_hdr, ACCENT_LT)

    # Top-5 table
    companies = [
        ("1", "Роснефть", "Консолид. акций", "500М ₽", 9.3),
        ("2", "Аэрофлот", "Дробление акций", "100М ₽", 8.9),
        ("3", "ФСК ЕЭС", "Допэмиссия", "500М ₽", 8.4),
        ("4", "ЭнергоСнаб", "Контракт 350М", "350М ₽", 8.3),
        ("5", "ФармДистр.", "Закупка склад", "350М ₽", 7.5),
    ]
    tx, ty = 80, 130
    tw, rh = 1120, 52
    # Header
    draw.rounded_rectangle([tx, ty, tx + tw, ty + 36], radius=8, fill=(25, 25, 42))
    headers = [("#", 60), ("Компания", 280), ("Событие", 300), ("Сумма", 160), ("Вес", 140)]
    cx = tx + 20
    for h, hw in headers:
        draw.text((cx, ty + 7), h, font=f_hdr, fill=GREY)
        cx += hw
    ty += 42
    # Rows
    for i, (rank, name, event, amount, weight) in enumerate(companies):
        ry = ty + i * rh
        row_bg = (16, 16, 28) if i % 2 == 0 else (20, 20, 34)
        draw.rectangle([tx, ry, tx + tw, ry + rh - 4], fill=row_bg)
        cx = tx + 20
        draw.text((cx, ry + 14), rank, font=f_row, fill=GREY); cx += 60
        draw.text((cx, ry + 14), name, font=f_row, fill=WHITE); cx += 280
        draw.text((cx, ry + 14), event, font=f_row, fill=GREY); cx += 300
        draw.text((cx, ry + 14), amount, font=f_row, fill=WHITE); cx += 160
        # Weight bar
        _bar(draw, cx, ry + 18, 100, 16, weight / 10, ACCENT_LT)
        draw.text((cx + 110, ry + 14), f"{weight}", font=f_row, fill=ACCENT_LT)

    img.save(path)

def scene_analyst_full(path):
    """Scene 4: ANALYST — risk matrix table with confidence bars."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    f_title = _font(48)
    f_hdr = _font(22)
    f_row = _font(14, bold=False)
    f_sm = _font(12, bold=False)

    _text_centered(draw, "ANALYST", W//2, 25, f_title, WHITE)
    _text_centered(draw, "Риск-профили и продуктовая матрица", W//2, 85, f_hdr, ACCENT_LT)

    # Risk table
    companies = [
        ("Роснефть", "Низкий", 93, "Проект. фин. + ВЭД + хедж"),
        ("Аэрофлот", "Низкий", 89, "Предодобр. линия + ВЭД"),
        ("ФСК ЕЭС", "Низкий", 84, "Проект. фин. + РКО API"),
        ("ЭнергоСнаб", "Низ-Ср", 83, "Гарантия + кредит + РКО"),
        ("ФармДистр.", "Средний", 75, "Кредит + гарантии + РКО"),
    ]
    tx, ty = 60, 120
    tw, rh = 1160, 52
    # Header
    draw.rounded_rectangle([tx, ty, tx + tw, ty + 32], radius=8, fill=(25, 25, 42))
    headers = [("Компания", 220), ("Риск", 120), ("Confidence", 220), ("Продукты", 400)]
    cx = tx + 20
    for h, hw in headers:
        draw.text((cx, ty + 7), h, font=f_hdr, fill=GREY)
        cx += hw
    ty += 42

    for i, (name, risk, conf, products) in enumerate(companies):
        ry = ty + i * rh
        row_bg = (16, 16, 28) if i % 2 == 0 else (20, 20, 34)
        draw.rectangle([tx, ry, tx + tw, ry + rh - 6], fill=row_bg)
        cx = tx + 20
        draw.text((cx, ry + 14), name, font=f_row, fill=WHITE); cx += 220
        # Risk badge
        risk_color = GREEN if "Низкий" in risk and "Ср" not in risk else (GOLD if "Ср" in risk else ACCENT_LT)
        _pill(draw, cx, ry + 10, risk, _font(12), risk_color, (25, 25, 40)); cx += 120
        # Confidence bar
        _bar(draw, cx, ry + 18, 160, 14, conf / 100, ACCENT_LT)
        draw.text((cx + 170, ry + 14), f"{conf}%", font=f_row, fill=WHITE); cx += 220
        draw.text((cx, ry + 14), products, font=f_sm, fill=GREY)

    # "Система учится" callout at bottom
    cy = ty + len(companies) * rh + 15
    _rounded_card(draw, 200, cy, 880, 70, radius=14, fill=(30, 20, 28), border=ACCENT)
    _text_centered(draw, "Система учится: Аэрофлот отклонил аргумент → корректировка → новый подход", W//2, cy + 22, _font(16), ACCENT_LT)
    img.save(path)

def scene_warmup_full(path):
    """Scene 5: WARMUP — personalized outreach showing competitive advantages."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    f_title = _font(48)
    f_hdr = _font(22)
    f_big = _font(28)
    f_sm = _font(18, bold=False)

    _text_centered(draw, "WARMUP", W//2, 25, f_title, WHITE)
    _text_centered(draw, "Персонализированная рассылка — преимущества перед другими банками", W//2, 85, f_hdr, ACCENT_LT)

    # Three advantage cards
    cards = [
        ("Скорость", "Оформление за 1 день", "Конкуренты: 3–5 дней", ACCENT_LT),
        ("Выгоднее", "Пакет: кредит + ВЭД + РКО", "Конкуренты: по отдельности", GOLD),
        ("Надёжнее", "Обеспечение — сам проект", "Конкуренты: залог активов", GREEN),
    ]
    cw = 360
    gap = 30
    total_w = cw * 3 + gap * 2
    start_x = (W - total_w) // 2
    cy = 130
    ch = 300

    for i, (title, desc, comp, color) in enumerate(cards):
        cx = start_x + i * (cw + gap)
        _rounded_card(draw, cx, cy, cw, ch, radius=16, fill=(28, 22, 30), border=color)
        # Icon circle
        ix = cx + cw // 2
        iy = cy + 45
        r = 28
        draw.ellipse([ix - r, iy - r, ix + r, iy + r], fill=(40, 30, 38), outline=color, width=2)
        _text_centered(draw, str(i + 1), ix, iy - 14, _font(28), color)
        # Title
        _text_centered(draw, title, ix, cy + 95, f_big, WHITE)
        # Description
        _text_centered(draw, desc, ix, cy + 140, f_sm, color)
        # Competitor comparison
        _text_centered(draw, comp, ix, cy + 175, _font(16, bold=False), DARK_GREY)
        # Checkmark
        _text_centered(draw, "✓", ix, cy + 230, _font(40), color)

    # Bottom: key message
    by = 460
    _rounded_card(draw, 150, by, 980, 70, radius=14, fill=(20, 20, 35), border=CARD_BORDER)
    _text_centered(draw, "Каждое письмо показывает, почему мы — лучший выбор", W//2, by + 15, _font(22), ACCENT_LT)
    _text_centered(draw, "Не ставка ниже, а конкретные преимущества под задачу клиента", W//2, by + 45, f_sm, GREY)
    img.save(path)

def scene_brief_full(path):
    """Scene 6: BRIEF — document mockup with key data."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    f_title = _font(48)
    f_hdr = _font(22)
    f_row = _font(20, bold=False)
    f_sm = _font(16, bold=False)

    _text_centered(draw, "BRIEF", W//2, 25, f_title, WHITE)
    _text_centered(draw, "Досье на каждую компанию", W//2, 85, f_hdr, ACCENT_LT)

    # Document card
    dx, dy, dw, dh = 120, 120, 1040, 420
    _rounded_card(draw, dx, dy, dw, dh, radius=14, fill=(22, 22, 36))

    # Company name
    draw.text((dx + 30, dy + 25), "ПАО Роснефть", font=_font(32), fill=WHITE)
    _pill(draw, dx + dw - 200, dy + 30, "93% confidence", _font(16), GREEN, (20, 30, 20))

    # Divider
    draw.rectangle([dx + 30, dy + 80, dx + dw - 30, dy + 82], fill=CARD_BORDER)

    # Key data rows
    data = [
        ("Продукт", "Проектное финансирование"),
        ("Сумма", "до 10 млрд ₽"),
        ("Ставка", "11.2% (−0.3% к ВТБ)"),
        ("Срок", "7 лет"),
        ("Обеспечение", "Сам проект"),
        ("Кросс-селл", "ВЭД + хедж + РКО + зарплатный"),
    ]
    for i, (k, v) in enumerate(data):
        ry = dy + 100 + i * 45
        draw.text((dx + 40, ry), k, font=f_row, fill=GREY)
        draw.text((dx + 220, ry), v, font=f_row, fill=WHITE)
        if i < len(data) - 1:
            draw.rectangle([dx + 30, ry + 35, dx + dw - 30, ry + 36], fill=(28, 28, 44))

    # Bottom: plan callout (below the document card)
    py = dy + dh + 15
    _rounded_card(draw, dx + 30, py, dw - 60, 50, radius=10, fill=(30, 20, 28), border=ACCENT)
    draw.text((dx + 50, py + 14), "План звонка: 5 шагов и ответы на возражения", font=f_row, fill=ACCENT_LT)
    img.save(path)

def scene_tracker_full(path):
    """Scene 7: TRACKER — sales funnel."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    f_title = _font(48)
    f_hdr = _font(22)
    f_row = _font(22)

    _text_centered(draw, "TRACKER", W//2, 25, f_title, WHITE)
    _text_centered(draw, "Воронка контактов и самообучение", W//2, 85, f_hdr, ACCENT_LT)

    # Funnel stages
    stages = [
        ("В воронке", 5, ACCENT_LT, 500),
        ("Outreach", 5, ACCENT_LT, 400),
        ("Дообработка", 1, GOLD, 300),
        ("Встречи", 0, DARK_GREY, 200),
        ("Сделки", 0, DARK_GREY, 100),
    ]
    fy = 130
    for i, (name, count, color, width) in enumerate(stages):
        ry = fy + i * 90
        # Funnel shape — trapezoid
        cx = W // 2
        x0 = cx - width // 2
        x1 = cx + width // 2
        if i < len(stages) - 1:
            next_w = stages[i + 1][3]
            x0n = cx - next_w // 2
            x1n = cx + next_w // 2
            draw.polygon([(x0, ry), (x1, ry), (x1n, ry + 70), (x0n, ry + 70)], fill=(20 + i * 3, 18 + i * 2, 30 + i * 3), outline=color)
        else:
            draw.polygon([(x0, ry), (x1, ry), (x1 - 30, ry + 70), (x0 + 30, ry + 70)], fill=(20 + i * 3, 18 + i * 2, 30 + i * 3), outline=color)
        # Count
        count_text = str(count)
        _text_centered(draw, count_text, cx, ry + 18, _font(36), color)
        _text_centered(draw, name, cx, ry + 58, _font(18, bold=False), GREY)

    # Learn callout
    ly = fy + len(stages) * 90 - 10
    _rounded_card(draw, 250, ly, 780, 55, radius=12, fill=(30, 20, 28), border=ACCENT)
    _text_centered(draw, "Самообучение — корректировка аргументов", W//2, ly + 16, _font(20), ACCENT_LT)
    img.save(path)

def scene_final_full(path):
    """Scene 8: Final — key stats + logo."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    f_big = _font(56)
    f_mid = _font(32)
    f_sm = _font(24)

    _text_centered(draw, "588 → 5", W//2, 130, f_big, WHITE)
    _text_centered(draw, "сигналов → готовых клиентов", W//2, 200, f_mid, GREY)

    # Stats row
    stats = [("10", "источников"), ("5", "стадий"), ("1", "команда")]
    sx = 250
    for val, label in stats:
        _text_centered(draw, val, sx + 130, 280, f_big, ACCENT_LT)
        _text_centered(draw, label, sx + 130, 350, f_sm, GREY)
        sx += 320

    _text_centered(draw, "PROACT", W//2, 460, _font(80), ACCENT)
    _text_centered(draw, "Проактивная аналитика для корпоративного бизнеса", W//2, 550, f_sm, DARK_GREY)
    img.save(path)

# ── TTS ────────────────────────────────────────────────────

async def _tts(text, out):
    await edge_tts.Communicate(text, VOICE).save(out)

def gen_tts(text, out):
    asyncio.run(_tts(text, out))

def audio_dur(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    return float(r.stdout.strip())

# ── Scene Rendering ───────────────────────────────────────

def render_scene(bg_path, narration, overlays, min_dur, out_path, tmpdir, use_scale=False):
    """Render one scene with static bg + text overlays + TTS.

    overlays: [(text, appear_at, y_frac, fontsize, color_hex, fade_dur), ...]
    use_scale: if True, apply very slow zoom (1.0 -> 1.04) for subtle motion.
    """
    audio = os.path.join(tmpdir, "audio.mp3")
    gen_tts(narration, audio)
    tts_dur = audio_dur(audio)
    dur = tts_dur + 0.5
    frames = int(dur * FPS)

    parts = []

    # PIL backgrounds already have dark backgrounds with proper text — no overlay bars needed

    for i, (text, appear, yf, fs, color, fade) in enumerate(overlays):
        tf = os.path.join(tmpdir, f"t{i}.txt")
        Path(tf).write_text(text, encoding="utf-8")
        alpha = f"if(lt(t,{appear}),0,if(lt(t,{appear + fade}),(t-{appear})/{fade},1))"
        # Text with shadow for readability
        parts.append(
            f"drawtext=fontfile={FONT}:textfile={tf}:fontcolor={color}:"
            f"fontsize={fs}:x=(w-text_w)/2:y=h*{yf}:"
            f"shadowcolor=0x000000@0.8:shadowx=3:shadowy=3:"
            f"alpha='{alpha}':enable='gte(t,{appear})'"
        )

    parts.append("vignette=angle=PI/10")  # subtle corner darkening
    parts.append("fade=t=in:st=0:d=0.3")
    parts.append(f"fade=t=out:st={dur - 0.3:.2f}:d=0.3")
    vf = ",".join(parts)

    if use_scale:
        # Very slow, smooth zoom — no jitter
        vf_in = f"scale={W}x{H},zoompan=z='1+on/{frames}*0.03':d={frames}:s={W}x{H}:fps={FPS}"
    else:
        vf_in = f"scale={W}x{H}"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", str(FPS),
        "-i", bg_path,
        "-i", audio,
        "-vf", f"{vf_in},{vf}",
        "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-t", f"{dur:.2f}",
        out_path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"FFMPEG ERROR:\n{r.stderr[-2000:]}")
        raise RuntimeError(f"ffmpeg failed for {out_path}")
    return dur

# ── Scene Definitions ──────────────────────────────────────

SCENES = [
    {
        "name": "01_problem",
        "bg_func": scene_problem_full,
        "narration": "Десять тысяч компаний. Пятьсот восемьдесят восемь сигналов каждый день.",
        "overlays": [],
        "duration": 8,
        "scale": False,
    },
    {
        "name": "02_solution",
        "bg_func": scene_solution_full,
        "narration": "ПРОАКТ. Одна команда — весь конвейер.",
        "overlays": [],
        "duration": 7,
        "scale": False,
    },
    {
        "name": "03_scout",
        "bg_func": scene_scout_full,
        "narration": "Разведка: десять источников, пятьсот восемьдесят восемь событий, топ пятьдесят компаний.",
        "overlays": [],
        "duration": 12,
        "scale": False,
    },
    {
        "name": "04_analyst",
        "bg_func": scene_analyst_full,
        "narration": "Анализ: риск-профили, достоверность, продуктовая матрица. И система учится на отказах.",
        "overlays": [],
        "duration": 12,
        "scale": False,
    },
    {
        "name": "05_warmup",
        "bg_func": scene_warmup_full,
        "narration": "Разогрев: персонализированная рассылка. Демонстрируем клиенту преимущества перед другими банками.",
        "overlays": [],
        "duration": 10,
        "scale": False,
    },
    {
        "name": "06_brief",
        "bg_func": scene_brief_full,
        "narration": "Досье: на каждую компанию. План звонка и ответы на возражения.",
        "overlays": [],
        "duration": 10,
        "scale": False,
    },
    {
        "name": "07_tracker",
        "bg_func": scene_tracker_full,
        "narration": "Отслеживание: воронка контактов. Отказ — это данные для следующего подхода.",
        "overlays": [],
        "duration": 10,
        "scale": False,
    },
    {
        "name": "08_final",
        "bg_func": scene_final_full,
        "narration": "От пятисот восьмидесяти восьми сигналов — до пяти клиентов. Одна команда.",
        "overlays": [],
        "duration": 10,
        "scale": False,
    },
]

# ── Main ───────────────────────────────────────────────────

def main():
    test_idx = None
    if "--test" in sys.argv:
        ti = sys.argv.index("--test")
        test_idx = int(sys.argv[ti + 1]) if ti + 1 < len(sys.argv) else 0

    out_dir = os.path.join(os.path.dirname(__file__) or ".", "reports", "video")
    os.makedirs(out_dir, exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="proact_vid_")

    scenes_to_render = [test_idx] if test_idx is not None else range(len(SCENES))
    scene_clips = []

    for idx in scenes_to_render:
        s = SCENES[idx]
        print(f"\n{'='*60}")
        print(f"Scene {idx + 1}/{len(SCENES)}: {s['name']}")
        print(f"{'='*60}")

        bg_path = os.path.join(tmpdir, f"bg_{idx}.png")
        print(f"  [1/3] Generating background ({s['bg_func'].__name__})...")
        s['bg_func'](bg_path)
        print(f"        OK: {os.path.getsize(bg_path) // 1024} KB")

        clip_path = os.path.join(tmpdir, f"scene_{idx}.mp4")
        print(f"  [2/3] Rendering scene (TTS + ffmpeg)...")
        dur = render_scene(
            bg_path, s["narration"], s["overlays"],
            s["duration"], clip_path, tmpdir, s.get("scale", False)
        )
        print(f"        OK: {dur:.1f}s, {os.path.getsize(clip_path) // 1024} KB")
        scene_clips.append(clip_path)

    if test_idx is not None:
        out_path = os.path.join(out_dir, f"test_scene_{test_idx + 1}.mp4")
        subprocess.run(["cp", scene_clips[0], out_path], check=True)
        print(f"\n✅ Test scene saved: {out_path}")
        print(f"   Size: {os.path.getsize(out_path) // 1024} KB")
        return

    # Concat all scenes
    print(f"\n{'='*60}")
    print("Concatenating all scenes...")
    concat_list = os.path.join(tmpdir, "concat.txt")
    Path(concat_list).write_text(
        "\n".join(f"file '{c}'" for c in scene_clips) + "\n",
        encoding="utf-8"
    )
    final_path = os.path.join(out_dir, "proact_demo.mp4")
    # Remove old file to avoid corrupt-file confusion
    if os.path.exists(final_path):
        os.remove(final_path)
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        final_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    total_dur = sum(audio_dur(c) for c in scene_clips)
    size_mb = os.path.getsize(final_path) / (1024 * 1024)
    print(f"\n✅ Final video: {final_path}")
    print(f"   Duration: {total_dur:.1f}s ({total_dur / 60:.1f} min)")
    print(f"   Size: {size_mb:.1f} MB")
    print(f"   Scenes: {len(scene_clips)}")


if __name__ == "__main__":
    main()
