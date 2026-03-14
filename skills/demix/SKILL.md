---
name: demix
description: >-
  Separate audio stems (vocals, instruments, drums, bass) from video or audio
  files using Meta Demucs. For video inputs, remuxes the chosen stem back into
  the video. Works on CPU (~3-5× realtime) with full quality.
metadata:
  {
    "openclaw":
      {
        "emoji": "🎙️",
        "requires": { "bins": ["uv", "ffmpeg"] },
      },
  }
---

# demix — Audio Source Separation

Separates audio stems from video or audio files using Meta's Demucs model.
For video inputs, the selected stem is remuxed back into the video (original
video track unchanged). For audio inputs, WAV stem files are written alongside.

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

---

## When to Use

Use this skill when the user wants to:
- Remove background music from a talking-head video (extract clean vocals)
- Strip vocals to get an instrumental track
- Clean up video audio before normalisation in clawvig
- Prepare audio for re-mixing with clawbeat

---

## Setup (first run only)

```bash
cd "$SKILL_DIR" && uv sync
```

Demucs model weights are downloaded automatically on first use (~80 MB for htdemucs).

---

## Agent Workflow

### 1. Ask the user

```
Before I separate the audio, I need to know:

🎙️ Stem to extract
  - vocals     — isolated voice track (removes music)  (default)
  - no_vocals  — instrumental / music without vocals
  - drums      — drum track only
  - bass       — bass track only

🧠 Model (optional, default: htdemucs)
  - htdemucs      — best general quality (default)
  - htdemucs_ft   — fine-tuned, slightly better on music
  - htdemucs_6s   — 6-stem model (also separates guitar, piano)

⚙️  Device
  - auto  — GPU if available, else CPU (default)
  - cpu   — fully functional at ~3–5× realtime

📁 Input / output directories  (default: ./input and ./output)
```

### 2. Edit config.json

### 3. Run

```bash
cd "$SKILL_DIR" && uv run python scripts/separate.py --config config.json
```

### 4. Report results

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `input_dir` | path | `./input` | Source folder (video or audio files) |
| `output_dir` | path | `./output` | Destination folder |
| `stem` | `vocals`, `no_vocals`, `drums`, `bass`, `other` | `vocals` | Stem to extract |
| `model` | `htdemucs`, `htdemucs_ft`, `htdemucs_6s`, `mdx_extra`, `mdx_extra_q` | `htdemucs` | Demucs model |
| `device` | `auto`, `cpu`, `cuda` | `auto` | Inference device |
| `mp3_bitrate` | integer | `320` | Bitrate for MP3 output |

**Supported input formats:** `.mp4`, `.mov`, `.avi`, `.mkv`, `.m4v`, `.webm`, `.mp3`, `.wav`, `.aac`, `.flac`

---

## Common Invocations

```bash
# Extract clean vocals from a video (default)
cd "$SKILL_DIR" && uv run python scripts/separate.py

# Get the instrumental (remove vocals from music)
cd "$SKILL_DIR" && uv run python scripts/separate.py --stem no_vocals

# Force CPU
cd "$SKILL_DIR" && uv run python scripts/separate.py --device cpu

# High-quality fine-tuned model
cd "$SKILL_DIR" && uv run python scripts/separate.py --model htdemucs_ft
```

---

## Output

**Video input:** video file written to `output_dir` with the stem audio replacing the original track.
**Audio input:** `<name>_<stem>.wav` written to `output_dir`.
