---
name: clawbeat
description: >-
  Generate royalty-free background music from a text prompt using Meta MusicGen.
  Optionally mixes the result under a video at a target loudness so speech
  stays primary. Works on CPU (small model only, very slow).
metadata:
  {
    "openclaw":
      {
        "emoji": "🎵",
        "requires": { "bins": ["uv", "ffmpeg"] },
      },
  }
---

# clawbeat — Brand Music Generation

Generates royalty-free background music from a text prompt using Meta's
MusicGen. The result is saved as a WAV file or mixed directly under a video.

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

---

## When to Use

Use this skill when the user wants to:
- Add background music to a video without paying for licensed tracks
- Generate audio that matches the brand mood (e.g. "warm lo-fi", "energetic EDM")
- Replace stripped music (after clawsep) with brand-aligned music

---

## Setup (first run only)

```bash
cd "$SKILL_DIR" && uv sync
```

MusicGen weights are downloaded on first use:
- `small` (~1 GB), `medium` / `melody` (~3 GB), `large` (~7 GB)

---

## Agent Workflow

### 1. Ask the user

```
Before I generate music, I need to know:

💬 Prompt — describe the music you want
  e.g. "warm upbeat acoustic guitar, coffee shop feel"
       "lo-fi hip hop, chill, rain sounds"
       "energetic electronic, punchy bass, motivational"

⏱️  Duration (seconds, default: 30)

🎚️  Mix under video? (optional)
  If yes, provide the video path. Music will be ducked to -20 LUFS
  so speech stays primary. Or adjust with music_volume_lufs.

🧠 Model
  - small    — 300M, fast, ~3GB VRAM (default)
  - medium   — 1.5B, better quality, ~8GB VRAM
  - melody   — 1.5B, can condition on a reference melody

⚙️  Device
  - auto  — GPU if available, else CPU (default)
  - cpu   — small model only; very slow (~10× realtime)
```

### 2. Edit config.json

### 3. Run

```bash
# Generate audio only
cd "$SKILL_DIR" && uv run python scripts/generate_music.py --config config.json

# Mix under video (set "video" in config.json first)
cd "$SKILL_DIR" && uv run python scripts/generate_music.py --config config.json
```

Warn the user: the first run downloads model weights. On CPU, a 30s clip takes ~5 minutes.

### 4. Report results

Tell the user where the output file was written and its duration.

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `output_dir` | path | `./output` | Destination folder |
| `prompt` | string | required | Text description of the music |
| `duration` | 1–300 | `30` | Duration of generated music in seconds |
| `model` | `small`, `medium`, `melody`, `large` | `small` | MusicGen model |
| `device` | `auto`, `cpu`, `cuda` | `auto` | Inference device |
| `music_volume_lufs` | negative float | `-20` | Music loudness when mixing under video |
| `video` | path or null | `null` | If set, mix music under this video |

---

## Common Invocations

```bash
# Generate a 30s audio file
cd "$SKILL_DIR" && uv run python scripts/generate_music.py \
  --prompt "warm upbeat acoustic guitar coffee shop"

# 60s clip, mix under a video
cd "$SKILL_DIR" && uv run python scripts/generate_music.py \
  --prompt "lo-fi chill beats, rain" \
  --duration 60 \
  --video ./input/talking_head.mp4

# Higher quality model (needs ~8GB free VRAM)
cd "$SKILL_DIR" && uv run python scripts/generate_music.py \
  --prompt "epic orchestral, cinematic" --model medium

# Force CPU (small model only, ~5 min for 30s)
cd "$SKILL_DIR" && uv run python scripts/generate_music.py \
  --prompt "acoustic guitar" --duration 15 --model small --device cpu
```

---

## Output

- `output_dir/music.wav` — when no video is specified
- `output_dir/<video_name>.mp4` — video with music mixed in at the target loudness

---

## Error Handling

- `model != small` + `device = cpu` → rejected at config validation
- Video file not found → exits with clear message before generating music
- ffmpeg not installed → shows install instructions
