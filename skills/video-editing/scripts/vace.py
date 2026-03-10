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
    free_gb = free / 1024**3
    total_gb = total / 1024**3
    if free_gb < required_gb:
        used_gb = total_gb - free_gb
        print("Error: insufficient GPU VRAM for clawvace.", file=sys.stderr)
        print(f"  Required:  {required_gb:.1f} GB", file=sys.stderr)
        print(
            f"  Available: {free_gb:.1f} GB  "
            f"({used_gb:.1f} GB in use, {total_gb:.1f} GB total)",
            file=sys.stderr,
        )
        print(
            "  Tip: pause other GPU workloads (e.g. the LLM context) to free VRAM.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(
        f"GPU: {torch.cuda.get_device_name()} — "
        f"{free_gb:.1f} GB free / {total_gb:.1f} GB total"
    )


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
        errors.append(
            "'mask_region' is required when mask='region' (format: 'x1,y1,x2,y2')"
        )
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
        raise ValueError(
            f"Invalid mask_region '{region_str}'. Expected 'x1,y1,x2,y2' fractions."
        )
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
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=r_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    fps_str = probe.stdout.strip()
    try:
        num, den = fps_str.split("/")
        fps = float(num) / float(den)
    except Exception:
        fps = 30.0

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        str(frames_dir / "%06d.png"),
        "-hide_banner",
        "-loglevel",
        "error",
    ]
    subprocess.run(cmd, check=True)
    return fps


def assemble_video(
    frames_dir: Path, fps: float, audio_source: Path, output_path: Path
) -> None:
    tmp_video = frames_dir.parent / "assembled.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(frames_dir / "%06d.png"),
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        str(tmp_video),
        "-hide_banner",
        "-loglevel",
        "error",
    ]
    subprocess.run(cmd, check=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(tmp_video),
        "-i",
        str(audio_source),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0?",
        "-shortest",
        str(output_path),
        "-hide_banner",
        "-loglevel",
        "error",
    ]
    subprocess.run(cmd, check=True)


# ---------------------------------------------------------------------------
# VACE pipeline
# ---------------------------------------------------------------------------


def load_pipeline(model_id: str):
    import torch
    from diffusers import WanVACEPipeline

    print(f"Loading WanVACE pipeline from '{model_id}'…")
    print("  (First run downloads model weights — this may take several minutes.)")
    pipe = WanVACEPipeline.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
    )

    # Favor lower VRAM usage over speed.
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing("max")
    if hasattr(pipe, "enable_vae_slicing"):
        pipe.enable_vae_slicing()
    if hasattr(pipe, "enable_sequential_cpu_offload"):
        pipe.enable_sequential_cpu_offload()
    else:
        pipe.enable_model_cpu_offload()

    return pipe


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

# Default processing limits for VRAM-constrained environments
_DEFAULT_MAX_PROC_DIM = 384
_DEFAULT_BATCH_SIZE = 8


def process_video(
    input_path: Path,
    output_path: Path,
    cfg: dict,
    pipe,
) -> None:
    import torch

    mask_mode = cfg.get("mask", "background")
    mask_region = cfg.get("mask_region")
    prompt = cfg["prompt"]
    negative_prompt = cfg.get("negative_prompt", "worst quality, blurry, distorted")
    num_inference_steps = cfg.get("num_inference_steps", 30)
    guidance_scale = float(cfg.get("guidance_scale", 5.0))

    max_proc_dim = int(cfg.get("max_proc_dim", _DEFAULT_MAX_PROC_DIM))
    batch_size = int(cfg.get("batch_size", _DEFAULT_BATCH_SIZE))
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    if max_proc_dim < 64:
        raise ValueError("max_proc_dim must be >= 64")

    with tempfile.TemporaryDirectory(prefix="clawvace_") as tmp_str:
        tmp = Path(tmp_str)
        frames_in = tmp / "frames_in"
        frames_out = tmp / "frames_out"
        frames_in.mkdir()
        frames_out.mkdir()

        fps = extract_frames(input_path, frames_in)
        frame_paths = sorted(frames_in.glob("*.png"))
        print(f"  {len(frame_paths)} frames @ {fps:.2f} fps")

        # Load all frames
        frames = [Image.open(fp).convert("RGB") for fp in frame_paths]
        orig_w, orig_h = frames[0].size

        # Scale down for VACE processing (memory budget), keep aspect ratio
        scale = min(max_proc_dim / orig_w, max_proc_dim / orig_h, 1.0)
        proc_w = max(16, round(orig_w * scale / 16) * 16)
        proc_h = max(16, round(orig_h * scale / 16) * 16)

        # Compute mask from first frame, replicate for all frames
        first_frame_proc = frames[0].resize((proc_w, proc_h), Image.LANCZOS)
        if mask_mode == "background":
            print("  Computing background mask via rembg…")
            mask = make_background_mask(first_frame_proc)
        else:
            if not isinstance(mask_region, str) or not mask_region:
                raise ValueError("mask_region must be provided when mask='region'.")
            mask = make_region_mask(first_frame_proc, mask_region)

        frames_proc = [f.resize((proc_w, proc_h), Image.LANCZOS) for f in frames]
        masks_proc = [mask.resize((proc_w, proc_h), Image.NEAREST) for _ in frames]

        total_frames = len(frames_proc)
        print(
            f"  Editing {total_frames} frames @ {proc_w}×{proc_h} "
            f"in batches of {batch_size} [prompt: {prompt[:60]}…]"
        )

        output_frames = []
        for start in range(0, total_frames, batch_size):
            end = min(start + batch_size, total_frames)
            batch_frames = frames_proc[start:end]
            batch_masks = masks_proc[start:end]
            print(f"    Batch {start + 1}-{end}/{total_frames}")

            result = pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                video=batch_frames,
                mask=batch_masks,
                height=proc_h,
                width=proc_w,
                num_frames=len(batch_frames),
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                output_type="pil",
                generator=torch.Generator("cuda"),
            )

            # result.frames[0] is a list of PIL Images at proc dimensions
            output_frames.extend(result.frames[0])

            # Encourage allocator reuse between batches to reduce fragmentation
            torch.cuda.empty_cache()

        for fp, frame in zip(frame_paths, output_frames):
            # Resize back to original dimensions
            frame.resize((orig_w, orig_h), Image.LANCZOS).save(frames_out / fp.name)

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
        p
        for p in input_dir.iterdir()
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
    parser.add_argument(
        "--mask", choices=["background", "region"], help="Override mask mode"
    )
    parser.add_argument(
        "--mask-region", help="Override mask_region (x1,y1,x2,y2 fractions)"
    )
    parser.add_argument("--strength", type=float, help="Override strength")
    parser.add_argument("--steps", type=int, help="Override num_inference_steps")
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
    if args.steps is not None:
        cfg["num_inference_steps"] = args.steps
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
