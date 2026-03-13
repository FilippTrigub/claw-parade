#!/usr/bin/env python3
"""
txt2img.py — Generate images from text prompts using HuggingFace diffusers.

Supports multiple model architectures:
- FLUX (black-forest-labs/FLUX.1-dev, FLUX.1-schnell)
- SDXL (stabilityai/stable-diffusion-xl-base-1.0)
- SD3 (stabilityai/stable-diffusion-3-medium)
- Playground v2 (playgroundai/playground-v2.5-1024px-aesthetic)
- Any custom diffusers-compatible model

Usage:
    python scripts/txt2img.py --config config.json
    python scripts/txt2img.py --prompt "a cat sitting on a couch" --model flux
    python scripts/txt2img.py --prompt "landscape" --model sdxl --output ./output
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image

# Supported predefined models with their configurations
PREDEFINED_MODELS = {
    "flux": {
        "id": "black-forest-labs/FLUX.1-dev",
        "min_vram_gb": 12.0,
        "pipeline": "flux",
        "default_steps": 28,
        "default_guidance": 3.5,
    },
    "flux-schnell": {
        "id": "black-forest-labs/FLUX.1-schnell",
        "min_vram_gb": 12.0,
        "pipeline": "flux",
        "default_steps": 4,
        "default_guidance": 1.0,
    },
    "sdxl": {
        "id": "stabilityai/stable-diffusion-xl-base-1.0",
        "min_vram_gb": 8.0,
        "pipeline": "sdxl",
        "default_steps": 30,
        "default_guidance": 7.5,
    },
    "sd3": {
        "id": "stabilityai/stable-diffusion-3-medium",
        "min_vram_gb": 6.0,
        "pipeline": "sd3",
        "default_steps": 28,
        "default_guidance": 7.0,
    },
    "playground": {
        "id": "playgroundai/playground-v2.5-1024px-aesthetic",
        "min_vram_gb": 6.0,
        "pipeline": "playground",
        "default_steps": 30,
        "default_guidance": 3.0,
    },
}

DEFAULT_MODEL = "flux"
MIN_VRAM_GB = 6.0


# ---------------------------------------------------------------------------
# GPU check
# ---------------------------------------------------------------------------


def check_gpu(required_gb: float = MIN_VRAM_GB) -> None:
    import torch

    if not torch.cuda.is_available():
        print(
            "Error: text-to-image generation requires a CUDA-capable GPU.",
            file=sys.stderr,
        )
        print(f"  Required VRAM: {required_gb:.1f} GB", file=sys.stderr)
        print("  No CUDA device detected.", file=sys.stderr)
        sys.exit(1)
    free, total = torch.cuda.mem_get_info()
    free_gb = free / 1024**3
    total_gb = total / 1024**3
    if free_gb < required_gb:
        used_gb = total_gb - free_gb
        print(
            "Error: insufficient GPU VRAM for text-to-image generation.",
            file=sys.stderr,
        )
        print(f"  Required:  {required_gb:.1f} GB", file=sys.stderr)
        print(
            f"  Available: {free_gb:.1f} GB  "
            f"({used_gb:.1f} GB in use, {total_gb:.1f} GB total)",
            file=sys.stderr,
        )
        print("  Tip: pause other GPU workloads to free VRAM.", file=sys.stderr)
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


def resolve_model(model_arg: str) -> dict:
    """Resolve model argument to full config."""
    if model_arg in PREDEFINED_MODELS:
        return PREDEFINED_MODELS[model_arg]
    # Assume it's a HuggingFace model ID
    return {
        "id": model_arg,
        "min_vram_gb": 8.0,  # Default assumption
        "pipeline": "auto",
        "default_steps": 25,
        "default_guidance": 7.0,
    }


def validate_config(cfg: dict) -> dict:
    errors = []
    if not cfg.get("prompt"):
        errors.append("'prompt' is required")

    width = cfg.get("width", 1024)
    height = cfg.get("height", 1024)

    # Model-specific validation
    model_key = cfg.get("model", DEFAULT_MODEL)
    model_config = resolve_model(model_key)

    # Some models have resolution constraints
    if model_key.startswith("flux"):
        # FLUX works best with specific resolutions
        if width % 8 != 0 or height % 8 != 0:
            errors.append("FLUX requires width and height to be multiples of 8")

    if errors:
        print("Config errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    # Set defaults based on model
    if "num_inference_steps" not in cfg:
        cfg["num_inference_steps"] = model_config["default_steps"]
    if "guidance_scale" not in cfg:
        cfg["guidance_scale"] = model_config["default_guidance"]

    return cfg


# ---------------------------------------------------------------------------
# Pipeline loading
# ---------------------------------------------------------------------------


def load_pipeline(
    model_id: str, pipeline_type: str = "auto", torch_dtype: str = "bfloat16"
):
    """Load the diffusion pipeline."""
    import torch
    from diffusers import DiffusionPipeline
    from diffusers.pipelines import StableDiffusionXLPipeline
    from diffusers.pipelines import StableDiffusion3Pipeline

    print(f"Loading pipeline from '{model_id}'…")
    print("  (First run downloads model weights — this may take several minutes.)")

    dtype_map = {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }

    try:
        # Try to load as DiffusionPipeline (auto-detects architecture)
        pipe = DiffusionPipeline.from_pretrained(
            model_id,
            torch_dtype=dtype_map.get(torch_dtype, torch.bfloat16),
        )
    except Exception as e:
        print(f"Warning: Auto-detection failed: {e}", file=sys.stderr)
        print("Trying with specific pipeline type…", file=sys.stderr)

        # Try SDXL
        try:
            pipe = StableDiffusionXLPipeline.from_pretrained(
                model_id,
                torch_dtype=dtype_map.get(torch_dtype, torch.bfloat16),
            )
        except Exception:
            # Try SD3
            pipe = StableDiffusion3Pipeline.from_pretrained(
                model_id,
                torch_dtype=dtype_map.get(torch_dtype, torch.bfloat16),
            )

    pipe.to("cuda")

    # Enable memory optimizations
    pipe.enable_model_cpu_offload()

    # Try to enable attention slicing for smaller GPUs
    try:
        pipe.enable_attention_slicing("auto")
    except Exception:
        pass

    return pipe


def generate(
    pipe,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    num_inference_steps: int,
    guidance_scale: float,
    seed: int | None = None,
) -> Image.Image:
    """Generate an image from a prompt."""
    import torch

    generator = None
    if seed is not None:
        generator = torch.Generator("cuda").manual_seed(seed)

    result = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        generator=generator,
    )

    return result.images[0]


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------


def process(config_path: Path) -> None:
    cfg = validate_config(load_config(config_path))

    # Resolve model
    model_key = cfg.get("model", DEFAULT_MODEL)
    model_config = resolve_model(model_key)

    check_gpu(model_config["min_vram_gb"])

    output_dir = Path(cfg.get("output_dir", "./output"))
    prompt = cfg["prompt"]
    negative_prompt = cfg.get(
        "negative_prompt", "worst quality, low quality, blurry, distorted, ugly"
    )
    width = cfg.get("width", 1024)
    height = cfg.get("height", 1024)
    num_inference_steps = cfg.get("num_inference_steps", model_config["default_steps"])
    guidance_scale = cfg.get("guidance_scale", model_config["default_guidance"])
    seed = cfg.get("seed", None)
    num_images = cfg.get("num_images", 1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load pipeline
    pipe = load_pipeline(model_config["id"], model_config.get("pipeline", "auto"))

    print(f"Generating {num_images} image(s): {width}x{height}")
    print(f"  Model: {model_config['id']}")
    print(f"  Prompt: {prompt[:80]}...")
    print(f"  Steps: {num_inference_steps}, CFG: {guidance_scale}")
    print()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for i in range(num_images):
        img_seed = (seed + i) if seed is not None else None
        print(f"[{i + 1}/{num_images}]" + (f" seed={img_seed}" if img_seed else ""))

        try:
            image = generate(
                pipe,
                prompt,
                negative_prompt,
                width,
                height,
                num_inference_steps,
                guidance_scale,
                img_seed,
            )

            out_path = output_dir / f"{timestamp}_{i + 1:03d}.png"
            image.save(out_path)
            print(f"  → {out_path}")
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)

    print("\nDone.")


def main() -> None:
    parser = argparse.ArgumentParser(description="txt2img — text to image generation")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--prompt", help="Text prompt")
    parser.add_argument("--negative-prompt", help="Negative prompt")
    parser.add_argument(
        "--model",
        help="Model: flux, flux-schnell, sdxl, sd3, playground, or HF model ID",
    )
    parser.add_argument("--output", dest="output_dir", help="Output directory")
    parser.add_argument("--width", type=int, help="Image width")
    parser.add_argument("--height", type=int, help="Image height")
    parser.add_argument(
        "--steps", type=int, dest="num_inference_steps", help="Inference steps"
    )
    parser.add_argument(
        "--cfg", type=float, dest="guidance_scale", help="Guidance scale (CFG)"
    )
    parser.add_argument("--seed", type=int, help="Random seed")
    parser.add_argument(
        "--num-images", type=int, default=1, help="Number of images to generate"
    )
    args = parser.parse_args()

    # Load and merge config
    cfg = validate_config(load_config(Path(args.config)))

    # Override with CLI args
    if args.prompt:
        cfg["prompt"] = args.prompt
    if args.negative_prompt:
        cfg["negative_prompt"] = args.negative_prompt
    if args.model:
        cfg["model"] = args.model
    if args.output_dir:
        cfg["output_dir"] = args.output_dir
    if args.width:
        cfg["width"] = args.width
    if args.height:
        cfg["height"] = args.height
    if args.num_inference_steps:
        cfg["num_inference_steps"] = args.num_inference_steps
    if args.guidance_scale:
        cfg["guidance_scale"] = args.guidance_scale
    if args.seed is not None:
        cfg["seed"] = args.seed
    if args.num_images:
        cfg["num_images"] = args.num_images

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
