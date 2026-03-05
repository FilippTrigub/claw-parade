# 🦉 Claw-Parade - Personal Brand Agent

> **AI-powered personal brand management system** that transforms raw inputs into polished, multi-channel social media content with branded images and videos.

Transform articles, notes, ideas, and meeting recordings into ready-to-publish content across Instagram, LinkedIn, Twitter, and more — all while maintaining perfect brand consistency.

---

## 🎯 Features

| Feature | 💡 Benefit |
|---------|----------------|
| **Brand Consistency** | Maintains your unique voice, tone, and visual identity across all content |
| **Multi-Channel Output** | Generates platform-specific content for Instagram, LinkedIn, Twitter, and more |
| **Media Generation** | Automated image and video processing with brand-aligned visuals |
| **Smart Scheduling** | Buffer-based scheduling with optimal posting times |
| **Modular Skills** | Extensible skill system for custom workflows |
| **Docker Ready** | Containerized deployment with GPU acceleration |

---

## 🚀 Quick Start

### Prerequisites

- Git (for submodule management)
- Docker (for containerized deployment)
- Python with `uv` (for AI enhancement tools)

### Initialize Project

```bash
# Clone the repository
git clone <repo-url>
cd claw-parade

# Initialize skills as submodules
git submodule update --init --recursive

# Build Docker images
make build-base
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

## 📋 Workflow

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

## 📁 Directory Structure

```
claw-parade/
├── README.md              # This file
├── SOUL.md               # Agent identity and behavior specification
├── BRAND.md              # Generated brand spec (created by init)
├── WORKFLOW.md           # Detailed workflow documentation
├── Dockerfile           # Container build configuration
├── docker-compose.yml   # Container orchestration
├── skills/              # Modular skill definitions
│   ├── brand-awareness/  # Brand identity maintenance
│   ├── video-processing/  # Video enhancement and captioning
│   ├── image-processing/  # Image resize and filtering
│   ├── buffer/           # Schedule and publish posts
│   ├── + 10 standalone skills # AI enhancement tools
│   └── SKILL.md files    # Individual skill documentation
├── input/               # Raw input files (articles, notes, ideas)
└── output/              # Processed content organized by channel
    ├── instagram/
    ├── linkedin/
    └── twitter/
```

---

## 🔧 Docker Integration

### Docker Compose

```yaml
# Run as service
docker compose up openclaw-gateway

# Run CLI commands
docker compose run openclaw-cli claw init --input ./input/
```

### Environment Variables

```bash
# Core configuration
CLAW_BRAND_FILE=./BRAND.md         # Path to brand specification
CLAW_INPUT_DIR=./input/            # Raw input location
CLAW_OUTPUT_DIR=./output/          # Processed output location

# Scheduling defaults
CLAW_BUFFER_DAYS=5                 # Default buffer days
CLAW_DEFAULT_CHANNEL=instagram     # Default target channel

# External services
CLAW_GDRIVE_ENABLED=true           # Enable Google Drive sync
BUFFER_API_KEY=your-buffer-token   # Required for scheduling
```

---

## 🎨 AI Enhancement Tools

OpenClaw includes 12 standalone AI enhancement tools that can be used independently:

| Tool | Input | What it does | Min VRAM |
|------|-------|--------------|----------|
| **clawaes** | images | Score and pick the best photos | ~1 GB |
| **clawdepth** | images | Synthetic bokeh / portrait mode | ~1.5 GB |
| **clawbg** | images | Remove background, replace with colour/image | ~0.5 GB |
| **clawvlm** | images | Auto-describe and suggest captions | ~4 GB |
| **clawrife** | videos | Frame interpolation (60fps / slow motion) | ~2 GB |
| **clawmatte** | videos | Remove video background, composite backdrop | ~3 GB |
| **clawsep** | video/audio | Separate vocals from music | ~2 GB |
| **clawbeat** | prompt / video | Generate brand background music | ~3 GB |
| **clawanimate** | images | Image → animated video clip | ~8 GB |
| **clawvace** | video | Edit / inpaint video regions via prompt | ~8 GB |
| **clawportrait** | portrait + driver video | Animate a face from a driving video | ~4 GB |

**Usage:** Drop files into `./input`, get results in `./output`. Each tool follows the same conventions (`uv sync`, `--input`, `--output`, `--device cpu` fallback).

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [🏷️ SOUL.md](./SOUL.md) | Agent identity, persona, and behavior specs |
| [📖 WORKFLOW.md](./WORKFLOW.md) | Complete processing workflow and best practices |
| [🔧 Skills](./skills/) | Individual skill documentation and configuration |
| [🎨 AI Enhancements](./AI_ENHANCEMENTS.md) | Detailed AI tool documentation (notes) |

---

## 🚀 Getting Help

### CLI Commands

```bash
# Get help for any command
claw --help
claw init --help
claw process --help
claw schedule --help
```

### Common Issues

| Issue | Resolution |
|-------|------------|
| No BRAND.md | Auto-trigger Init phase |
| Unclear input | Request clarification via chat |
| Media generation fail | Fall back to templates |
| Scheduling fail | Queue to manual review |
| Channel not supported | Suggest alternative channels |

---

## 📄 License

MIT

---