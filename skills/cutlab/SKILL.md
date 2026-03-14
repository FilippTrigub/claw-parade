---
name: cutlab
description: >-
  Edit a region of a video using a text prompt via Wan2.1-VACE inpainting.
  Supports two modes: background (auto-segment via rembg) or region (rectangle
  defined by fractions). Requires a CUDA GPU with at least 8 GB free VRAM.
metadata:
  {
    "openclaw":
      {
        "emoji": "✏️",
        "requires": { "bins": ["uv", "ffmpeg"] },
      },
  }
---

# cutlab — AI Video Region Editing

Edits a masked region of every frame of a video using the Wan2.1-VACE-1.3B
diffusion model. Describe the desired result in a text prompt; the model
inpaints the masked area while keeping the rest unchanged. Audio is preserved.

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

> **GPU required.** Needs a CUDA GPU with ≥ 8 GB free VRAM.
> Pause the LLM context before running to free VRAM.

---

## When to Use

Use this skill when the user wants to:
- Replace the background of a talking-head video with a different scene
- Edit a rectangular region of a video (sky, sign, screen, etc.)
- Change environment details while preserving the subject

---

## Setup (first run only)

```bash
cd "$SKILL_DIR" && uv sync
```

Wan2.1-VACE-1.3B model weights are downloaded from HuggingFace on first run
(~3 GB). rembg model weights are also downloaded on first background-mode run.

---

## Agent Workflow

### 1. Ask the user

```
Before I edit the video(s), I need to know:

💬 Prompt  (required)
   Describe what the edited region should look like, e.g.:
   "modern office with floor-to-ceiling windows and city view"

🎭 Mask mode
  - background  — auto-detect and replace the background  [default]
  - region      — edit a rectangular area (x1,y1,x2,y2 as fractions 0.0–1.0)

📐 If mode=region: mask_region
   Format: "x1,y1,x2,y2"  e.g. "0.0,0.0,1.0,0.3" for the top 30% of the frame

⚙️  Strength  (0.0–1.0, default 0.85)
   How strongly to apply the edit. Lower = more faithful to original.

📁 Input / output directories  (default: ./input and ./output)
```

Wait for user response before proceeding.

### 2. Edit config.json

Write or update `$SKILL_DIR/config.json` based on the user's choices.

### 3. Run

```bash
cd "$SKILL_DIR" && uv run python scripts/vace.py --config config.json
```

### 4. Report results

Tell the user the output file paths, mask mode used, and prompt applied.

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `input_dir` | path | `./input` | Folder containing input videos |
| `output_dir` | path | `./output` | Destination folder |
| `prompt` | string | *(required)* | Description of desired edited region |
| `negative_prompt` | string | `"worst quality, blurry, distorted"` | What to avoid |
| `mask` | `background`, `region` | `background` | Masking strategy |
| `mask_region` | `"x1,y1,x2,y2"` | *(required if region)* | Rectangle as fractions |
| `strength` | float (0, 1] | `0.85` | Inpainting strength |
| `num_inference_steps` | integer | `30` | Diffusion steps |
| `guidance_scale` | float | `5.0` | Prompt adherence |
| `batch_size` | integer | `8` | Frames processed per inference batch (lower for less VRAM) |
| `max_proc_dim` | integer | `384` | Max frame dimension before inpaint (lower for less VRAM) |
| `model` | HuggingFace ID | `Wan-AI/Wan2.1-VACE-1.3B-diffusers` | Model to use |

---

## Common Invocations

```bash
# Replace background automatically
cd "$SKILL_DIR" && uv run python scripts/vace.py \
  --prompt "serene mountain lake at sunset"

# Edit a rectangular region (top third of frame = sky replacement)
cd "$SKILL_DIR" && uv run python scripts/vace.py \
  --mask region --mask-region "0.0,0.0,1.0,0.33" \
  --prompt "clear blue sky with scattered clouds"

# Lighter edit (preserve more original detail)
cd "$SKILL_DIR" && uv run python scripts/vace.py \
  --prompt "cosy home office" --strength 0.6

# Custom directories
cd "$SKILL_DIR" && uv run python scripts/vace.py \
  --input /path/to/videos --output /path/to/edited \
  --prompt "futuristic cityscape"
```

---

## Output

Each input video produces one `.mp4` in `output_dir` with the same filename.
Original audio is muxed back in.

---

## Error Handling

- Insufficient VRAM → prints required vs available GB, tips to free VRAM, exits
- No CUDA GPU → clear error message, exits
- No videos in input_dir → clean message, exits
- Invalid mask_region format → clear error with expected format, exits
- Individual video errors → logged; other videos continue processing
