# OpenClaw - Personal Brand Agent

> **AI-powered personal brand management system** that automates the creation, adaptation, and scheduling of social media content.

Transform raw inputs (articles, notes, ideas, meeting notes) into polished, multi-channel posts complete with branded images and videos.

---

## Features

- **Brand Consistency**: Maintains your unique voice, tone, and visual identity across all content
- **Multi-Channel Output**: Generate platform-specific content for Instagram, LinkedIn, Twitter, and more
- **Media Generation**: Automated image and video processing with brand-aligned visuals
- **Smart Scheduling**: Buffer-based scheduling with optimal posting times
- **Modular Skills**: Extensible skill system for custom workflows

---

## Quick Start

### Prerequisites

- Git (for submodule management)
- Docker (for containerized deployment)

### Initialize Project

```bash
# Clone the repository
git clone <repo-url>
cd claw-parade

# Initialize skills as submodules
git submodule add https://github.com/FilippTrigub/clawvig skills/video-processing
git submodule add https://github.com/FilippTrigub/clawimig skills/image-processing

# Update submodules
git submodule update --init --recursive
```

### Build Docker Image

```bash
# Build the base image first
make build-base

# Build the local image
docker build -t clawparade .
```

### Run the Agent

```bash
# Initialize brand from your content
docker run -v $(pwd)/input:/input clawparade claw init --input /input/

# Process content for a channel
docker run -v $(pwd)/input:/input -v $(pwd)/output:/output clawparade \
  claw process --input /input/article.md --channel instagram

# Schedule content with a 5-day buffer
docker run -v $(pwd)/output:/output clawparade \
  claw schedule --buffer-days 5
```

---

## Workflow

### Phase 1: Brand Initialization (One-Time)

Establish your brand identity by analyzing your content, resume, and past posts. This generates `BRAND.md` with:
- Voice and tone guidelines
- Visual identity specifications
- Core values and messaging

```bash
claw init --input ./raw-inputs/
```

### Phase 2: Content Processing (Regular Use)

```bash
# Process a single file
claw process --input ./input/article.md --channel instagram

# Process video content
claw process --input ./input/meeting.mp4 --channel linkedin --video

# Bulk process from folder
claw process --folder ./input/ --channel twitter

# Schedule with buffer
claw schedule --buffer-days 5
```

---

## Directory Structure

```
claw-parade/
├── SOUL.md              # Agent identity and behavior specification
├── BRAND.md             # Generated brand spec (created by init)
├── WORKFLOW.md          # Detailed workflow documentation
├── Dockerfile           # Container build configuration
├── skills/              # Modular skill definitions
│   ├── brand-awareness/ # Brand identity maintenance
│   ├── video-processing/ # Video processing (submodule)
│   └── image-processing/ # Image processing (submodule)
├── input/               # Raw input files (articles, notes, ideas)
└── output/              # Processed content organized by channel
    ├── instagram/
    ├── linkedin/
    └── twitter/
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [SOUL.md](./SOUL.md) | Agent identity, persona, and behavior specs |
| [WORKFLOW.md](./WORKFLOW.md) | Complete processing workflow and best practices |
| [Skills](./skills/) | Individual skill documentation and configuration |

---

## Environment Configuration

```bash
CLAW_BRAND_FILE=./BRAND.md         # Path to brand specification
CLAW_INPUT_DIR=./input/            # Raw input location
CLAW_OUTPUT_DIR=./output/          # Processed output location
CLAW_GDRIVE_ENABLED=true           # Enable Google Drive sync
CLAW_BUFFER_DAYS=5                 # Default buffer days
CLAW_DEFAULT_CHANNEL=instagram     # Default target channel
```

---

## License

Copyright © 2026 Filipp Trigub. All rights reserved.
