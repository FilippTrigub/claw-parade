---
name: clawportrait
description: >-
  Animate a portrait photo by transferring facial expressions and head motion
  from a driver video using LivePortrait. Great for talking-head content from
  a single still image. Requires a CUDA GPU with at least 4 GB free VRAM.
metadata:
  {
    "openclaw":
      {
        "emoji": "🎭",
        "requires": { "bins": ["uv"] },
      },
  }
---

# clawportrait — Portrait Animation (Talking Head)

Transfers facial expressions and head motion from a driver video onto a source
portrait photo using LivePortrait. The result is a realistic animated face
driven entirely by another video — no speech synthesis required.

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

> **GPU required.** Needs a CUDA GPU with ≥ 4 GB free VRAM.
> Pause the LLM context before running to free VRAM.

---

## When to Use

Use this skill when the user wants to:
- Animate a headshot photo to match someone speaking on video
- Create a talking-head clip from a single portrait image
- Apply facial expressions from one person onto another's photo
- Batch-animate one portrait against multiple driver clips

---

## Setup (first run only)

```bash
cd "$SKILL_DIR" && uv sync
```

LivePortrait model weights are downloaded from HuggingFace on first run (~1–2 GB).

---

## Agent Workflow

### 1. Ask the user

```
Before I animate the portrait, I need to know:

🖼️  Portrait image path  (required)
   A clear front-facing headshot works best.

🎬 Driver video path  (required)
   The facial expressions from this video will be applied to the portrait.
   Can also be a directory for batch mode (one output per driver video).

⚙️  Options
  - Relative motion  (default: yes) — transfers motion relative to the driver's
    neutral pose; keeps the portrait's original head position natural.
    Use --no-relative-motion to use absolute motion instead.

📁 Output directory  (default: ./output)
```

Wait for user response before proceeding.

### 2. Edit config.json

Write or update `$SKILL_DIR/config.json` based on the user's choices.

### 3. Run

```bash
cd "$SKILL_DIR" && uv run python scripts/portrait.py --config config.json
```

### 4. Report results

Tell the user the output file path(s) and which driver video(s) were used.

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `portrait` | path | *(required)* | Source portrait image |
| `driver` | path or dir | *(required)* | Driving video or directory of videos |
| `output_dir` | path | `./output` | Destination folder |
| `flag_relative_motion` | bool | `true` | Use relative (vs absolute) motion |
| `flag_pasteback` | bool | `true` | Paste animated face back onto original |
| `flag_crop_driving_video` | bool | `true` | Auto-crop driver video to face region |

---

## Common Invocations

```bash
# Animate a portrait from a driver video
cd "$SKILL_DIR" && uv run python scripts/portrait.py \
  --portrait ./input/headshot.jpg \
  --driver ./input/driver.mp4

# Batch mode: one portrait against all videos in a folder
cd "$SKILL_DIR" && uv run python scripts/portrait.py \
  --portrait ./input/headshot.jpg \
  --driver ./input/drivers/

# Disable relative motion (absolute motion transfer)
cd "$SKILL_DIR" && uv run python scripts/portrait.py \
  --portrait ./input/headshot.jpg \
  --driver ./input/driver.mp4 \
  --no-relative-motion

# Custom output directory
cd "$SKILL_DIR" && uv run python scripts/portrait.py \
  --portrait ./input/headshot.jpg \
  --driver ./input/driver.mp4 \
  --output ./output/animated
```

---

## Output

Output video(s) are written to `output_dir` named
`<portrait_stem>--<driver_stem>.mp4`.

In batch mode, one output file is created per driver video found in the driver
directory.

---

## Error Handling

- Insufficient VRAM → prints required vs available GB, tips to free VRAM, exits
- No CUDA GPU → clear error message, exits
- Portrait or driver file not found → clear error with path, exits
- No driver videos in directory (batch mode) → clean message, exits
- Individual driver errors (batch) → logged; other drivers continue processing
