#!/usr/bin/env python3
"""PROACT video generator — programmatic MP4 via edge-tts + ffmpeg.

No paid APIs. No post-production. Script → Russian voiceover + text → finished MP4.
"""

import asyncio
import subprocess
import tempfile
import os
import sys
from pathlib import Path

try:
    import edge_tts
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "edge-tts", "--quiet"], check=True)
    import edge_tts

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
VOICE = "ru-RU-DmitryNeural"
W, H = 1280, 720
FPS = 30


async def _gen_tts(text: str, out_path: str):
    await edge_tts.Communicate(text, VOICE).save(out_path)


def gen_tts(text: str, out_path: str):
    asyncio.run(_gen_tts(text, out_path))


def audio_duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    return float(r.stdout.strip())


def render_scene(narration: str, title: str, text_lines: list,
                 out_path: str, tmpdir: str) -> float:
    """Render one scene: TTS audio + dark-bg video with text overlays -> MP4."""
    # 1. TTS
    audio_path = os.path.join(tmpdir, "scene_audio.mp3")
    gen_tts(narration, audio_path)
    dur = audio_duration(audio_path)

    # 2. Build drawtext filter chain (textfile avoids Cyrillic escaping issues)
    filters = []

    if title:
        tf = os.path.join(tmpdir, "title.txt")
        Path(tf).write_text(title, encoding="utf-8")
        filters.append(
            f"drawtext=fontfile={FONT}:textfile={tf}:"
            f"fontcolor=white:fontsize=80:x=(w-text_w)/2:y=h*0.25:"
            f"enable='gte(t,0)'"
        )

    n = max(len(text_lines), 1)
    for i, line in enumerate(text_lines):
        tf = os.path.join(tmpdir, f"line_{i}.txt")
        Path(tf).write_text(line, encoding="utf-8")
        appear = dur * (0.25 + i * 0.5 / n)
        y_pos = f"h*0.5+{i*65}"
        filters.append(
            f"drawtext=fontfile={FONT}:textfile={tf}:"
            f"fontcolor=0xccccdd:fontsize=48:x=(w-text_w)/2:y={y_pos}:"
            f"enable='gte(t,{appear:.2f})'"
        )

    vf = ",".join(filters)

    # 3. Render: dark background + text overlays + TTS audio
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x0d0d18:s={W}x{H}:d={dur}:r={FPS}",
        "-i", audio_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        out_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return dur


# === Test scene ===
TEST_SCENE = {
    "title": "PROACT",
    "narration": (
        "PROACT. От пятисот восьмидесяти восьми сигналов — "
        "до пяти готовых к звонку клиентов. Одна команда."
    ),
    "text_lines": [
        "588 сигналов → 5 клиентов",
        "Одна команда — весь конвейер",
    ],
}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "test_scene.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        d = render_scene(
            TEST_SCENE["narration"],
            TEST_SCENE["title"],
            TEST_SCENE["text_lines"],
            out, tmp
        )
        size_kb = os.path.getsize(out) // 1024
        print(f"OK: {out} | {d:.1f}s | {size_kb}KB")
