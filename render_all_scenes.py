#!/usr/bin/env python3
"""Render scenes one at a time, then concatenate — avoids OOM on 2GB RAM."""
import subprocess, sys, os, tempfile, shutil
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(__file__), "proact_video_generator.py")
OUT_DIR = os.path.join(os.path.dirname(__file__), "reports", "video")
os.makedirs(OUT_DIR, exist_ok=True)

TOTAL = 8
clips = []

for i in range(1, TOTAL + 1):
    clip = os.path.join(OUT_DIR, f"scene_{i}.mp4")
    if os.path.exists(clip) and os.path.getsize(clip) > 5000:
        print(f"Scene {i}/{TOTAL}: already exists ({os.path.getsize(clip)//1024} KB), skipping")
        clips.append(clip)
        continue

    print(f"\n{'='*50}")
    print(f"Scene {i}/{TOTAL} rendering...")
    print(f"{'='*50}")

    # Run each scene as a separate process to free memory between scenes
    result = subprocess.run(
        ["python3", SCRIPT, "--test", str(i - 1)],
        capture_output=True, text=True, timeout=90
    )

    if result.returncode != 0:
        print(f"FAILED scene {i}: {result.stderr[-500:]}")
        sys.exit(1)

    # Copy test file to scene_N.mp4
    test_file = os.path.join(OUT_DIR, f"test_scene_{i}.mp4")
    if os.path.exists(test_file):
        shutil.copy(test_file, clip)
        clips.append(clip)
        print(f"OK: scene {i} -> {clip} ({os.path.getsize(clip)//1024} KB)")
    else:
        print(f"ERROR: test file not found: {test_file}")
        sys.exit(1)

# Concatenate all scenes
print(f"\n{'='*50}")
print("Concatenating all scenes...")
print(f"{'='*50}")

concat_list = os.path.join(OUT_DIR, "concat.txt")
Path(concat_list).write_text(
    "\n".join(f"file '{c}'" for c in clips) + "\n",
    encoding="utf-8"
)

final_path = os.path.join(OUT_DIR, "proact_demo_v2.mp4")
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
result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

if result.returncode != 0:
    print(f"CONCAT FAILED: {result.stderr[-500:]}")
    sys.exit(1)

# Get duration
probe = subprocess.run(
    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
     "-of", "csv=p=0", final_path],
    capture_output=True, text=True
)
dur = float(probe.stdout.strip()) if probe.stdout.strip() else 0
size_mb = os.path.getsize(final_path) / (1024 * 1024)

print(f"\n✅ Final video: {final_path}")
print(f"   Duration: {dur:.1f}s ({dur/60:.1f} min)")
print(f"   Size: {size_mb:.1f} MB")
print(f"   Scenes: {len(clips)}")
