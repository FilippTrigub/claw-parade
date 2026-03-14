---
name: grade
description: >-
  Score a folder of images by visual quality and copy the top-K to output.
  Uses CLIP (aesthetic mode, no prompt needed) or PickScore (pick mode, ranked
  against a text prompt). Ideal for culling large photo batches automatically.
metadata:
  {
    "openclaw":
      {
        "emoji": "🏆",
        "requires": { "bins": ["uv"] },
      },
  }
---

# grade — Aesthetic Image Auto-Selection

Scores images by perceived visual quality and copies the top-K to output.
Eliminates manual photo culling.

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

---

## When to Use

Use this skill when the user wants to:
- Pick the best photos from a large batch automatically
- Rank images by visual quality without manual review
- Select images most relevant to a specific subject or style (with `--mode pick`)

---

## Setup (first run only)

```bash
cd "$SKILL_DIR" && uv sync
```

On first use, CLIP or PickScore weights are downloaded from HuggingFace (~1–5 GB).

---

## Agent Workflow

### 1. Ask the user

```
Before I score the images, I need to know:

🏆 Mode
  - aesthetic  — rank by general visual quality (no prompt needed)
  - pick       — rank by relevance to a text prompt

🔢 How many to keep?  (default: 3)

💬 Prompt (only for pick mode)
  e.g. "warm, natural light, outdoor portrait"

⚙️  Device
  - auto   — GPU if available, else CPU (default)
  - cpu    — force CPU (~2s/image, fine for small batches)

📁 Input / output directories  (default: ./input and ./output)
```

Wait for user response before proceeding.

### 2. Edit config.json

Write or update `$SKILL_DIR/config.json` based on the user's choices.

### 3. Run

```bash
cd "$SKILL_DIR" && uv run python scripts/score.py --config config.json
```

### 4. Report results

Tell the user which images were selected, their scores, and where they were copied.

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `input_dir` | path | `./input` | Source image folder |
| `output_dir` | path | `./output` | Destination folder |
| `mode` | `aesthetic`, `pick` | `aesthetic` | Scoring strategy |
| `top` | integer ≥ 1 | `3` | Number of images to copy |
| `prompt` | string or null | `null` | Required for `mode=pick` |
| `device` | `auto`, `cpu`, `cuda` | `auto` | Inference device |

---

## Common Invocations

```bash
# Default: pick top 3 by aesthetic score
cd "$SKILL_DIR" && uv run python scripts/score.py

# Pick top 5 matching a prompt
cd "$SKILL_DIR" && uv run python scripts/score.py \
  --mode pick --prompt "warm golden hour portrait" --top 5

# Force CPU (LLM is using the GPU)
cd "$SKILL_DIR" && uv run python scripts/score.py --device cpu

# Custom input/output directories
cd "$SKILL_DIR" && uv run python scripts/score.py \
  --input /path/to/photos --output /path/to/selected
```

---

## Output

Selected images are copied to `output_dir` with rank prefix:
```
01_photo.jpg   ← best
02_photo.jpg
03_photo.jpg
```

---

## Error Handling

- No images in input_dir → clear message, exits cleanly
- Invalid config → all errors printed before any images are scored
- Individual image errors → logged; other images continue
