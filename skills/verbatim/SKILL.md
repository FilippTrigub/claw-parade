---
name: verbatim
description: >-
  Transcribe audio from video or audio files using HuggingFace ASR models.
  Outputs per-segment JSON with timestamps and text. Uses transformers or
  nemo library. Works on GPU (~realtime) or CPU (~1–2× realtime).
metadata:
  {
    "openclaw":
      {
        "emoji": "🎤",
        "requires": { "bins": ["uv", "ffmpeg"] },
      },
  }
---

# verbatim — Audio Transcription

Transcribes audio from video or audio files using HuggingFace ASR models.
Outputs a JSON file with per-segment text and timestamps for downstream
processing (e.g., video-cutting with cuts based on speech pauses).

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

---

## When to Use

Use this skill when the user wants to:
- Transcribe video audio to text with timestamps
- Extract subtitles from a video
- Prepare transcripts for content repurposing
- Get timestamped segments for video cutting or editing
- **Automatically detect speech segments** to avoid monotony (smart cutting)

---

## Setup (first run only)

```bash
cd "$SKILL_DIR" && uv sync
```

ASR model weights are downloaded automatically on first use (typically 1–4 GB).

---

## Agent Workflow

### 1. Ask the user

```
Before I transcribe the audio, I need to know:

📹 Source file(s)
   List the video/audio files and their locations

🗣️ Language (optional)
   - en      — English (default)
   - es      — Spanish
   - fr      — French
   - de      — German
   - ja      — Japanese
   - zh      — Chinese
   - Any ISO 639-1 code supported by the model

🧠 ASR Model (optional, default: ibm-granite/granite-4.0-1b-speech)
   - ibm-granite/granite-4.0-1b-speech  — ~4GB VRAM, excellent accuracy
   - openai/whisper-large-v3            — High accuracy, ~5GB VRAM
   - distil-whisper/distil-large-v3     — Fast, good accuracy, ~2GB VRAM
   - any model ID on HuggingFace

⚙️  Device
   - auto  — GPU if available, else CPU (default)
   - cpu   — fully functional at ~1–2× realtime
   - cuda  — force GPU

📁 Input / output directories (default: ./input and ./output)
```

Wait for user response before proceeding.

### Smart Auto-Detect (Optional)

If the user wants **automatic segment detection** based on speech pauses:

```
🤖 Auto-Detect Mode

I can automatically detect speech segments based on pauses to create
natural cuts. This avoids boring, repetitive content by cutting at
natural speech boundaries.

⚙️ Pause detection:
   - min_pause: minimum seconds of silence to trigger a cut (default: 0.5)
   - max_pause: maximum seconds before starting a new segment (default: 3.0)
   - min_segment_duration: minimum seconds per segment (default: 1.0)

Example config with auto-detect:
{
  "segments": [{"source": "video.mp4", "start": 0, "end": 60}],
  "auto_detect": {
    "enabled": true,
    "min_pause": 0.5,
    "max_pause": 3.0,
    "min_segment_duration": 1.0
  }
}
```

### 2. Edit config.json

Write or update `$SKILL_DIR/config.json` based on the user's choices.

### 3. Run

```bash
cd "$SKILL_DIR" && uv run python scripts/transcriber.py --config config.json
```

### 4. Report results

Tell the user the output JSON file path, total duration transcribed, and number of segments.

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `input_dir` | path | `./input` | Folder containing input video/audio files |
| `output_dir` | path | `./output` | Destination folder for output JSON |
| `model` | string | `ibm-granite/granite-4.0-1b-speech` | HuggingFace model ID |
| `language` | ISO code | `en` | Speech language code |
| `device` | `auto`, `cpu`, `cuda` | `auto` | Inference device |
| `output_format` | `json`, `srt`, `vtt` | `json` | Output format |

**Supported input formats:** `.mp4`, `.mov`, `.avi`, `.mkv`, `.m4v`, `.webm`, `.mp3`, `.wav`, `.aac`, `.flac`

### Output JSON Format

```json
{
  "file": "video.mp4",
  "duration": 120.5,
  "language": "en",
  "model": "ibm-granite/granite-4.0-1b-speech",
  "segments": [
    {
      "start": 0.0,
      "end": 4.2,
      "text": "Hello, welcome to this demonstration video."
    },
    {
      "start": 4.5,
      "end": 8.1,
      "text": "Today we'll be exploring audio transcription."
    }
  ]
}
```

### Subtitle Formats (Optional)

When `output_format` is `srt` or `vtt`, the output will be a subtitle file:

**SRT Example:**
```srt
1
00:00:00,000 --> 00:00:04,200
Hello, welcome to this demonstration video.

2
00:00:04,500 --> 00:00:08,100
Today we'll be exploring audio transcription.
```

---

## Common Invocations

```bash
# Default config (English, IBM Granite model)
cd "$SKILL_DIR" && uv run python scripts/transcriber.py --config config.json

# Custom model (Whisper)
cd "$SKILL_DIR" && uv run python scripts/transcriber.py --model openai/whisper-large-v3

# Force CPU mode
cd "$SKILL_DIR" && uv run python scripts/transcriber.py --device cpu

# Spanish transcription
cd "$SKILL_DIR" && uv run python scripts/transcriber.py --language es

# Output as SRT subtitle file
cd "$SKILL_DIR" && uv run python scripts/transcriber.py --output-format srt
```

---

## Output

Each config produces one JSON file (default: `<input_name>_transcription.json`) in `output_dir` containing all segments with timestamps.

**Video input:** Extracts audio automatically, transcribes, outputs JSON.
**Audio input:** Transcribes directly, outputs JSON.

---

## Error Handling

- No source file found → error message, exits
- Invalid model ID → clear error with expected format
- Unsupported language → error with supported codes
- Device unavailable → fallback message if GPU requested but not available
- Model not found → error with HuggingFace model ID suggestion
