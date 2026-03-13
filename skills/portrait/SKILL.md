---
name: portrait
description: >-
  Apply synthetic depth-of-field bokeh to photos using MiDaS monocular depth
  estimation. Makes phone photos look like they were shot with a fast prime lens.
  No depth sensor required — works from a single image.
metadata:
  {
    "openclaw":
      {
        "emoji": "📷",
        "requires": { "bins": ["uv"] },
      },
  }
---

# clawdepth — Synthetic Bokeh via Depth Estimation

Estimates per-pixel depth from each image using Intel MiDaS, then applies
variable lens blur: near objects stay sharp, far objects blur progressively.

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

---

## When to Use

Use this skill when the user wants to:
- Add a portrait-mode / DSLR-style shallow depth-of-field effect
- Make phone photos look more professional
- Blur distracting backgrounds without manual masking

---

## Setup (first run only)

```bash
cd "$SKILL_DIR" && uv sync
```

MiDaS weights are downloaded from torch.hub on first use (~400 MB for DPT_Large).

---

## Agent Workflow

### 1. Ask the user

```
Before I process the images, I need to know:

🌀 Blur strength  (1–50, default: 15)
  Stronger = more pronounced bokeh.
  Subtle effect: 5–10  |  Natural: 12–18  |  Heavy: 20+

🧠 Model
  - DPT_Large   — most accurate depth, slower  (default)
  - DPT_Hybrid  — good balance
  - MiDaS_small — fastest, lower depth quality

⚙️  Device
  - auto   — GPU if available, else CPU (default)
  - cpu    — force CPU (~5s/image, fine for small batches)

📁 Input / output directories  (default: ./input and ./output)
```

### 2. Edit config.json

### 3. Run

```bash
cd "$SKILL_DIR" && uv run python scripts/bokeh.py --config config.json
```

### 4. Report results

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `input_dir` | path | `./input` | Source image folder |
| `output_dir` | path | `./output` | Destination folder |
| `model` | `DPT_Large`, `DPT_Hybrid`, `MiDaS_small` | `DPT_Large` | Depth model |
| `blur_strength` | 1–50 | `15` | Maximum blur radius in pixels |
| `device` | `auto`, `cpu`, `cuda` | `auto` | Inference device |

---

## Common Invocations

```bash
# Default settings
cd "$SKILL_DIR" && uv run python scripts/bokeh.py

# Stronger blur
cd "$SKILL_DIR" && uv run python scripts/bokeh.py --blur-strength 25

# Fast mode (lower quality depth)
cd "$SKILL_DIR" && uv run python scripts/bokeh.py --model MiDaS_small

# Force CPU
cd "$SKILL_DIR" && uv run python scripts/bokeh.py --device cpu
```

---

## Output

Processed images written to `output_dir` with the same filenames as input.

---

## Error Handling

- Missing input_dir → exits with clear message
- Individual image failures → logged; other images continue
- Depth model download failure → shows torch.hub error with fix suggestion
