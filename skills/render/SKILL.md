---
name: render
description: >-
  Generate images from text prompts using HuggingFace diffusers. Supports multiple
  model architectures including FLUX, SDXL, SD3, and Playground v2. Can use
  predefined models or any custom HuggingFace model ID. Requires a CUDA GPU.
metadata:
  {
    "openclaw":
      {
        "emoji": "🎨",
        "requires": { "bins": ["uv"] },
      },
  }
---

# render — Text to Image Generation

Generate images from text prompts using state-of-the-art diffusion models from
HuggingFace. Supports multiple model architectures with automatic downloading.

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

> **GPU required.** VRAM requirements vary by model (see table below).
> Pause other GPU workloads before running.

---

## When to Use

Use this skill when the user wants to:
- Generate images from text descriptions
- Create concept art, product shots, or social media visuals
- Use any diffusers-compatible model from HuggingFace

---

## Supported Models

| Model Key | HuggingFace ID | VRAM | Best For |
|-----------|----------------|------|----------|
| `flux` | black-forest-labs/FLUX.1-dev | ≥12 GB | Highest quality, photorealistic |
| `flux-schnell` | black-forest-labs/FLUX.1-schnell | ≥12 GB | Fast generation (4 steps) |
| `sdxl` | stabilityai/stable-diffusion-xl-base-1.0 | ≥8 GB | Balanced quality/speed |
| `sd3` | stabilityai/stable-diffusion-3-medium | ≥6 GB | Good quality, lower VRAM |
| `playground` | playgroundai/playground-v2.5-1024px-aesthetic | ≥6 GB | Aesthetic/p stylized images |
| *custom* | Any HF model ID | ≥6 GB | User-specified model |

---

## Setup (first run only)

```bash
cd "$SKILL_DIR" && uv sync
```

Model weights are downloaded from HuggingFace on first run (~4-12 GB depending on model).

---

## Agent Workflow

### 1. Ask the user

```
Before I generate images, I need to know:

🎨 Prompt  (required)
   Describe what you want to see, e.g.:
   "a cat sitting on a couch, photorealistic, warm lighting"

🚫 Negative prompt  (optional)
   Default: "worst quality, low quality, blurry, distorted, ugly"

📐 Image settings
   - width       — image width in pixels  (default: 1024)
   - height      — image height in pixels (default: 1024)

🤖 Model  (optional)
   Available: flux (default), flux-schnell, sdxl, sd3, playground
   Or specify any HuggingFace model ID

⚙️ Generation settings
   - steps   — inference steps (default: varies by model)
   - cfg     — guidance scale / prompt adherence (default: varies)
   - seed    — random seed for reproducibility (optional)
   - num_images — number of images to generate (default: 1)

📁 Output directory  (default: ./output)
```

Wait for user response before proceeding.

### 2. Edit config.json

Write or update `$SKILL_DIR/config.json` based on the user's choices.

### 3. Run

```bash
cd "$SKILL_DIR" && uv run python scripts/txt2img.py --config config.json
```

### 4. Report results

Tell the user the output file path(s) and generation settings used.

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `model` | string | `flux` | Model key or HuggingFace model ID |
| `output_dir` | path | `./output` | Destination folder |
| `prompt` | string | *(required)* | Text description of desired image |
| `negative_prompt` | string | *(see above)* | Things to avoid |
| `width` | int | `1024` | Image width (multiple of 8 for FLUX) |
| `height` | int | `1024` | Image height (multiple of 8 for FLUX) |
| `num_inference_steps` | int | *varies* | Diffusion steps |
| `guidance_scale` | float | *varies* | Prompt adherence strength |
| `seed` | int or null | `null` | Random seed for reproducibility |
| `num_images` | int | `1` | Number of images to generate |

---

## Common Invocations

```bash
# Generate with FLUX (default)
cd "$SKILL_DIR" && uv run python scripts/txt2img.py \
  --prompt "a photorealistic cat on a couch"

# Generate multiple images with specific seeds
cd "$SKILL_DIR" && uv run python scripts/txt2img.py \
  --prompt "landscape at sunset" --num-images 4 --seed 42

# Use SDXL for faster generation
cd "$SKILL_DIR" && uv run python scripts/txt2img.py \
  --model sdxl --prompt "cyberpunk city neon lights"

# Use custom model
cd "$SKILL_DIR" && uv run python scripts/txt2img.py \
  --model "runwayml/stable-diffusion-v1-5" \
  --prompt "your prompt here"

# Lower resolution for speed
cd "$SKILL_DIR" && uv run python scripts/txt2img.py \
  --prompt "abstract art" --width 512 --height 512 --steps 15
```

---

## Output

Generated images are saved to `output_dir` as PNG files with timestamp names:
```
20240315_143022_001.png
20240315_143022_002.png
```

---

## Error Handling

- Insufficient VRAM → prints required vs available GB, tips to free VRAM, exits
- No CUDA GPU → clear error message, exits
- Invalid model → attempts auto-detection, falls back gracefully
- Generation errors → logged per-image; other images continue

---

## Adding Custom Models

Any diffusers-compatible model from HuggingFace can be used by passing its
model ID as the `--model` argument:

```bash
uv run python scripts/txt2img.py \
  --model "your-username/your-model" \
  --prompt "your prompt"
```

The script will attempt to auto-detect the model architecture.
