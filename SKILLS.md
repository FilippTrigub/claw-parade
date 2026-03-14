# Skills Reference

Comprehensive documentation for all Abra skills. Each skill operates independently: drop files into `./input`, get results in `./output`. Combine as needed.

All skills follow the same conventions:
- Python deps managed with `uv` (`uv sync` + `uv run`)
- Scripts live in `$SKILL_DIR/scripts/`
- Input dir: `./input` (or override with `--input`)
- Output dir: `./output` (or override with `--output`)

---

## GPU / CPU Compatibility

The OpenClaw agent runs an LLM on the GPU, leaving some VRAM free. These tools run in a **separate process** and share that VRAM. Each extra CUDA context costs ~200–400 MB overhead.

Practical constraint: if the LLM occupies N GB, only `total - N - 0.4` GB is available. Tools needing more will crash with OOM unless `--device cpu` is passed.

Every tool accepts `--device cpu` to fall back to CPU/RAM:

| Skill | Min VRAM (GPU) | CPU fallback? | CPU speed |
|-------|---------------|---------------|-----------|
| grade | ~1 GB | ✅ yes | fast (~2s/image) |
| portrait | ~1.5 GB | ✅ yes | acceptable (~5s/image) |
| knockout | ~0.5 GB | ✅ yes | acceptable (~3s/image) |
| alt | ~4 GB | ✅ yes (moondream2 only) | slow (~7s/image) |
| tween | ~2 GB | ⚠️ technically yes | very slow, impractical for video |
| keyer | ~3 GB | ❌ no practical path | too slow |
| demix | ~2 GB | ✅ yes | slow but usable (~3–5× realtime) |
| score | ~3 GB | ✅ yes | very slow (~10× realtime) |
| liven | ~8 GB | ❌ no | hours per clip |
| cutlab | ~8 GB | ❌ no | hours per clip |

**Recommendation:** When VRAM is limited, prefer tools marked ✅. Generative tools (`liven`, `cutlab`) are best run when LLM is idle.

---

## Core Skills

---

### persona — Brand Identity Management

**What it does:** Maintains and applies brand identity across all content operations. Ensures every output aligns with the personal brand's voice, values, and visual identity.

**Features:**
- Brand asset storage (logos, fonts, templates)
- Voice and tone guidelines
- Visual identity specifications
- Content adaptation to brand standards

**Usage:**
```bash
# Store a brand image
python skills/persona/scripts/brand_assets.py store-image \
  --input ./logo.png --name main-logo --tags logo,primary

# List all assets
python skills/persona/scripts/brand_assets.py list
```

---

### verbatim — Audio Transcription

**What it does:** Transcribes audio from video or audio files using HuggingFace ASR models. Outputs per-segment JSON with timestamps and text.

**Model:** transformers or nemo library

**Requires:** `uv`, GPU (~realtime) or CPU (~1–2× realtime)

**Usage:**
```bash
cd skills/verbatim && uv sync
uv run python scripts/transcribe.py --input ./input --output ./output
```

---

### snip — Video Cutting

**What it does:** Cuts videos into segments, rearranges them, and produces an output video with a specific cuts-per-second rate. Uses MoviePy. Prioritizes audio transcription for timestamped cutting, falls back to adaptive scene detection.

**Requires:** `uv`, GPU recommended

**Usage:**
```bash
cd skills/snip && uv sync
uv run python scripts/cut.py --input ./input --output ./output --segments 3
```

---

### render — Text to Image

**What it does:** Generates images from text prompts using HuggingFace diffusers. Supports multiple model architectures including FLUX, SDXL, SD3, and Playground v2.

**Requires:** `uv`, CUDA GPU

**Usage:**
```bash
cd skills/render && uv sync
uv run python scripts/generate.py --prompt "professional headshot" --output ./output
```

---

### liven — Image to Video

**What it does:** Animates a still image into a short video clip (5–10s) using LTX-Video (image-to-video diffusion). Guided by a text prompt describing desired motion.

**Models:**
- Wan2.1-I2V-1.3B — 8GB VRAM, 480p, fast
- LTX-Video 13B — higher quality, faster-than-realtime on 4090

**Requires:** `uv`, GPU required (8GB+ VRAM)

**Usage:**
```bash
cd skills/liven && uv sync
uv run python scripts/img2vid.py --input ./input --output ./output \
  --prompt "slow camera push-in, soft bokeh"
```

---

### keyer — Video Matting

**What it does:** Removes the background from every frame of a video using AI (BiRefNet-general via rembg). Outputs transparent-background video or composites onto a solid colour or image.

**Model:** BiRefNet-general

**Requires:** `uv`, NVIDIA GPU (3GB+ VRAM)

**Usage:**
```bash
cd skills/keyer && uv sync
uv run python scripts/matte.py --input ./input --output ./output --bg "#0d0d0d"
```

---

### tween — Frame Interpolation

**What it does:** Doubles or quadruples the frame rate of any video using neural optical flow. Produces smooth slow motion without a high-speed camera.

**Model:** Practical-RIFE — pure PyTorch, GPU

**Requires:** `uv`, GPU required

**Usage:**
```bash
cd skills/tween && uv sync
uv run python scripts/interpolate.py --input ./input --output ./output --multiplier 2
```

---

### score — Music Generation

**What it does:** Generates royalty-free background music from a text prompt. Optionally mixes the result under a video at target loudness so speech stays primary.

**Model:** MusicGen by Meta
- musicgen-small (300M) — ~6GB VRAM, fast
- musicgen-melody (1.5B) — higher quality, melody conditioning

**Requires:** `uv`, GPU recommended (16GB for medium model)

**Usage:**
```bash
cd skills/score && uv sync
uv run python scripts/generate_music.py --prompt "warm acoustic guitar" \
  --duration 30 --output ./output/music.wav
```

---

### demix — Audio Separation

**What it does:** Separates vocals from background music in any video or audio file. Useful for getting clean voice tracks or stripping music before adding brand music.

**Model:** Demucs by Meta — GPU-accelerated

**Requires:** `uv`, GPU recommended

**Usage:**
```bash
cd skills/demix && uv sync
uv run python scripts/separate.py --input ./input --output ./output --stem vocals
```

---

### alt — Auto-Caption

**What it does:** Runs a local vision-language model over each image and writes a JSON sidecar with a description, suggested Instagram caption, and detected tags.

**Models:**
- moondream2 — 2B params, fast, runs on CPU
- Phi-4-multimodal — 3.8B, higher quality

**Requires:** `uv`, GPU recommended

**Usage:**
```bash
cd skills/alt && uv sync
uv run python scripts/describe.py --input ./input --output ./output
```

Output:
```json
{
  "description": "A woman in a café holding a coffee cup.",
  "caption": "Morning rituals ☕ #coffeetime",
  "tags": ["portrait", "coffee", "indoor"]
}
```

---

### knockout — Background Removal

**What it does:** Removes backgrounds from portraits or product shots. Outputs transparent PNGs or composites onto a solid colour or gradient.

**Model:** rembg with IS-Net / U2Net via ONNX Runtime

**Requires:** `uv`, GPU recommended

**Usage:**
```bash
cd skills/knockout && uv sync
uv run python scripts/rembg_batch.py --input ./input --output ./output
```

---

### portrait — Depth Bokeh

**What it does:** Estimates per-pixel depth from a single photo using MiDaS, then applies lens blur weighted by depth. Makes phone photos look like shot with a fast prime lens.

**Model:** MiDaS DPT-Large

**Requires:** `uv`, GPU recommended

**Usage:**
```bash
cd skills/portrait && uv sync
uv run python scripts/bokeh.py --input ./input --output ./output
```

---

### grade — Aesthetic Selection

**What it does:** Scores a folder of images by visual quality and copies the top K to output. Eliminates manual photo culling.

**Models:**
- improved-aesthetic-predictor — CLIP + MLP, ~1s/image on GPU
- PickScore — ranks images against a text prompt

**Requires:** `uv`, GPU recommended

**Usage:**
```bash
cd skills/grade && uv sync
uv run python scripts/score.py --input ./input --output ./output --top 3
```

---

### mux — Video Processing

**What it does:** Instagram video enhancement and captioning pipeline. Includes sharpening, colour grading, warmth adjustments, audio normalisation, or burning animated captions.

**Requires:** `uv`, GPU recommended

**Usage:**
```bash
cd skills/mux && uv sync
uv run python scripts/caption_service.py --output output --preset cinematic
```

---

### filter — Image Processing

**What it does:** Processes a directory of images for Instagram using sharp (resize/crop/pad) and pilgram (Instagram filters). Reads a `config.json` and writes processed images to an output directory.

**Requires:** `uv`

**Usage:**
```bash
cd skills/filter && uv sync
uv run python scripts/process.py --config config.json
```

---

### buffer — Content Scheduling

**What it does:** Schedules, creates, and manages social media posts on Instagram and LinkedIn using the Buffer GraphQL API.

**Requires:** `uv`, Buffer API key

**Usage:**
```bash
cd skills/buffer && uv sync
uv run python scripts/posts.py create \
  --channel-id CHANNEL_ID \
  --text "Post caption" \
  --mode addToQueue
```

---

### canva — Design Integration

**What it does:** MCP skill for Canva. Provides 23 tools for uploading assets, searching designs, creating designs, and managing exports.

**Requires:** Canva API credentials

**Usage:** Use via OpenClaw tool calls for design automation.

---

## Quick Reference

| Skill | Input | What it does | Min VRAM | CPU ok? |
|-------|-------|-------------|----------|---------|
| grade | images | Score and pick the best photos | ~1 GB | ✅ fast |
| portrait | images | Synthetic bokeh / portrait mode | ~1.5 GB | ✅ acceptable |
| knockout | images | Remove background | ~0.5 GB | ✅ acceptable |
| alt | images | Auto-describe and caption | ~4 GB | ✅ slow |
| tween | videos | Frame interpolation | ~2 GB | ⚠️ impractical |
| keyer | videos | Remove video background | ~3 GB | ❌ no |
| demix | video/audio | Separate vocals from music | ~2 GB | ✅ slow |
| score | prompt/video | Generate music | ~3 GB | ✅ very slow |
| liven | images | Image → video clip | ~8 GB | ❌ no |
| cutlab | video | Edit/inpaint video | ~8 GB | ❌ no |

Core: persona, verbatim, snip, render, mux, filter, buffer, canva
