---
name: clawcut
description: >-
  Cut videos into segments, rearrange them, and produce an output video
  with a specific cuts-per-second rate. Uses MoviePy for video manipulation.
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
- **Auto-detect scene changes** to avoid monotony (smart cutting)

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

### Smart Auto-Detect (Optional)

If the user wants **automatic scene detection** to avoid monotony:

```
🤖 Auto-Detect Mode

I can automatically detect scene changes in your video to create cuts.
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

Example config with auto-detect:
{
  "segments": [{"source": "video.mp4", "start": 0, "end": 60}],
  "auto_detect": {
    "enabled": true,
    "mode": "adaptive",
    "min_scene_duration": 1.0,
    "max_scene_duration": 10.0,
    "adaptive_threshold": 3.0,
    "window_width": 2,
    "min_scene_len": 15
  }
}
```

### 2. Edit config.json

Write or update `$SKILL_DIR/config.json` based on the user's choices.

### 3. Run

```bash
cd "$SKILL_DIR" && uv run python scripts/cutter.py --config config.json
```

### 4. Report results

Tell the user the output file path, duration, and FPS.

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

### Auto-Detect (Optional)

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `enabled` | boolean | `true` | Enable automatic scene detection |
| `mode` | `adaptive`, `content`, `threshold` | `adaptive` | Detection algorithm |
| `min_scene_duration` | float | `1.0` | Skip scenes shorter than this (seconds) |
| `max_scene_duration` | float | `10.0` | Skip scenes longer than this (seconds) |
| `threshold` | float | `27.0` | Pixel diff threshold for content/threshold mode (lower = more sensitive) |
| `adaptive_threshold` | float | `3.0` | Ratio threshold for adaptive mode (lower = more sensitive) |
| `window_width` | int | `2` | Frames to average before/after (higher = smoother, slower) |
| `min_scene_len` | int | `15` | Minimum frames before a cut can be registered |
| `min_content_val` | float | `15.0` | Minimum content change to register as new scene |

#### Detection Modes

- **adaptive** (default): Best for videos with varying lighting or gradual transitions. Uses rolling average to smooth detections.
- **content**: Best for videos with sharp, clear scene cuts. Uses fixed threshold on pixel differences.
- **threshold**: Best for detecting fade in/out transitions. Uses brightness threshold.

---

## Common Invocations

```bash
# Default config
cd "$SKILL_DIR" && uv run python scripts/cutter.py --config config.json

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
- Individual segment errors → logged; other segments continue
