# Image Processing Skill

**Description**: Processes and generates image content optimized for social media platforms.

**Category**: Media Processing

**Trigger**: When image output is needed for content creation

**Submodule**: https://github.com/FilippTrigub/clawimig

---

## Tools

### 1. process-image

**Purpose**: Process existing images for social media (resize, crop, enhance, add branding)

**Input**:
- Image file path or URL
- Target platform (instagram, linkedin, twitter, etc.)
- Brand specs from BRAND.md

**Output**:
- Optimized image file ready for posting
- Variants for different aspect ratios

**Usage**:
```
Input: ./input/photo.jpg
Config: platform=instagram, add_branding=true
Output: ./output/instagram/photo_processed.jpg
```

---

### 2. generate-image

**Purpose**: Generate images from text prompts using AI image generation

**Input**:
- Text prompt or description
- Brand visual specs
- Platform requirements

**Output**:
- Generated image file
- Variants if applicable

**Usage**:
```
Input: "Modern tech minimalist workspace"
Config: platform=instagram, style=minimalist
Output: ./output/instagram/generated_workspace.jpg
```

---

## Integration

- Receives brand specs from `brand-awareness` skill
- Outputs to `/output/[channel]/` directory
- Integrated with scheduling buffer
