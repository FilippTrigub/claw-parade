---
name: liven
description: >-
  Animate a still image into a short video clip using LTX-Video (image-to-video
  diffusion). Guided by a text prompt describing the desired motion. Requires a
  CUDA GPU with at least 8 GB free VRAM.
metadata:
  {
    "openclaw":
      {
        "emoji": "🎬",
        "requires": { "bins": ["uv"] },
      },
  }
---

# clawanimate — Image to Video Animation

Brings still images to life using the LTX-Video diffusion model. Provide an
image and a motion prompt; the model generates a short video clip (~3 seconds
at 24 fps).

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

> **GPU required.** Needs a CUDA GPU with ≥ 8 GB free VRAM.
> Pause the LLM context before running to free VRAM.

---

## When to Use

Use this skill when the user wants to:
- Animate a photo or illustration into a short video
- Create a cinematic motion from a still (e.g. slow zoom, pan, light flicker)
- Generate social media video content from product shots or portraits

---

## Setup (first run only)

```bash
cd "$SKILL_DIR" && uv sync
```

LTX-Video model weights are downloaded from HuggingFace on first run (~8 GB).

---

## Agent Workflow

### 1. Ask the user

```
Before I animate the image(s), I need to know:

💬 Motion prompt  (required)
   Describe the motion you want, e.g.:
   "slow cinematic push-in, golden hour light, subtle camera drift"

🚫 Negative prompt  (optional)
   Default: "worst quality, inconsistent motion, blurry, jittery, distorted"

🎬 Clip settings
   - num_frames   — number of frames to generate  (default: 81 ≈ 3.4 s at 24 fps)
   - width        — output width in pixels          (default: 768, multiple of 32)
   - height       — output height in pixels         (default: 512, multiple of 32)

📁 Input / output directories  (default: ./input and ./output)
```

Wait for user response before proceeding.

### 2. Edit config.json

Write or update `$SKILL_DIR/config.json` based on the user's choices.

### 3. Run

```bash
cd "$SKILL_DIR" && uv run python scripts/img2vid.py --config config.json
```

### 4. Report results

Tell the user the output file paths, clip duration, and resolution.

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `input_dir` | path | `./input` | Folder containing source images |
| `output_dir` | path | `./output` | Destination folder |
| `prompt` | string | *(required)* | Motion description |
| `negative_prompt` | string | see above | Things to avoid |
| `num_frames` | integer ≥ 9 | `81` | Frames to generate |
| `width` | int, multiple of 32 | `768` | Output width |
| `height` | int, multiple of 32 | `512` | Output height |
| `guidance_scale` | float | `3.0` | Prompt adherence strength |
| `num_inference_steps` | integer | `40` | Diffusion steps (quality vs speed) |
| `model` | HuggingFace ID | `Lightricks/LTX-Video` | Model to use |

---

## Common Invocations

```bash
# Animate with a motion prompt
cd "$SKILL_DIR" && uv run python scripts/img2vid.py \
  --prompt "slow cinematic push-in, golden hour light"

# Shorter clip (9 frames minimum)
cd "$SKILL_DIR" && uv run python scripts/img2vid.py \
  --prompt "subtle wind in the trees" --num-frames 25

# Square output
cd "$SKILL_DIR" && uv run python scripts/img2vid.py \
  --prompt "gentle wave motion" --width 512 --height 512

# Fewer steps for faster preview
cd "$SKILL_DIR" && uv run python scripts/img2vid.py \
  --prompt "zoom out slowly" --steps 20
```

---

## Output

Each input image produces one `.mp4` clip in `output_dir`, named
`<image_stem>.mp4`. Duration depends on `num_frames` and the model's fps.

---

## Error Handling

- Insufficient VRAM → prints required vs available GB, tips to free VRAM, exits
- No CUDA GPU → clear error message, exits
- No images in input_dir → clean message, exits
- Individual image errors → logged; other images continue processing
