# OpenClaw - Personal Brand Agent

A personal brand content agent that transforms raw inputs into polished, multi-channel social media content with automated image/video processing and scheduling.

## Setup

### Prerequisites
- Node.js or Python runtime
- Git (for submodules)

### Initialize Submodules
```bash
git submodule add https://github.com/FilippTrigub/clawvig skills/video-processing
git submodule add https://github.com/FilippTrigub/clawimig skills/image-processing
```

### Initialize Brand
```bash
claw init --input ./input/
```

## Usage

### Process Content
```bash
claw process --input ./input/article.md --channel instagram
```

### Schedule Buffer
```bash
claw schedule --buffer-days 5
```

## Documentation

- [SOUL.md](./SOUL.md) - Agent identity and behavior
- [WORKFLOW.md](./WORKFLOW.md) - Complete workflow guide
- [Skills](./skills/) - Individual skill documentation

## Directory Structure

```
claw-parade/
├── SOUL.md           # Agent identity
├── BRAND.md          # Brand spec (generated)
├── WORKFLOW.md       # Workflow guide
├── skills/           # Skill definitions
│   ├── brand-awareness/
│   ├── video-processing/  # submodule
│   └── image-processing/  # submodule
├── input/            # Raw input files
└── output/           # Processed outputs
```

## License

[Your License Here]
