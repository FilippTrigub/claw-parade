#!/usr/bin/env python3
"""
img2vid.py — clawanimate: animate still images into short video clips via LTX-Video.

Runs the LTX-Video image-to-video pipeline locally. Model weights are
downloaded once to ~/.cache/huggingface and reused on subsequent runs.

Requires a CUDA GPU with at least 8 GB free VRAM. Blocks with a clear error
if VRAM is insufficient.

Usage:
  python scripts/img2vid.py [--config config.json]
  python scripts/img2vid.py --input ./input --output ./output \
      --prompt "slow cinematic push-in, golden hour light"
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

INPUT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MIN_VRAM_GB = 8.0
DEFAULT_MODEL = "Lightricks/LTX-Video"


# ---------------------------------------------------------------------------
# GPU check
# ---------------------------------------------------------------------------

def check_gpu(required_gb: float = MIN_VRAM_GB) -> None:
    import torch
    if not torch.cuda.is_available():
        print("Error: clawanimate requires a CUDA-capable GPU.", file=sys.stderr)
        print(f"  Required VRAM: {required_gb:.1f} GB", file=sys.stderr)
        print("  No CUDA device detected.", file=sys.stderr)
        sys.exit(1)
    free, total = torch.cuda.mem_get_info()
    free_gb = free / 1024 ** 3
    total_gb = total / 1024 ** 3
    if free_gb < required_gb:
        used_gb = total_gb - free_gb
        print("Error: insufficient GPU VRAM for clawanimate.", file=sys.stderr)
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
    num_frames = cfg.get("num_frames", 81)
    if not isinstance(num_frames, int) or num_frames < 9:
        errors.append("'num_frames' must be an integer >= 9")
    for dim in ("width", "height"):
        val = cfg.get(dim, 512)
        if not isinstance(val, int) or val < 64 or val % 32 != 0:
            errors.append(f"'{dim}' must be a multiple of 32 and at least 64")
    if errors:
        print("Config errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    return cfg


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def load_pipeline(model_id: str):
    import torch
    from diffusers import LTXImageToVideoPipeline

    print(f"Loading LTX-Video pipeline from '{model_id}'…")
    print("  (First run downloads model weights — this may take several minutes.)")
    pipe = LTXImageToVideoPipeline.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
    )
    pipe.to("cuda")
    pipe.enable_model_cpu_offload()  # offload between steps to save VRAM
    return pipe


def generate(
    pipe,
    image: Image.Image,
    prompt: str,
    negative_prompt: str,
    num_frames: int,
    width: int,
    height: int,
    guidance_scale: float,
    num_inference_steps: int,
) -> list:
    import torch

    result = pipe(
        image=image,
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_frames=num_frames,
        width=width,
        height=height,
        guidance_scale=guidance_scale,
        num_inference_steps=num_inference_steps,
        generator=torch.Generator("cuda"),
    )
    return result.frames[0]  # list of PIL Images


def save_video(frames: list, output_path: Path, fps: int = 24) -> None:
    try:
        import imageio
        imageio.mimsave(str(output_path), frames, fps=fps)
    except ImportError:
        # Fallback: use ffmpeg via PIL frame dump
        import subprocess, tempfile
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            for i, frame in enumerate(frames):
                frame.save(tmp / f"{i:06d}.png")
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-i", str(tmp / "%06d.png"),
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                str(output_path), "-hide_banner", "-loglevel", "error",
            ]
            subprocess.run(cmd, check=True)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process(config_path: Path) -> None:
    cfg = validate_config(load_config(config_path))
    check_gpu()

    input_dir = Path(cfg.get("input_dir", "./input"))
    output_dir = Path(cfg.get("output_dir", "./output"))
    model_id = cfg.get("model", DEFAULT_MODEL)
    prompt = cfg["prompt"]
    negative_prompt = cfg.get("negative_prompt",
                              "worst quality, inconsistent motion, blurry, jittery, distorted")
    num_frames = cfg.get("num_frames", 81)
    width = cfg.get("width", 768)
    height = cfg.get("height", 512)
    guidance_scale = float(cfg.get("guidance_scale", 3.0))
    num_inference_steps = cfg.get("num_inference_steps", 40)

    if not input_dir.exists():
        print(f"Error: input_dir does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)

    images = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in INPUT_EXTENSIONS
    )
    if not images:
        print(f"No images found in {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    pipe = load_pipeline(model_id)

    print(f"Animating {len(images)} image(s): {width}×{height}, {num_frames} frames")
    print(f"  Prompt: {prompt[:80]}")
    print()

    succeeded, failed = 0, []
    for img_path in images:
        print(f"[{img_path.name}]")
        try:
            image = Image.open(img_path).convert("RGB").resize((width, height), Image.LANCZOS)
            frames = generate(
                pipe, image, prompt, negative_prompt,
                num_frames, width, height, guidance_scale, num_inference_steps,
            )
            out_path = output_dir / (img_path.stem + ".mp4")
            save_video(frames, out_path)
            print(f"  → {out_path}  ({len(frames)} frames)")
            succeeded += 1
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            failed.append(img_path.name)

    print()
    print(f"Done: {succeeded}/{len(images)} succeeded", end="")
    if failed:
        print(f", {len(failed)} failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="clawanimate — image to video")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--input", help="Override input_dir")
    parser.add_argument("--output", help="Override output_dir")
    parser.add_argument("--prompt", help="Override prompt")
    parser.add_argument("--negative-prompt", help="Override negative_prompt")
    parser.add_argument("--num-frames", type=int, help="Override num_frames")
    parser.add_argument("--width", type=int, help="Override width")
    parser.add_argument("--height", type=int, help="Override height")
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
    if args.negative_prompt:
        cfg["negative_prompt"] = args.negative_prompt
    if args.num_frames is not None:
        cfg["num_frames"] = args.num_frames
    if args.width is not None:
        cfg["width"] = args.width
    if args.height is not None:
        cfg["height"] = args.height
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
