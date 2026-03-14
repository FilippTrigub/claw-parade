---
name: filter
description: >-
  Process a directory of images for Instagram using sharp (resize/crop/pad) and pilgram (Instagram filters). Reads a config.json and writes processed images to an output directory.
metadata:
  {
    "openclaw":
      {
        "emoji": "📸",
        "requires": { "bins": ["node", "python3", "uv"] },
      },
  }
---

# filter — Instagram Image Pipeline

Two-stage pipeline that prepares images for Instagram:
- **Stage 1** — resize, crop, or pad to exact Instagram dimensions (Node.js / sharp)
- **Stage 2** — apply an Instagram-style color filter (Python / pilgram)

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

---

## When to Use

Use this skill when the user wants to:
- Prepare photos for Instagram (resize, aspect ratio, padding)
- Apply Instagram-style filters to images (clarendon, gingham, etc.)
- Batch process a folder of images for social media

---

## Setup (first run only)

Install dependencies from the lock file — this guarantees reproducible versions:

```bash
# Python deps (locked)
cd "$SKILL_DIR/scripts" && uv sync

# Node deps (locked via package-lock.json)
cd "$SKILL_DIR/scripts" && npm install
```

Both lockfiles (`uv.lock`, `package-lock.json`) are committed to the skill repo — no version drift.

---

## Agent Workflow

When the user invokes this skill, follow these steps:

### 1. Ask the user for their intent before doing anything

Present the key options and confirm before writing any config or running the pipeline:

```
Before I run the pipeline, here's what I need to know:

📐 Format
  - portrait  (1080×1350, 4:5) — most common for feed photos
  - square    (1080×1080, 1:1)
  - landscape (1080×566, 1.91:1)
  - custom    (you specify width and height)

✂️ Fit (how to fill the canvas)
  - cover   — crop to fill (no padding, may cut edges)
  - contain — pad with a background color (no cropping)
  - fill    — stretch to fit (may distort)

🎨 Filter (optional)
  Available: _1977, aden, brannan, brooklyn, clarendon, earlybird, gingham,
  hudson, inkwell, kelvin, lark, lofi, maven, mayfair, moon, nashville,
  perpetua, reyes, rise, slumber, stinson, toaster, valencia, walden, willow, xpro2
  Or: none (skip filter, geometry only)

📁 Input / output directories
  Default: ./input and ./output

Which settings would you like?
```

Wait for user response before proceeding.

### 2. Write config.json

Based on the user's answers, write a `config.json` in the user's working directory:

```json
{
  "format": "portrait",
  "custom_dimensions": null,
  "background_color": "#ffffff",
  "fit": "cover",
  "filter": "clarendon",
  "output_format": "jpeg",
  "quality": 90,
  "input_dir": "./input",
  "output_dir": "./output"
}
```

See the Config Reference section below for all options.

**Multiple configs:** If the user wants to try several filters or formats, write multiple config files (e.g. `config-clarendon.json`, `config-gingham.json`) and run the pipeline once per config. Output dirs should be distinct so results don't overwrite each other.

### 3. Place images

Ensure the user's images are in `input_dir`. If they haven't copied them yet, tell them to do so and wait, or copy them yourself if you have the paths.

### 4. Run the pipeline

```bash
cd <user-project-dir>
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/process.py" --config config.json
```

For multiple configs:
```bash
for config in config-clarendon.json config-gingham.json config-lark.json; do
  uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/process.py" --config "$config"
done
```

### 5. Report results

After the run, tell the user:
- How many images succeeded / failed
- Where the output files are
- If any errors occurred, show the error messages

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `format` | `square`, `portrait`, `landscape`, `custom` | `portrait` | Instagram aspect ratio |
| `custom_dimensions` | `{"width": N, "height": N}` | `null` | Required when `format` is `custom` |
| `background_color` | hex or CSS color | `#ffffff` | Padding color for `contain` fit |
| `fit` | `contain`, `cover`, `fill` | `contain` | How to fill the target canvas |
| `filter` | pilgram filter name or `null` | `null` | Instagram-style color filter |
| `output_format` | `jpeg`, `png`, `webp` | `jpeg` | Output file format |
| `quality` | 1–100 | `90` | Compression quality (JPEG/WebP) |
| `input_dir` | path | `./input` | Folder with source images |
| `output_dir` | path | `./output` | Folder for processed images |

**Supported input formats:** `.jpg`, `.jpeg`, `.png`, `.webp`

---

## Error Handling

- Missing `input_dir` → pipeline exits with a clear error before touching any files
- Invalid config values → all validation errors are printed before any images are processed
- Per-image failures → reported individually; other images continue processing
- Non-zero exit code if any image failed — check the summary line at the end of output
