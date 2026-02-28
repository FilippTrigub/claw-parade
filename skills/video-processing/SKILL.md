# Video Processing Skill

**Description**: Processes and generates video content optimized for social media platforms using the clawvig library.

**Category**: Media Processing

**Trigger**: When video output is needed for content creation

**Submodule**: https://github.com/FilippTrigub/clawvig

---

## Tools

### 1. process-video

**Purpose**: Process existing video files for social media (resize, crop, add branding, optimize)

**Input**:
- Video file path or URL
- Target platform (instagram, tiktok, linkedin, etc.)
- Brand specs from BRAND.md

**Output**:
- Optimized video file ready for posting
- Thumbnail extraction

**Usage**:
```
Input: ./input/meeting.mp4
Config: platform=instagram, brand_align=true
Output: ./output/instagram/video_reel.mp4
```

---

### 2. generate-video

**Purpose**: Generate video content from text/image inputs using AI generation

**Input**:
- Text script or description
- Source images (optional)
- Brand visual specs
- Platform requirements

**Output**:
- Generated video file
- Accompanying assets

**Usage**:
```
Input: "Explain AI agents in 30 seconds"
Config: platform=instagram, duration=30s
Output: ./output/instagram/generated_explainer.mp4
```

---

## Integration

- Receives brand specs from `brand-awareness` skill
- Outputs to `/output/[channel]/` directory
- Integrated with scheduling buffer
