# clawvig

Instagram video enhancement + captioning pipeline, packaged as an OpenClaw skill.

**Pipeline:** sharpen → colour grade → warm → normalise audio to -14 LUFS → burn animated captions

## Presets

| Preset | Effect |
|---|---|
| `natural` | Subtle sharpening, slight colour boost |
| `cinematic` | Strong sharpening, vibrant + warm grade (Instagram-optimised) |
| `vivid` | Maximum saturation and sharpness |

## Prerequisites

- [`ffmpeg`](https://ffmpeg.org) — video processing binary
- [`uv`](https://docs.astral.sh/uv) — Python package manager

```bash
# Arch / CachyOS
sudo pacman -S ffmpeg

# macOS
brew install ffmpeg

# Ubuntu
sudo apt install ffmpeg
```

## Install as an OpenClaw skill

```bash
git clone https://github.com/FilippTrigub/clawvig ~/.openclaw/skills/clawvig
cd ~/.openclaw/skills/clawvig && uv sync
```

Once installed, OpenClaw picks it up automatically. Describe a video task and clawvig activates:

> "enhance the videos in ./input with the cinematic preset and add captions"

## Manual usage

```bash
cd ~/.openclaw/skills/clawvig

# With enhancement preset
uv run python scripts/caption_service.py \
  --input ./input --output ./output \
  --preset cinematic --css scripts/futuristic.css

# Captions only (no enhancement)
uv run python scripts/caption_service.py \
  --input ./input --output ./output

# Watch mode (polls every 10s for new videos)
uv run python scripts/caption_service.py \
  --input ./input --output ./output --preset cinematic --watch
```

## CSS styles

`scripts/futuristic.css` — alternating gold/magenta captions with glow effects, monospace font. Pass any CSS file via `--css`.
