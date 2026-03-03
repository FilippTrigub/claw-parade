---
name: clawrife
description: >-
  Increase video frame rate by 2× or 4× using AI optical flow interpolation
  (RAFT). Produces smoother motion from low-fps footage. Requires a CUDA GPU
  with at least 2 GB free VRAM.
metadata:
  {
    "openclaw":
      {
        "emoji": "🎞️",
        "requires": { "bins": ["uv", "ffmpeg"] },
      },
  }
---

# clawrife — AI Frame Interpolation

Increases video frame rate using RAFT optical flow to synthesise intermediate
frames. 24 fps → 48/96 fps, or any source fps × 2/4.

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

> **GPU required.** Needs a CUDA GPU with ≥ 2 GB free VRAM.
> If the LLM context is occupying VRAM, pause it before running.

---

## When to Use

Use this skill when the user wants to:
- Make slow-motion footage smoother
- Increase the frame rate of a video clip (2× or 4×)
- Remove judder from low-fps recordings

---

## Setup (first run only)

```bash
cd "$SKILL_DIR" && uv sync
```

RAFT model weights are downloaded automatically from torchvision on first run.

---

## Agent Workflow

### 1. Ask the user

```
Before I interpolate the video(s), I need to know:

🎞️  Multiplier
  - 2  — double the frame rate (e.g. 24 → 48 fps)  [default]
  - 4  — quadruple the frame rate (e.g. 24 → 96 fps)

🧠 Model
  - raft_large  — higher quality, more VRAM  [default]
  - raft_small  — faster, uses less VRAM

📁 Input / output directories  (default: ./input and ./output)
```

Wait for user response before proceeding.

### 2. Edit config.json

Write or update `$SKILL_DIR/config.json` based on the user's choices.

### 3. Run

```bash
cd "$SKILL_DIR" && uv run python scripts/interpolate.py --config config.json
```

### 4. Report results

Tell the user the output file paths, original vs new frame rate, and frame count.

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `input_dir` | path | `./input` | Folder containing input videos |
| `output_dir` | path | `./output` | Destination folder |
| `multiplier` | `2`, `4` | `2` | Frame rate multiplier |
| `model` | `raft_large`, `raft_small` | `raft_large` | RAFT model variant |

---

## Common Invocations

```bash
# Default: 2× interpolation with raft_large
cd "$SKILL_DIR" && uv run python scripts/interpolate.py

# 4× frame rate
cd "$SKILL_DIR" && uv run python scripts/interpolate.py --multiplier 4

# Faster, lower VRAM usage
cd "$SKILL_DIR" && uv run python scripts/interpolate.py --model raft_small

# Custom directories
cd "$SKILL_DIR" && uv run python scripts/interpolate.py \
  --input /path/to/clips --output /path/to/smooth
```

---

## Output

Each input video produces one output `.mp4` with the same filename in `output_dir`.
Frame rate is multiplied; duration stays the same.

---

## Error Handling

- Insufficient VRAM → prints required vs available GB, tips to free VRAM, exits
- No CUDA GPU → clear error message, exits
- No videos in input_dir → clean message, exits
- Individual video errors → logged; other videos continue processing
