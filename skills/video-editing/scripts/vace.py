#!/usr/bin/env python3
"""
vace.py — clawvace: edit video regions via text prompt using Wan2.1-VACE.

Runs Wan2.1-VACE-1.3B locally. Supports two masking modes:
  background   — auto-segment background via rembg and inpaint it
  region       — mask a rectangular region (fractions: x1,y1,x2,y2)

Model weights are downloaded once to ~/.cache/huggingface.

Requires a CUDA GPU with at least 8 GB free VRAM. Blocks with a clear error
if VRAM is insufficient.

Usage:
  python scripts/vace.py [--config config.json]
  python scripts/vace.py --input ./input/video.mp4 --output ./output \
      --mask background --prompt "modern office with floor-to-ceiling windows"
  python scripts/vace.py --input ./input/video.mp4 --output ./output \
      --mask-region "0.0,0.0,1.0,0.3" --prompt "clear blue sky"
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}
MIN_VRAM_GB = 8.0
DEFAULT_MODEL = "Wan-AI/Wan2.1-VACE-1.3B-diffusers"


# ---------------------------------------------------------------------------
# GPU check
# ---------------------------------------------------------------------------

def check_gpu(required_gb: float = MIN_VRAM_GB) -> None:
    import torch
    if not torch.cuda.is_available():
        print("Error: clawvace requires a CUDA-capable GPU.", file=sys.stderr)
        print(f"  Required VRAM: {required_gb:.1f} GB", file=sys.stderr)
        print("  No CUDA device detected.", file=sys.stderr)
        sys.exit(1)
    free, total = torch.cuda.mem_get_info()
    free_gb = free / 1024 ** 3
    total_gb = total / 1024 ** 3
    if free_gb < required_gb:
        used_gb = total_gb - free_gb
        print("Error: insufficient GPU VRAM for clawvace.", file=sys.stderr)
        print(f"  Required:  {required_gb:.1f} GB", file=sys.stderr)
        print(f"  Available: {free_gb:.1f} GB  "
              f"({used_gb:.1f} GB in use, {total_gb:.1f} GB total)", file=sys.stderr)
        print("  Tip: pause other GPU workloads (e.g. the LLM context) to free VRAM.",
              file=sys.stderr)
        sys.exit(1)
    print(f"GPU: {torch.cuda.get_device_name()} — "
          f"{free_gb:.1f} GB free / {total_gb:.1f} GB total")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(path: Path) -> dict:
    if not path.exists():
        print(f"Error: config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open() as f:
        return json.load(f)


def validate_config(cfg: dict) -> dict:
    errors = []
    if not cfg.get("prompt"):
        errors.append("'prompt' is required")
    mask = cfg.get("mask", "background")
    if mask not in {"background", "region"}:
        errors.append("'mask' must be 'background' or 'region'")
    if mask == "region" and not cfg.get("mask_region"):
        errors.append("'mask_region' is required when mask='region' (format: 'x1,y1,x2,y2')")
    strength = cfg.get("strength", 0.85)
    if not isinstance(strength, (int, float)) or not (0 < strength <= 1):
        errors.append("'strength' must be a float in (0, 1]")
    if errors:
        print("Config errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    return cfg


# ---------------------------------------------------------------------------
# Mask generation
# ---------------------------------------------------------------------------

def make_background_mask(frame: Image.Image) -> Image.Image:
    """Use rembg to get a foreground alpha, then invert to get background mask."""
    from rembg import remove
    rgba = remove(frame.convert("RGBA"))
    alpha = rgba.split()[3]
    # Invert: foreground (alpha=255) → 0 (keep), background (alpha=0) → 255 (edit)
    mask_array = 255 - np.array(alpha)
    return Image.fromarray(mask_array, mode="L")


def make_region_mask(frame: Image.Image, region_str: str) -> Image.Image:
    """Create a rectangular mask from 'x1,y1,x2,y2' fractions."""
    w, h = frame.size
    try:
        x1, y1, x2, y2 = [float(v) for v in region_str.split(",")]
    except ValueError:
        raise ValueError(f"Invalid mask_region '{region_str}'. Expected 'x1,y1,x2,y2' fractions.")
    mask = Image.new("L", (w, h), 0)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    draw.rectangle(
        [int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)],
        fill=255,
    )
    return mask


# ---------------------------------------------------------------------------
# Video I/O helpers
# ---------------------------------------------------------------------------

def extract_frames(video_path: Path, frames_dir: Path) -> float:
    """Extract frames to PNG files. Returns fps."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True,
    )
    fps_str = probe.stdout.strip()
    try:
        num, den = fps_str.split("/")
        fps = float(num) / float(den)
    except Exception:
        fps = 30.0

    cmd = ["ffmpeg", "-y", "-i", str(video_path),
           str(frames_dir / "%06d.png"), "-hide_banner", "-loglevel", "error"]
    subprocess.run(cmd, check=True)
    return fps


def assemble_video(frames_dir: Path, fps: float, audio_source: Path, output_path: Path) -> None:
    tmp_video = frames_dir.parent / "assembled.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "%06d.png"),
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
        str(tmp_video), "-hide_banner", "-loglevel", "error",
    ]
    subprocess.run(cmd, check=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(tmp_video),
        "-i", str(audio_source),
        "-c:v", "copy", "-c:a", "aac",
        "-map", "0:v:0", "-map", "1:a:0?",
        "-shortest", str(output_path),
        "-hide_banner", "-loglevel", "error",
    ]
    subprocess.run(cmd, check=True)


# ---------------------------------------------------------------------------
# VACE pipeline
# ---------------------------------------------------------------------------

def load_pipeline(model_id: str):
    import torch
    from diffusers import AutoPipelineForInpainting

    print(f"Loading VACE pipeline from '{model_id}'…")
    print("  (First run downloads model weights — this may take several minutes.)")
    pipe = AutoPipelineForInpainting.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
    )
    pipe.to("cuda")
    pipe.enable_model_cpu_offload()
    return pipe


def edit_frame(
    pipe,
    frame: Image.Image,
    mask: Image.Image,
    prompt: str,
    negative_prompt: str,
    strength: float,
    num_inference_steps: int,
    guidance_scale: float,
) -> Image.Image:
    import torch
    result = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        image=frame,
        mask_image=mask,
        strength=strength,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        generator=torch.Generator("cuda"),
    )
    return result.images[0]


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_video(
    input_path: Path,
    output_path: Path,
    cfg: dict,
    pipe,
) -> None:
    mask_mode = cfg.get("mask", "background")
    mask_region = cfg.get("mask_region")
    prompt = cfg["prompt"]
    negative_prompt = cfg.get("negative_prompt", "worst quality, blurry, distorted")
    strength = float(cfg.get("strength", 0.85))
    num_inference_steps = cfg.get("num_inference_steps", 30)
    guidance_scale = float(cfg.get("guidance_scale", 5.0))

    with tempfile.TemporaryDirectory(prefix="clawvace_") as tmp_str:
        tmp = Path(tmp_str)
        frames_in = tmp / "frames_in"
        frames_out = tmp / "frames_out"
        frames_in.mkdir()
        frames_out.mkdir()

        fps = extract_frames(input_path, frames_in)
        frame_paths = sorted(frames_in.glob("*.png"))
        print(f"  {len(frame_paths)} frames @ {fps:.2f} fps")

        # Compute mask from first frame (reused for all frames)
        first_frame = Image.open(frame_paths[0]).convert("RGB")
        if mask_mode == "background":
            print("  Computing background mask via rembg…")
            mask = make_background_mask(first_frame)
        else:
            mask = make_region_mask(first_frame, mask_region)

        print(f"  Editing frames [prompt: {prompt[:60]}…]")
        for i, fp in enumerate(frame_paths):
            frame = Image.open(fp).convert("RGB")
            edited = edit_frame(
                pipe, frame, mask, prompt, negative_prompt,
                strength, num_inference_steps, guidance_scale,
            )
            edited.save(frames_out / fp.name)
            if (i + 1) % 10 == 0:
                print(f"    {i + 1}/{len(frame_paths)} frames done…")

        assemble_video(frames_out, fps, input_path, output_path)


def process(config_path: Path) -> None:
    cfg = validate_config(load_config(config_path))
    check_gpu()

    input_dir = Path(cfg.get("input_dir", "./input"))
    output_dir = Path(cfg.get("output_dir", "./output"))
    model_id = cfg.get("model", DEFAULT_MODEL)

    if not input_dir.exists():
        print(f"Error: input_dir does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)

    videos = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not videos:
        print(f"No video files found in {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    pipe = load_pipeline(model_id)

    print(f"Processing {len(videos)} video(s)…")
    print()

    succeeded, failed = 0, []
    for video_path in videos:
        print(f"[{video_path.name}]")
        try:
            out_path = output_dir / video_path.with_suffix(".mp4").name
            process_video(video_path, out_path, cfg, pipe)
            print(f"  → {out_path}")
            succeeded += 1
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            failed.append(video_path.name)

    print()
    print(f"Done: {succeeded}/{len(videos)} succeeded", end="")
    if failed:
        print(f", {len(failed)} failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="clawvace — video inpainting")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--input", help="Override input_dir")
    parser.add_argument("--output", help="Override output_dir")
    parser.add_argument("--prompt", help="Override prompt")
    parser.add_argument("--mask", choices=["background", "region"], help="Override mask mode")
    parser.add_argument("--mask-region", help="Override mask_region (x1,y1,x2,y2 fractions)")
    parser.add_argument("--strength", type=float, help="Override strength")
    parser.add_argument("--model", help="Override model HuggingFace ID")
    args = parser.parse_args()

    cfg = validate_config(load_config(Path(args.config)))
    if args.input:
        cfg["input_dir"] = args.input
    if args.output:
        cfg["output_dir"] = args.output
    if args.prompt:
        cfg["prompt"] = args.prompt
    if args.mask:
        cfg["mask"] = args.mask
    if args.mask_region:
        cfg["mask_region"] = args.mask_region
    if args.strength is not None:
        cfg["strength"] = args.strength
    if args.model:
        cfg["model"] = args.model

    import tempfile as _tf, json as _json
    with _tf.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        _json.dump(cfg, tmp)
        tmp_path = Path(tmp.name)
    try:
        process(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
