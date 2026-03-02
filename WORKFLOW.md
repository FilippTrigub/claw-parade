# OpenClaw Personal Brand Agent - Workflow

## Overview

This agent transforms raw inputs into polished, multi-channel social media content with images/videos. It maintains brand consistency throughout and schedules publications via Buffer.

---

## Typical Workflow

### Phase 1: Init (One-Time Setup)

**Goal**: Establish brand state and create BRAND.md specification

**Steps**:
1. Gather raw input about the brand persona (resume, bios, past content, notes)
2. Run `brand-awareness` skill → `read-about-me` tool
3. Review generated BRAND.md
4. Adjust if needed based on additional information

**Output**: BRAND.md file with complete brand identity specification

---

### Phase 2: Regular Processing (Per Content Item)

**Goal**: Process raw input into ready-to-publish content

#### 2.1 Read Raw Input
```
Input: New article link, meeting notes, idea snippet, blog post draft
Action: Extract key insights, main points, and content opportunities
Output: Content brief with highlights and angles
```

#### 2.2 Generate Post Draft
```
Input: Content brief
Action: Create initial post content based on main insights
Output: Draft post (generic, not yet brand-aligned)
```

#### 2.3 Adapt to Brand
```
Input: Draft post, BRAND.md, target channel (e.g., "instagram")
Action: Run `brand-awareness` skill → `adapt-content-to-brand` tool
Output: Brand-aligned post ready for channel formatting
```

#### 2.4 Process Media (Image/Video)

**Images** — use the `clawimig` skill:
```bash
# Install deps (first run only)
cd skills/image-processing/scripts && uv sync && npm install

# Run the pipeline
uv run --project skills/image-processing/scripts \
  python skills/image-processing/scripts/process.py --config config.json
```
Output lands in `output/` (path set in `config.json`).

**Videos** — use the `clawvig` skill:
```bash
# Install deps (first run only)
cd ~/.openclaw/skills/clawvig && uv sync

# Cinematic preset with futuristic captions
cd ~/.openclaw/skills/clawvig && uv run python scripts/caption_service.py \
  --output output --preset cinematic \
  --css ~/.openclaw/skills/clawvig/scripts/futuristic.css
```
Output lands in `~/.openclaw/skills/clawvig/output/`.

#### 2.5 Organize Output
```
Input: Final post text + media files
Action: Save to local output directory
Organize by: channel / date (YYYY/MM/DD) / status
Output: Files stored in output/[channel]/[date]/
```

#### 2.6 Schedule with Buffer

Use the `buffer` skill scripts from `skills/buffer/scripts/`:

```bash
# Get your org ID (one-time)
uv run organizations.py list

# Schedule an image post
uv run posts.py create \
  --channel-id CHANNEL_ID \
  --text "Post text here" \
  --mode customScheduled \
  --due-at "2026-04-01T12:00:00Z" \
  --image-url output/instagram/2026-04-01/photo.jpg

# Schedule a video reel (local file served automatically via cloudflared)
uv run posts.py create \
  --channel-id CHANNEL_ID \
  --text "Reel caption here" \
  --mode customScheduled \
  --due-at "2026-04-01T12:00:00Z" \
  --video-url output/instagram/2026-04-01/video.mp4 \
  --ig-type reel
```

Local file paths for `--image-url` and `--video-url` are handled automatically — no manual upload step required. See the `buffer` skill for full details.

---

## Directory Structure

```
claw-parade/
├── SOUL.md                    # Agent identity and behavior spec
├── BRAND.md                   # Brand identity (generated)
├── WORKFLOW.md                # This file
├── skills/
│   ├── brand-awareness/
│   │   └── SKILL.md          # Brand awareness skill definition
│   ├── video-processing/      # Submodule: clawvig
│   ├── image-processing/      # Submodule: clawimig
│   └── buffer/                # Buffer scheduling skill
├── input/                     # Raw input files
│   └── [user-provided content]
└── output/                    # Processed outputs
    ├── instagram/
    │   └── [YYYY/MM/DD]/
    ├── linkedin/
    └── twitter/
```

---

## Skill Integration Map

| Skill | Location | Purpose |
|-------|----------|---------|
| brand-awareness | `skills/brand-awareness/` | Brand identity maintenance |
| video-processing | `skills/video-processing/` (clawvig) | Video enhancement and captioning |
| image-processing | `skills/image-processing/` (clawimig) | Image resize, crop, and filtering |
| buffer | `skills/buffer/` | Schedule and publish posts |

---

## Quick Start

### First Time Setup
```bash
# 1. Initialize brand (init phase)
# Provide raw input files in input/, then run brand-awareness skill

# 2. Process media
cd skills/image-processing/scripts && uv sync && npm install
cd skills/video-processing && uv sync

# 3. Install Buffer script deps
cd skills/buffer/scripts && uv sync
```

### Regular Use
```bash
# Process images
uv run --project skills/image-processing/scripts \
  python skills/image-processing/scripts/process.py --config config.json

# Process video
cd ~/.openclaw/skills/clawvig && uv run python scripts/caption_service.py \
  --output output --preset cinematic

# Schedule post (local file paths work directly)
cd skills/buffer/scripts
uv run posts.py create \
  --channel-id CHANNEL_ID \
  --text "Caption here" \
  --mode addToQueue \
  --image-url ../../output/instagram/photo.jpg
```

---

## Configuration

### Environment Variables
```bash
BUFFER_API_KEY=your-buffer-token   # Required for scheduling
CLAW_BRAND_FILE=./BRAND.md         # Path to brand spec
CLAW_INPUT_DIR=./input/            # Raw input location
CLAW_OUTPUT_DIR=./output/          # Processed output location
CLAW_BUFFER_DAYS=5                 # Default buffer days
CLAW_DEFAULT_CHANNEL=instagram     # Default target channel
```

### BRAND.md Location
The BRAND.md file should be in the project root. If missing, the agent will trigger the Init phase automatically.

---

## Error Handling

| Issue | Resolution |
|-------|------------|
| No BRAND.md | Auto-trigger Init phase |
| Unclear input | Request clarification via chat |
| Media generation fail | Fall back to templates |
| Scheduling fail | Queue to manual review |
| Channel not supported | Suggest alternative channels |

---

## Best Practices

1. **Start with Init** - Don't skip brand setup
2. **Keep inputs clean** - Clear, well-formatted input = better output
3. **Review before schedule** - Always check final content
4. **Maintain buffer** - Keep 3-7 days of scheduled content
5. **Iterate on brand** - Update BRAND.md as persona evolves
