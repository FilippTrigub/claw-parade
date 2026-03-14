---
name: keyer
description: >-
  Remove the background from every frame of a video using AI (BiRefNet-general
  via rembg). Outputs transparent-background video or composites onto a solid
  colour or image. Requires a CUDA GPU with at least 3 GB free VRAM.
metadata:
  {
    "openclaw":
      {
        "emoji": "🎭",
        "requires": { "bins": ["uv", "ffmpeg"] },
      },
  }
---

# keyer — AI Video Background Removal

Removes the background from every frame of a video using BiRefNet-general
(a high-quality matting model via rembg). Optionally composites onto a flat
colour or a background image. Audio is preserved.

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

> **GPU required.** Needs a CUDA GPU with ≥ 3 GB free VRAM.
> If the LLM context is occupying VRAM, pause it before running.

---

## When to Use

Use this skill when the user wants to:
- Remove the background from a video (talking head, product demo, etc.)
- Place a subject onto a solid colour or branded background
- Export a video with a transparent background (alpha channel PNG frames)

---

## Setup (first run only)

```bash
cd "$SKILL_DIR" && uv sync
```

BiRefNet model weights are downloaded automatically on first run (~500 MB).

---

## Agent Workflow

### 1. Ask the user

```
Before I remove the background, I need to know:

🎭 Background replacement
  - null          — keep transparent alpha channel (PNG frames; no mp4 alpha)
  - #hex colour   — e.g. "#1a1a2e" for dark navy
  - /path/to/bg   — composite onto an image file

🧠 Model
  - birefnet-general   — best general quality  [default]
  - birefnet-portrait  — optimised for people
  - isnet-general-use  — faster alternative
  - u2net_human_seg    — fast, human-only

📁 Input / output directories  (default: ./input and ./output)
```

Wait for user response before proceeding.

### 2. Edit config.json

Write or update `$SKILL_DIR/config.json` based on the user's choices.

### 3. Run

```bash
cd "$SKILL_DIR" && uv run python scripts/matte.py --config config.json
```

### 4. Report results

Tell the user the output file paths and background mode used.

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `input_dir` | path | `./input` | Folder containing input videos |
| `output_dir` | path | `./output` | Destination folder |
| `model` | see above | `birefnet-general` | Matting model |
| `bg` | null / hex / path | `null` | Background replacement |

---

## Common Invocations

```bash
# Default: remove background, transparent output
cd "$SKILL_DIR" && uv run python scripts/matte.py

# Dark background composite
cd "$SKILL_DIR" && uv run python scripts/matte.py --bg "#0d0d0d"

# Composite onto an image
cd "$SKILL_DIR" && uv run python scripts/matte.py --bg /path/to/studio_bg.jpg

# Portrait-optimised model
cd "$SKILL_DIR" && uv run python scripts/matte.py --model birefnet-portrait

# Null background (pass as string "null" via CLI)
cd "$SKILL_DIR" && uv run python scripts/matte.py --bg null
```

---

## Output

Each input video produces one output `.mp4` in `output_dir` with the same
filename. If `bg=null`, the output is encoded with yuv420p (no true transparency
in mp4); for actual transparent frames, run clawimig or export as PNG sequence.

---

## Error Handling

- Insufficient VRAM → prints required vs available GB, tips to free VRAM, exits
- No CUDA GPU / ONNX CUDAExecutionProvider missing → clear error, exits
- No videos in input_dir → clean message, exits
- Individual video errors → logged; other videos continue processing
