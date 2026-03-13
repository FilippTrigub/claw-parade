---
name: snip
description: >-
  Cut videos into segments, rearrange them, and produce an output video
  with a specific cuts-per-second rate. Uses MoviePy for video manipulation.
  Prioritizes audio transcription for timestamped cutting, falls back to
  adaptive scene detection.
metadata:
  {
    "openclaw":
      {
        "emoji": "✂️",
        "requires": { "bins": ["ffmpeg", "uv"] },
      },
  }
---

# clawcut — Video Cutting and Rearranging

Cuts videos into segments, reorders them, and exports at a specified frame rate.
Useful for creating highlight reels, reordering scenes, or changing video pacing.

The skill directory (where this SKILL.md lives) is referred to as `$SKILL_DIR` below.

---

## When to Use

Use this skill when the user wants to:
- Cut a video into specific segments
- Rearrange video segments in a different order
- Remove unwanted sections from a video
- Change the output frame rate (cuts per second)
- **Auto-detect speech segments** for natural cuts (prioritized)
- Auto-detect scene changes as fallback

---

## Setup (first run only)

```bash
cd "$SKILL_DIR" && uv sync
```

---

## Agent Workflow

### 1. Ask the user

```
Before I cut the video(s), I need to know:

📹 Source video(s)
   List the video files and their locations

✂️ Segments to cut
   For each segment, specify:
   - source: filename
   - start: start time in seconds (e.g., 0.0, 5.5)
   - end: end time in seconds (e.g., 2.0, 10.0)
   
   Example segments:
   [
     {"source": "video.mp4", "start": 0.0, "end": 1.0},
     {"source": "video.mp4", "start": 3.0, "end": 4.5},
     {"source": "video.mp4", "start": 1.5, "end": 2.5}
   ]

🎬 Output FPS (optional)
   Default: 30 fps
   Common options: 24, 30, 60

📁 Input / output directories (default: ./input and ./output)
```

Wait for user response before proceeding.

### 2. Determine Cutting Strategy

**Priority Order:**
1. **Explicit segments** — If user provides specific start/end times, use those
2. **Audio transcription** — If `transcription.enabled: true` (default), look for or generate transcription and cut at speech segment boundaries
3. **Adaptive scene detection** — Fallback if transcription unavailable or fails

### Audio Transcription (Primary Method)

The skill will first try to use **audio transcription** to get timestamped speech segments from the video. This produces more natural cuts aligned with spoken content.

```
🤖 Audio Transcription Mode (PRIORITY)

The cutter will:
1. Look for an existing transcription JSON in output_dir (e.g., video_transcription.json)
2. If not found, run audio transcription automatically
3. Cut video at speech segment boundaries

⚙️ Configuration:
   - transcription.enabled: true (default)
   - fallback_to_adaptive: true (default) — use scene detection if transcription fails
   - min_segment_duration: minimum seconds per segment (default: 1.0)
   - max_segment_duration: maximum seconds per segment (default: 30.0)

Example config:
{
  "segments": [{"source": "video.mp4", "start": 0, "end": 60}],
  "transcription": {
    "enabled": true,
    "fallback_to_adaptive": true,
    "min_segment_duration": 1.0,
    "max_segment_duration": 30.0
  }
}
```

### Adaptive Scene Detection (Fallback)

If transcription is disabled or fails, the skill falls back to visual scene detection:

```
🎬 Adaptive Scene Detection (FALLBACK)

Automatically detect scene changes in your video to create cuts.
This avoids boring, repetitive content by cutting at natural transitions.

⚙️ Detection mode:
   - adaptive  — Best for varying lighting/gradual changes [default]
   - content   — Best for fast, clear scene cuts
   - threshold — Best for fade in/out detection

📏 Scene duration filters:
   - min_scene_duration: minimum seconds per scene (default: 1.0)
   - max_scene_duration: maximum seconds per scene (default: 10.0)

🎛️ Advanced (optional):
   - threshold: pixel diff threshold for content mode (default: 27.0)
   - adaptive_threshold: ratio threshold for adaptive mode (default: 3.0)
   - window_width: frames to average (default: 2)
   - min_scene_len: minimum frames before cut (default: 15)
   - min_content_val: minimum content change (default: 15.0)

Example config with auto-detect fallback:
{
  "segments": [{"source": "video.mp4", "start": 0, "end": 60}],
  "transcription": {
    "enabled": false
  },
  "auto_detect": {
    "enabled": true,
    "mode": "adaptive",
    "min_scene_duration": 1.0,
    "max_scene_duration": 10.0
  }
}
```

### 3. Edit config.json

Write or update `$SKILL_DIR/config.json` based on the user's choices.

### 4. Run

```bash
cd "$SKILL_DIR" && uv run python scripts/cutter.py --config config.json
```

### 5. Report results

Tell the user the output file path, duration, and FPS. Mention which method was used (transcription-based or scene detection).

---

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `input_dir` | path | `./input` | Folder containing input videos |
| `output_dir` | path | `./output` | Destination folder |
| `segments` | array | *(required)* | List of segment definitions |
| `output_fps` | integer | `30` | Output frame rate |

### Segment Definition

| Key | Type | Description |
|-----|------|-------------|
| `source` | string | Filename in input_dir |
| `start` | float | Start time in seconds |
| `end` | float | End time in seconds |

### Transcription (Priority Method)

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `enabled` | boolean | `true` | Enable transcription-based cutting |
| `fallback_to_adaptive` | boolean | `true` | Use scene detection if transcription fails |
| `min_segment_duration` | float | `1.0` | Skip segments shorter than this (seconds) |
| `max_segment_duration` | float | `30.0` | Skip segments longer than this (seconds) |

### Auto-Detect (Fallback)

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `enabled` | boolean | `false` | Enable automatic scene detection (fallback only) |
| `mode` | `adaptive`, `content`, `threshold` | `adaptive` | Detection algorithm |
| `min_scene_duration` | float | `1.0` | Skip scenes shorter than this (seconds) |
| `max_scene_duration` | float | `10.0` | Skip scenes longer than this (seconds) |
| `threshold` | float | `27.0` | Pixel diff threshold for content/threshold mode |
| `adaptive_threshold` | float | `3.0` | Ratio threshold for adaptive mode |
| `window_width` | int | `2` | Frames to average before/after |
| `min_scene_len` | int | `15` | Minimum frames before a cut |
| `min_content_val` | float | `15.0` | Minimum content change |

#### Detection Modes (Fallback)

- **adaptive** (default): Best for videos with varying lighting or gradual transitions
- **content**: Best for videos with sharp, clear scene cuts
- **threshold**: Best for detecting fade in/out transitions

---

## Common Invocations

```bash
# Default config (uses transcription if available, falls back to adaptive)
cd "$SKILL_DIR" && uv run python scripts/cutter.py --config config.json

# Force adaptive scene detection (skip transcription)
cd "$SKILL_DIR" && uv run python scripts/cutter.py --config config.json --no-transcription

# Custom directories
cd "$SKILL_DIR" && uv run python scripts/cutter.py \
  --input /path/to/videos --output /path/to/output
```

---

## Output

Each config produces one `output.mp4` in `output_dir` containing the concatenated segments.
Audio is preserved from the original video segments.

---

## Error Handling

- No segments defined → error message, exits
- Invalid segment times → clear error with expected format
- Source video not found → error with file not found
- Transcription fails → falls back to adaptive if enabled, else error
- Individual segment errors → logged; other segments continue
