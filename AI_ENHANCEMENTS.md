# AI Enhancement Tools

Optional, standalone tools that plug into the content pipeline. Each operates independently: drop files into `./input`, get results in `./output`. None are required — combine as needed.

All tools follow the same conventions as the existing skills:
- Python deps managed with `uv` (`uv sync` + `uv run`)
- Scripts live in `$SKILL_DIR/scripts/`
- Input dir: `./input` (or override with `--input`)
- Output dir: `./output` (or override with `--output`)

---

## GPU / CPU Compatibility Notes

The OpenClaw agent runs an LLM on the GPU, leaving a portion of VRAM free. These tools run in a **separate process** and can freely use that remaining VRAM — CUDA does not isolate memory between processes. Each extra CUDA context costs ~200–400 MB overhead.

The practical constraint: if the LLM occupies N GB, only `total - N - 0.4` GB is available. Tools that need more than that will crash with OOM unless `--device cpu` is passed.

Every tool below accepts `--device cpu` to fall back to CPU/RAM. The table shows expected behaviour:

| Tool | Min VRAM (GPU) | CPU fallback? | CPU speed |
|------|---------------|---------------|-----------|
| `clawaes` | ~1 GB (CLIP ViT-L) | ✅ yes | fast (~2s/image) |
| `clawdepth` | ~1.5 GB (MiDaS DPT-L) | ✅ yes | acceptable (~5s/image) |
| `clawbg` | ~0.5 GB (ONNX, IS-Net) | ✅ yes | acceptable (~3s/image) |
| `clawvlm` | ~4 GB (moondream2) | ✅ yes (moondream2 only) | slow (~7s/image) |
| `clawrife` | ~2 GB | ⚠️ technically yes | very slow, impractical for video |
| `clawmatte` | ~3 GB (SD res) | ❌ no practical path | too slow |
| `clawsep` | ~2 GB (Demucs) | ✅ yes | slow but usable (~3–5× realtime) |
| `clawbeat` | ~3 GB (musicgen-small) | ✅ yes | very slow (~10× realtime) |
| `clawanimate` | ~8 GB (Wan2.1-1.3B) | ❌ no | hours per clip |
| `clawvace` | ~8 GB (VACE-1.3B) | ❌ no | hours per clip |
| `clawportrait` | ~4 GB (LivePortrait) | ⚠️ technically yes | very slow |

**Recommendation:** when the LLM is loaded and VRAM headroom is limited, prefer the tools marked ✅. The generative tools (`clawanimate`, `clawvace`) are best run when the LLM context is idle or offloaded.

---

## Image Tools

---

### clawaes — Aesthetic Auto-Selection

**What it does:** Scores a folder of images by visual quality and copies the top K to output. Eliminates manual photo culling.

**Models:**
- [`improved-aesthetic-predictor`](https://github.com/christophschuhmann/improved-aesthetic-predictor) — CLIP + MLP, ~1s/image on GPU
- [`PickScore`](https://huggingface.co/yuvalkirstain/PickScore_v1) — ranks images against a text prompt

**Requires:** `uv`, GPU recommended (CPU works, slower)

**Setup:**
```bash
cd "$SKILL_DIR/scripts" && uv sync
```

**Usage:**
```bash
# Pick top 3 images by aesthetic score
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/score.py" \
  --input ./input --output ./output --top 3

# Pick top 5 images most matching a prompt
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/score.py" \
  --input ./input --output ./output --top 5 \
  --prompt "warm, natural light, outdoor portrait"

# Force CPU (LLM is using the GPU)
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/score.py" \
  --input ./input --output ./output --top 3 --device cpu
```

**Output:** Selected images copied to `./output/`, ranked `01_filename.jpg`, `02_filename.jpg`, …

**Status:** [x] Built — skills/aesthetic-selection/

---

### clawdepth — Synthetic Bokeh (Portrait Mode)

**What it does:** Estimates per-pixel depth from a single photo using MiDaS, then applies lens blur weighted by depth. Makes phone photos look like they were shot with a fast prime lens.

**Model:** [`MiDaS DPT-Large`](https://pytorch.org/hub/intelisl_midas_v2/) via `torch.hub`

**Requires:** `uv`, GPU recommended

**Setup:**
```bash
cd "$SKILL_DIR/scripts" && uv sync
```

**Usage:**
```bash
# Default blur strength
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/bokeh.py" \
  --input ./input --output ./output

# Stronger blur
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/bokeh.py" \
  --input ./input --output ./output --blur-strength 25

# Force CPU (LLM is using the GPU)
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/bokeh.py" \
  --input ./input --output ./output --device cpu
```

**Output:** Processed images in `./output/`, same filenames as input.

**Status:** [x] Built — skills/depth-bokeh/

---

### clawbg — Background Removal (Images)

**What it does:** Removes the background from portraits or product shots. Outputs transparent PNGs or composites onto a solid colour or gradient.

**Model:** [`rembg`](https://github.com/danielgatis/rembg) with `rembg[gpu]` — IS-Net / U2Net via ONNX Runtime

**Requires:** `uv`, GPU recommended (`rembg[gpu]`)

**Setup:**
```bash
cd "$SKILL_DIR/scripts" && uv sync
```

**Usage:**
```bash
# Transparent PNG output
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/rembg_batch.py" \
  --input ./input --output ./output

# Replace background with a solid colour
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/rembg_batch.py" \
  --input ./input --output ./output --bg "#1a1a2e"

# Replace background with an image
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/rembg_batch.py" \
  --input ./input --output ./output --bg ./brand-backdrop.jpg

# Force CPU — rembg[cpu] uses ONNX CPU provider, acceptable speed
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/rembg_batch.py" \
  --input ./input --output ./output --device cpu
```

**Output:** Processed images in `./output/` as PNG.

**Status:** [x] Built — skills/bg-removal/

---

### clawvlm — Auto-Caption via Vision Model

**What it does:** Runs a small vision-language model over each image and writes a JSON sidecar with a description, suggested Instagram caption, and detected tags. Useful as input to other tools or for manual review.

**Models:**
- [`moondream2`](https://huggingface.co/vikhyatk/moondream2) — 2B params, fast, runs on CPU
- [`Phi-4-multimodal`](https://huggingface.co/microsoft/Phi-4-multimodal-instruct) — 3.8B, higher quality

**Requires:** `uv`, GPU recommended

**Setup:**
```bash
cd "$SKILL_DIR/scripts" && uv sync
```

**Usage:**
```bash
# Default model (moondream2)
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/describe.py" \
  --input ./input --output ./output

# Higher-quality model (needs ~8GB free VRAM)
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/describe.py" \
  --input ./input --output ./output --model phi4

# Force CPU — moondream2 only, ~7s/image on a modern desktop CPU
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/describe.py" \
  --input ./input --output ./output --device cpu
```
Note: `--device cpu` is only supported with `moondream2`. Phi-4 requires GPU.

**Output:** For each `photo.jpg` → `photo.json` in `./output/`:
```json
{
  "description": "A woman in a café holding a coffee cup, warm morning light.",
  "caption": "Morning rituals ☕ #coffeetime #morningvibes",
  "tags": ["portrait", "coffee", "indoor", "warm light"]
}
```

**Status:** [x] Built — skills/vision-caption/

---

## Video Tools

---

### clawrife — Frame Interpolation (Slow Motion / 60fps)

**What it does:** Doubles or quadruples the frame rate of any video using neural optical flow. Produces smooth slow motion without a high-speed camera.

**Model:** [`Practical-RIFE`](https://github.com/hzwer/Practical-RIFE) — pure PyTorch, GPU

**Requires:** `uv`, GPU required

**Setup:**
```bash
cd "$SKILL_DIR/scripts" && uv sync
```

**Usage:**
```bash
# 2× frame rate (30fps → 60fps)
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/interpolate.py" \
  --input ./input --output ./output --multiplier 2

# 4× frame rate (slow motion)
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/interpolate.py" \
  --input ./input --output ./output --multiplier 4
```
Note: GPU required for practical use. CPU fallback exists but is impractical for video (many minutes per second of output).

**Output:** Interpolated videos in `./output/`, same filenames as input.

**Status:** [x] Built — skills/frame-interpolation/

---

### clawmatte — Video Background Removal

**What it does:** Removes the background from talking-head or product videos without a green screen. Composites onto a solid colour, image, or video backdrop.

**Model:** [`BackgroundMattingV2`](https://github.com/PeterL1n/BackgroundMattingV2) — 4K@30fps on an RTX 2080 Ti

**Requires:** `uv`, NVIDIA GPU required

**Setup:**
```bash
cd "$SKILL_DIR/scripts" && uv sync
```

**Usage:**
```bash
# Composite onto a solid colour
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/matte.py" \
  --input ./input --output ./output --bg "#0d0d0d"

# Composite onto a background image
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/matte.py" \
  --input ./input --output ./output --bg ./brand-backdrop.jpg

# Composite onto a background video (loops if shorter)
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/matte.py" \
  --input ./input --output ./output --bg ./looping-bg.mp4
```

**Output:** Composited videos in `./output/`, same filenames as input.

**Status:** [x] Built — skills/video-matting/

---

### clawsep — Audio Source Separation

**What it does:** Separates vocals from background music in any video or audio file. Use to get a clean voice track before normalization, or to strip music before adding brand music.

**Model:** [`Demucs`](https://github.com/facebookresearch/demucs) by Meta — GPU-accelerated

**Requires:** `uv`, GPU recommended

**Setup:**
```bash
cd "$SKILL_DIR/scripts" && uv sync
```

**Usage:**
```bash
# Extract vocals only (replaces audio track in output video)
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/separate.py" \
  --input ./input --output ./output --stem vocals

# Extract instrumental (for remixing)
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/separate.py" \
  --input ./input --output ./output --stem no_vocals

# Force CPU — slower (~3–5× realtime) but fully functional
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/separate.py" \
  --input ./input --output ./output --stem vocals --device cpu
```

**Output:** Videos in `./output/` with replaced audio track. Raw stems also saved as `.wav` alongside.

**Status:** [x] Built — skills/audio-separation/

---

### clawbeat — Brand Music Generation

**What it does:** Generates royalty-free background music from a text prompt. Auto-mixes it under a video's voice track at −20 LUFS so speech stays primary.

**Model:** [`MusicGen`](https://github.com/facebookresearch/audiocraft/blob/main/docs/MUSICGEN.md) by Meta
- `musicgen-small` (300M) — ~6GB VRAM, fast
- `musicgen-melody` (1.5B) — higher quality, melody conditioning

**Requires:** `uv`, GPU recommended (16GB for medium model)

**Setup:**
```bash
cd "$SKILL_DIR/scripts" && uv sync
```

**Usage:**
```bash
# Generate and save as audio file
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/generate_music.py" \
  --prompt "warm upbeat acoustic guitar coffee shop" \
  --duration 30 \
  --output ./output/music.wav

# Generate and mix under a video
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/generate_music.py" \
  --prompt "warm upbeat acoustic guitar coffee shop" \
  --video ./input/video.mp4 \
  --output ./output/video_with_music.mp4

# Use melody model with a reference audio hint
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/generate_music.py" \
  --prompt "lo-fi chill beats" --melody ./input/reference.mp3 \
  --output ./output/music.wav

# Force CPU — works, but very slow (~10× realtime); use musicgen-small only
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/generate_music.py" \
  --prompt "acoustic guitar" --duration 15 --output ./output/music.wav \
  --model small --device cpu
```

**Output:** `.wav` audio file or `.mp4` video with music mixed in.

**Status:** [x] Built — skills/music-gen/

---

## Generative Tools

---

### clawanimate — Image to Video

**What it does:** Takes a single still image and generates a short animated video clip (5–10s) from it.

**Models (choose one):**
- [`Wan2.1-I2V-1.3B`](https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B-Diffusers) — 8GB VRAM, 480p, fast
- [`LTX-Video 13B`](https://github.com/Lightricks/LTX-Video) — faster-than-realtime at 30fps on a 4090, higher quality

**Requires:** `uv`, GPU required (8GB+ VRAM)

**Setup:**
```bash
cd "$SKILL_DIR/scripts" && uv sync
```

**Usage:**
```bash
# Animate with a motion prompt (Wan2.1 1.3B, default)
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/img2vid.py" \
  --input ./input --output ./output \
  --prompt "slow camera push-in, soft bokeh, gentle movement"

# Use LTX for higher quality
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/img2vid.py" \
  --input ./input --output ./output \
  --model ltx \
  --prompt "cinematic dolly zoom, golden hour light"

# Control clip length and resolution
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/img2vid.py" \
  --input ./input --output ./output \
  --frames 81 --width 848 --height 480
```

**Output:** Generated `.mp4` clips in `./output/`, one per input image.

**Status:** [x] Built — skills/image-to-video/

---

### clawvace — Video Editing via Inpainting

**What it does:** Edits video regions using a text prompt. Replace backgrounds, remove objects, change scenes — without a green screen. Based on Wan2.1-VACE (ICCV 2025).

**Model:** [`VACE-Wan2.1-1.3B`](https://huggingface.co/ali-vilab/VACE-Wan2.1-1.3B-Preview) — 8GB VRAM, 480p

**Requires:** `uv`, GPU required (8GB+ VRAM)

**Setup:**
```bash
cd "$SKILL_DIR/scripts" && uv sync
```

**Usage:**
```bash
# Replace background (auto-mask via segmentation)
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/vace.py" \
  --input ./input/video.mp4 --output ./output \
  --mask background \
  --prompt "modern minimalist office with floor-to-ceiling windows"

# Replace a rectangular region (x1,y1,x2,y2 as fractions 0–1)
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/vace.py" \
  --input ./input/video.mp4 --output ./output \
  --mask-region "0.0,0.0,1.0,0.4" \
  --prompt "clear blue sky with soft clouds"

# Video-to-video style transfer
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/vace.py" \
  --input ./input/video.mp4 --output ./output \
  --prompt "anime style, vibrant colors" --strength 0.6
```

**Output:** Edited `.mp4` in `./output/`.

**Status:** [x] Built — skills/video-editing/

---

### clawportrait — Talking Head Animation (LivePortrait)

**What it does:** Animates any portrait photo using a driving video. The face in the photo mimics the expressions and head motion from the driver. Used at production scale by Kuaishou/Douyin.

**Model:** [`LivePortrait`](https://github.com/KlingTeam/LivePortrait) — single consumer GPU

**Requires:** `uv`, GPU required

**Setup:**
```bash
cd "$SKILL_DIR/scripts" && uv sync
```

**Usage:**
```bash
# Animate a portrait using a driving video
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/portrait.py" \
  --portrait ./input/headshot.jpg \
  --driver ./input/driver.mp4 \
  --output ./output/animated.mp4

# Batch: animate one portrait against multiple drivers
uv run --project "$SKILL_DIR/scripts" python "$SKILL_DIR/scripts/portrait.py" \
  --portrait ./input/headshot.jpg \
  --driver ./input/drivers/ \
  --output ./output/
```

**Output:** Animated `.mp4` in `./output/`.

**Status:** [x] Built — skills/portrait-animation/

---

## Quick Reference

| Tool | Input | What it does | Min VRAM | CPU ok? |
|------|-------|-------------|----------|---------|
| `clawaes` | images | Score and pick the best photos | ~1 GB | ✅ fast |
| `clawdepth` | images | Synthetic bokeh / portrait mode | ~1.5 GB | ✅ acceptable |
| `clawbg` | images | Remove background, replace with colour/image | ~0.5 GB | ✅ acceptable |
| `clawvlm` | images | Auto-describe and suggest captions | ~4 GB | ✅ slow |
| `clawrife` | videos | Frame interpolation (60fps / slow motion) | ~2 GB | ⚠️ impractical |
| `clawmatte` | videos | Remove video background, composite backdrop | ~3 GB | ❌ no |
| `clawsep` | video/audio | Separate vocals from music | ~2 GB | ✅ slow |
| `clawbeat` | prompt / video | Generate brand background music | ~3 GB | ✅ very slow |
| `clawanimate` | images | Image → animated video clip | ~8 GB | ❌ no |
| `clawvace` | video | Edit / inpaint video regions via prompt | ~8 GB | ❌ no |
| `clawportrait` | portrait + driver video | Animate a face from a driving video | ~4 GB | ⚠️ impractical |

Existing tools: `clawimig` (image resize + filter) · `clawvig` (video enhance + caption) · `buffer` (schedule posts)
