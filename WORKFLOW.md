# OpenClaw Personal Brand Agent - Workflow

## Overview

This agent transforms raw inputs into polished, multi-channel social media content with images/videos. It maintains brand consistency throughout and schedules publications with a buffer strategy.

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

**Steps**:

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
```
Input: Brand-aligned post, BRAND.md visual specs
Action:
  - Use existing clawvig for video processing/generation
  - Use clawimig for image processing/generation
  - Apply brand colors, fonts, style guidelines
Output: Processed media assets (images/videos)
```

#### 2.5 Organize to Storage
```
Input: Final post + media assets
Action: Save to Google Drive or local output directory
Organize by:
  - Date (YYYY/MM/DD)
  - Channel (instagram, linkedin, twitter)
  - Status (draft, scheduled, published)
Output: Files stored in /output/[channel]/[date]/
```

#### 2.6 Schedule with Buffer
```
Input: Ready content + media, storage paths
Action: Add to scheduling buffer
- Queue for optimal posting times
- Maintain buffer of 3-7 days
- Distribute across channels
- Avoid posting fatigue
Output: Scheduled posts in buffer queue
```

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
│   └── image-processing/      # Submodule: clawimig
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

| Skill | Repository | Purpose |
|-------|------------|---------|
| brand-awareness | local | Brand identity maintenance |
| video-processing | clawvig | Video processing/generation |
| image-processing | clawimig | Image processing/generation |
| buffer-scheduling | existing | Queue and schedule posts |

---

## Quick Start

### First Time Setup
```bash
# 1. Initialize brand (init phase)
claw init --input ./raw-inputs/

# 2. Process content (regular phase)
claw process --input ./input/article.md --channel instagram

# 3. Review and schedule
claw schedule --buffer-days 5
```

### Regular Use
```bash
# Process a new idea
claw process --input ./input/idea.txt --channel twitter

# Process video content
claw process --input ./input/meeting.mp4 --channel linkedin --video

# Bulk process from folder
claw process --folder ./input/ --channel instagram
```

---

## Configuration

### Environment Variables
```bash
CLAW_BRAND_FILE=./BRAND.md          # Path to brand spec
CLAW_INPUT_DIR=./input/             # Raw input location
CLAW_OUTPUT_DIR=./output/           # Processed output location
CLAW_GDRIVE_ENABLED=true            # Enable Google Drive sync
CLAW_BUFFER_DAYS=5                  # Default buffer days
CLAW_DEFAULT_CHANNEL=instagram      # Default target channel
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
