#!/usr/bin/env python3
"""
bokeh.py — clawdepth: apply synthetic depth-of-field bokeh to images.

Uses MiDaS (DPT_Large or DPT_Hybrid) to estimate depth from a single image,
then blends a progressively blurred version of the image against the original
using the depth map as a mask. Near objects stay sharp, far objects blur.

Usage:
  python scripts/bokeh.py [--config config.json]
  python scripts/bokeh.py --input ./input --output ./output --blur-strength 20
  python scripts/bokeh.py --input ./input --output ./output --device cpu
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

INPUT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VALID_MODELS = {"DPT_Large", "DPT_Hybrid", "MiDaS_small"}
VALID_DEVICES = {"auto", "cpu", "cuda"}


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
    model = cfg.get("model", "DPT_Large")
    if model not in VALID_MODELS:
        errors.append(f"'model' must be one of: {', '.join(VALID_MODELS)}")
    blur = cfg.get("blur_strength", 15)
    if not isinstance(blur, (int, float)) or blur <= 0:
        errors.append("'blur_strength' must be a positive number")
    device = cfg.get("device", "auto")
    if device not in VALID_DEVICES:
        errors.append(f"'device' must be one of: {', '.join(VALID_DEVICES)}")
    if errors:
        print("Config errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    return cfg


def resolve_device(cfg: dict) -> str:
    device = cfg.get("device", "auto")
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


# ---------------------------------------------------------------------------
# Depth estimation
# ---------------------------------------------------------------------------

def load_midas(model_name: str, device: str):
    import torch
    model = torch.hub.load("intel-isl/MiDaS", model_name, trust_repo=True)
    model.to(device)
    model.eval()
    transforms = torch.hub.load("intel-isl/MiDaS", "transforms", trust_repo=True)
    if model_name == "MiDaS_small":
        transform = transforms.small_transform
    else:
        transform = transforms.dpt_transform
    return model, transform


def predict_depth(image: Image.Image, model, transform, device: str) -> np.ndarray:
    """Return a depth map normalised to [0, 1] where 1 = nearest."""
    import torch
    import cv2

    img_np = np.array(image.convert("RGB"))
    input_batch = transform(img_np).to(device)

    with torch.no_grad():
        prediction = model(input_batch)
        prediction = torch.nn.functional.interpolate(
            prediction.unsqueeze(1),
            size=img_np.shape[:2],
            mode="bicubic",
            align_corners=False,
        ).squeeze()

    depth = prediction.cpu().numpy()
    d_min, d_max = depth.min(), depth.max()
    if d_max > d_min:
        depth = (depth - d_min) / (d_max - d_min)
    else:
        depth = np.zeros_like(depth)
    return depth.astype(np.float32)


# ---------------------------------------------------------------------------
# Bokeh compositing
# ---------------------------------------------------------------------------

def apply_bokeh(image: Image.Image, depth: np.ndarray, blur_strength: int) -> Image.Image:
    """
    Blend a sharp and progressively blurred image using the depth map.
    Near (depth→1) = sharp.  Far (depth→0) = max blur.
    """
    n_levels = 6
    img_f = np.array(image.convert("RGB"), dtype=np.float32)
    result = img_f.copy()

    for i in range(1, n_levels + 1):
        radius = int(blur_strength * i / n_levels)
        if radius < 1:
            continue
        blurred = np.array(
            image.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32
        )
        # Apply blur where depth is low (far) for this level
        threshold = 1.0 - (i - 1) / n_levels
        alpha = np.clip((threshold - depth) * n_levels, 0.0, 1.0)
        alpha_3c = alpha[:, :, np.newaxis]
        result = result * (1.0 - alpha_3c) + blurred * alpha_3c

    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process(config_path: Path) -> None:
    cfg = validate_config(load_config(config_path))

    input_dir = Path(cfg.get("input_dir", "./input"))
    output_dir = Path(cfg.get("output_dir", "./output"))
    model_name = cfg.get("model", "DPT_Large")
    blur_strength = int(cfg.get("blur_strength", 15))
    device = resolve_device(cfg)

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

    print(f"Loading MiDaS {model_name} on {device}…")
    model, transform = load_midas(model_name, device)

    print(f"Processing {len(images)} image(s), blur_strength={blur_strength}…")
    print()

    succeeded, failed = 0, []

    for img_path in images:
        print(f"[{img_path.name}]")
        try:
            image = Image.open(img_path).convert("RGB")
            depth = predict_depth(image, model, transform, device)
            result = apply_bokeh(image, depth, blur_strength)

            out_path = output_dir / img_path.name
            result.save(out_path)
            print(f"  → {out_path}")
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
    parser = argparse.ArgumentParser(description="clawdepth — synthetic bokeh via MiDaS")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--input", help="Override input_dir")
    parser.add_argument("--output", help="Override output_dir")
    parser.add_argument("--model", choices=list(VALID_MODELS), help="Override MiDaS model")
    parser.add_argument("--blur-strength", type=int, help="Override blur_strength")
    parser.add_argument("--device", choices=list(VALID_DEVICES), help="Override device")
    args = parser.parse_args()

    cfg = validate_config(load_config(Path(args.config)))

    if args.input:
        cfg["input_dir"] = args.input
    if args.output:
        cfg["output_dir"] = args.output
    if args.model:
        cfg["model"] = args.model
    if args.blur_strength is not None:
        cfg["blur_strength"] = args.blur_strength
    if args.device:
        cfg["device"] = args.device

    import tempfile, json as _json
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        _json.dump(cfg, tmp)
        tmp_path = Path(tmp.name)

    try:
        process(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
