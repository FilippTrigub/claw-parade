---
name: mux
description: >-
  Instagram video enhancement and captioning pipeline. Use this skill when
  the user wants to process, enhance, grade, or caption videos for
  Instagram — including sharpening, colour grading, warmth adjustments,
  audio normalisation, or burning animated captions.
metadata:
  {
    "openclaw":
      {
        "emoji": "🎬",
        "requires": { "bins": ["ffmpeg", "uv"] },
      },
  }
---

# mux — Instagram Video Pipeline

Enhances videos (sharpening, colour grading, warmth) and burns in animated captions. Enhancement runs before captioning so filters don't interact with caption rendering.

## Pipeline

```
input video → enhance (ffmpeg filters + -14 LUFS audio) → captions (pycaps) → output/
```

## Presets

| Preset | Sharpness | Saturation | Warmth |
|---|---|---|---|
| `natural` | subtle | +10% | none |
| `cinematic` | strong | +35% | warm (red boost, blue reduce) |
| `vivid` | strong | +40% | none |

If the user has not specified a preset, ask them which look they want before running. Describe the options briefly: `natural` for a clean, understated result; `cinematic` for a warm, punchy Instagram-ready grade; `vivid` for maximum colour intensity. A preset is optional — omit `--preset` entirely if the user wants captions only with no colour grading.

## Caption style (CSS)

Captions are styled via a CSS file passed with `--css`. Three options are available:

1. **Default (no flag)** — the pycaps built-in minimalist style: plain white text, no effects.
2. **Futuristic (bundled)** — `--css ~/.openclaw/skills/clawvig/scripts/futuristic.css` — alternating gold/magenta captions with a glow effect and monospace font. Good for tech, gaming, or high-energy content.
3. **Custom** — the user can supply any CSS file path via `--css /path/to/custom.css`.

If the user has not mentioned a caption style, ask whether they want the default look, the futuristic style, or a custom CSS file. If they provide a CSS file path, pass it directly.

## Directory layout

The scripts are bundled at `~/.openclaw/skills/clawvig/scripts/`.
Input videos must be placed in the `input/` directory inside the clawvig skill folder: `~/.openclaw/skills/clawvig/input/`.
Output lands in `~/.openclaw/skills/clawvig/output/`.

## How to run

Before the first run, install Python dependencies:

```bash
cd ~/.openclaw/skills/clawvig && uv sync
```

**Note:** the very first run will be slow (potentially several minutes) because pycaps downloads the Whisper speech recognition model. Warn the user about this before starting.

Then process videos:

```bash
cd ~/.openclaw/skills/clawvig && uv run python scripts/caption_service.py \
  --output <path/to/output> \
  [--preset natural|cinematic|vivid] \
  [--css <path/to/style.css>]
```

## Common invocations

```bash
# Cinematic preset, futuristic captions
cd ~/.openclaw/skills/clawvig && uv run python scripts/caption_service.py \
  --output output --preset cinematic \
  --css ~/.openclaw/skills/clawvig/scripts/futuristic.css

# Default captions, no enhancement
cd ~/.openclaw/skills/clawvig && uv run python scripts/caption_service.py \
  --output output

# Vivid + custom caption style
cd ~/.openclaw/skills/clawvig && uv run python scripts/caption_service.py \
  --output output --preset vivid --css /path/to/my.css
```

## After running

Once the command completes, report back to the user:
- How many videos were processed successfully and how many failed.
- The full path to the output directory so they can find the results: `~/.openclaw/skills/clawvig/output/`.
- If any videos failed, name them explicitly.

## Edge cases

- If `ffmpeg` is not installed: tell the user to install it (`sudo pacman -S ffmpeg` on Arch/CachyOS, `brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Ubuntu)
- If `uv` is not installed: direct to https://docs.astral.sh/uv/getting-started/installation/
- If the input directory is empty: report clearly rather than silently exiting
- If an unknown preset is given: list the valid options (natural, cinematic, vivid)
- Audio normalisation may print a warning about dynamic mode for short clips — this is expected and not an error
