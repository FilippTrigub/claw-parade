---
name: knockout
description: >-
  Remove backgrounds from images using rembg (IS-Net / U2Net). Outputs
  transparent PNGs or composites onto a solid colour or custom backdrop image.
  Works on portraits, products, and general subjects.
metadata:
  {
    "openclaw":
      {
        "emoji": "✂️",
        "requires": { "bins": ["uv"] },
      },
  }
---

# knockout — Background Removal

Removes image backgrounds using rembg (IS-Net by default). The foreground
can be kept as a transparent PNG or composited onto a custom background.

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

---

## When to Use

Use this skill when the user wants to:
- Remove the background from portrait or product photos
- Place subjects onto a branded or custom background
- Prepare clean cutouts for other tools (e.g. clawimig padding, clawdepth)

---

## Setup (first run only)

```bash
cd "$SKILL_DIR" && uv sync
```

Model weights are downloaded automatically on first use (~180 MB for IS-Net).

---

## Agent Workflow

### 1. Ask the user

```
Before I process the images, I need to know:

✂️ Background
  - none          — keep as transparent PNG
  - #rrggbb       — solid colour (e.g. "#ffffff" or "#1a1a2e")
  - /path/to/img  — composite onto a background image

🧠 Model (optional, default: isnet-general-use)
  - isnet-general-use  — best for most subjects
  - u2net_human_seg    — optimised for people
  - isnet-anime        — optimised for illustrated/anime characters

⚙️  Device
  - auto  — GPU if available, else CPU (default)
  - cpu   — force CPU (~3s/image via ONNX CPU provider)

📁 Input / output directories  (default: ./input and ./output)
```

### 2. Edit config.json

### 3. Run

```bash
cd "$SKILL_DIR" && uv run python scripts/rembg_batch.py --config config.json
```

### 4. Report results

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `input_dir` | path | `./input` | Source image folder |
| `output_dir` | path | `./output` | Destination folder |
| `model` | see models below | `isnet-general-use` | Segmentation model |
| `bg` | null / hex / path | `null` | Background (null = transparent) |
| `output_format` | `png`, `webp` | `png` | Output format |
| `device` | `auto`, `cpu`, `cuda` | `auto` | Inference device |

**Available models:** `isnet-general-use`, `isnet-anime`, `u2net`, `u2net_human_seg`, `u2netp`, `birefnet-general`

---

## Common Invocations

```bash
# Transparent PNG
cd "$SKILL_DIR" && uv run python scripts/rembg_batch.py

# White background
cd "$SKILL_DIR" && uv run python scripts/rembg_batch.py --bg "#ffffff"

# Dark brand background
cd "$SKILL_DIR" && uv run python scripts/rembg_batch.py --bg "#0d1117"

# Custom backdrop image
cd "$SKILL_DIR" && uv run python scripts/rembg_batch.py --bg ./brand-backdrop.jpg

# Force CPU
cd "$SKILL_DIR" && uv run python scripts/rembg_batch.py --device cpu

# Portrait-optimised model
cd "$SKILL_DIR" && uv run python scripts/rembg_batch.py --model u2net_human_seg
```

---

## Output

Processed images written to `output_dir` as PNG (or WebP), same stem as input.
