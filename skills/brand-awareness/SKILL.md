# Brand Awareness Skill

**Description**: Maintains and applies brand identity across all content operations. This skill ensures every output aligns with the personal brand's voice, values, and visual identity.

**Category**: Identity & Branding

**Trigger**: Always active - applied to every content generation task

---

## Tools

### 1. read-about-me

**Purpose**: Analyzes available input about the brand and generates/updates BRAND.md with complete brand specifications.

**Input**:
- Raw text files, notes, documents about the persona/brand
- Existing BRAND.md (if present)
- Any profile information, resumes, bios, past content

**Output**:
- Generated or updated BRAND.md file
- Summary of brand characteristics extracted

**Usage**:
- Run during **Init phase** to establish brand state
- Re-run when new brand information becomes available
- Use to refresh brand understanding before major content batches

**Example Workflow**:
```
1. Provide raw input files (about.txt, resume.md, past-posts.md)
2. Skill analyzes all documents for:
   - Core values and principles
   - Voice and tone patterns
   - Areas of expertise
   - Audience and positioning
   - Visual preferences
3. Outputs structured BRAND.md
```

---

### 2. adapt-content-to-brand

**Purpose**: Takes raw content and adapts it to align with established brand identity.

**Input**:
- Draft content (social media post, article, message)
- BRAND.md specification
- Target channel/platform (Instagram, LinkedIn, Twitter, etc.)

**Output**:
- Brand-aligned content ready for publishing
- Notes on specific brand elements applied
- Suggestions for improvement

**Usage**:
- Run during **Regular phase** after initial content generation
- Specify target channel for platform-specific adaptation
- Iterate until content meets brand standards

**Example Workflow**:
```
1. Provide draft content
2. Specify target channel (e.g., "instagram")
3. Skill applies:
   - Brand voice and tone
   - Appropriate hashtags
   - Content length optimization
   - Call-to-action alignment
4. Returns polished, brand-compliant content
```

---

## Integration Points

### With Other Skills
- **Instagram Text Processing**: Receives brand-adapted content for channel formatting
- **Video Processing**: Ensures video content aligns with brand visual identity
- **Image Processing**: Applies brand colors, styles, and messaging
- **Image/Video Gen**: Generates materials using brand specifications
- **Schedule Publication**: Tags content with brand metadata for tracking

### Required Dependencies
- BRAND.md file in project root (created by `read-about-me` tool)

---

## Best Practices

1. **Always check BRAND.md first** - Ensure brand spec is current
2. **Run init phase early** - Establish brand state before regular processing
3. **Iterate on adaptation** - Use feedback loop to refine brand alignment
4. **Document variations** - Note when brand interpretation differs by channel
5. **Version BRAND.md** - Track brand evolution over time
