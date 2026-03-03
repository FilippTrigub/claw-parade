#!/usr/bin/env python3
"""
rembg_batch.py — clawbg: batch background removal for images.

Removes the background from every image in input_dir and writes results to
output_dir. Background can be:
  - null      → transparent PNG
  - "#rrggbb" → solid colour composite
  - a path    → image composite (resized to match)

Device selection:
  - "auto" / "cuda"  → GPU via ONNX CUDA execution provider
  - "cpu"            → CPU via ONNX CPU execution provider

Usage:
  python scripts/rembg_batch.py [--config config.json]
  python scripts/rembg_batch.py --input ./input --output ./output --bg "#ffffff"
  python scripts/rembg_batch.py --input ./input --output ./output --device cpu
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

INPUT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VALID_MODELS = {
    "isnet-general-use",
    "isnet-anime",
    "u2net",
    "u2net_human_seg",
    "u2netp",
    "birefnet-general",
}
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
    model = cfg.get("model", "isnet-general-use")
    if model not in VALID_MODELS:
        errors.append(f"'model' must be one of: {', '.join(sorted(VALID_MODELS))}")
    output_format = cfg.get("output_format", "png")
    if output_format not in {"png", "webp"}:
        errors.append("'output_format' must be 'png' or 'webp'")
    device = cfg.get("device", "auto")
    if device not in VALID_DEVICES:
        errors.append(f"'device' must be one of: {', '.join(VALID_DEVICES)}")
    bg = cfg.get("bg")
    if bg is not None and not isinstance(bg, str):
        errors.append("'bg' must be null, a hex colour string, or a file path")
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
        import onnxruntime as ort
        providers = ort.get_available_providers()
        return "cuda" if "CUDAExecutionProvider" in providers else "cpu"
    except Exception:
        return "cpu"


# ---------------------------------------------------------------------------
# Session creation
# ---------------------------------------------------------------------------

def make_session(model_name: str, device: str):
    from rembg import new_session
    if device == "cpu":
        return new_session(model_name, providers=["CPUExecutionProvider"])
    return new_session(model_name)  # auto-selects GPU if available


# ---------------------------------------------------------------------------
# Background compositing
# ---------------------------------------------------------------------------

def composite_background(
    foreground: Image.Image,
    bg: str | None,
) -> Image.Image:
    """
    Composite an RGBA foreground onto a background.
    bg: None → transparent PNG, "#rrggbb" → solid colour, path → image.
    """
    if bg is None:
        return foreground  # keep as RGBA

    bg_img: Image.Image
    bg_path = Path(bg)
    if bg_path.exists():
        bg_img = Image.open(bg_path).convert("RGBA").resize(
            foreground.size, Image.LANCZOS
        )
    else:
        # Treat as colour string
        try:
            colour = bg.strip()
            bg_img = Image.new("RGBA", foreground.size, colour)
        except Exception:
            print(f"  Warning: could not parse background '{bg}', using white", file=sys.stderr)
            bg_img = Image.new("RGBA", foreground.size, "#ffffff")

    bg_img.paste(foreground, mask=foreground.split()[3])
    return bg_img.convert("RGB")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process(config_path: Path) -> None:
    cfg = validate_config(load_config(config_path))

    input_dir = Path(cfg.get("input_dir", "./input"))
    output_dir = Path(cfg.get("output_dir", "./output"))
    model_name = cfg.get("model", "isnet-general-use")
    output_format = cfg.get("output_format", "png")
    bg = cfg.get("bg")
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

    print(f"Loading rembg model '{model_name}' on {device}…")
    from rembg import remove
    session = make_session(model_name, device)

    bg_desc = bg if bg is not None else "transparent"
    print(f"Processing {len(images)} image(s), background={bg_desc}…")
    print()

    succeeded, failed = 0, []
    ext = ".png" if output_format == "png" else ".webp"

    for img_path in images:
        print(f"[{img_path.name}]")
        try:
            image = Image.open(img_path).convert("RGBA")
            cutout = remove(image, session=session)
            result = composite_background(cutout, bg)

            out_path = output_dir / (img_path.stem + ext)
            save_kwargs = {"format": output_format.upper()}
            if output_format == "webp":
                save_kwargs["quality"] = 95
            result.save(out_path, **save_kwargs)

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
    parser = argparse.ArgumentParser(description="clawbg — batch background removal")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--input", help="Override input_dir")
    parser.add_argument("--output", help="Override output_dir")
    parser.add_argument("--model", choices=list(VALID_MODELS), help="Override rembg model")
    parser.add_argument("--bg", help="Override background (null / hex colour / image path)")
    parser.add_argument("--output-format", choices=["png", "webp"], help="Override output_format")
    parser.add_argument("--device", choices=list(VALID_DEVICES), help="Override device")
    args = parser.parse_args()

    cfg = validate_config(load_config(Path(args.config)))

    if args.input:
        cfg["input_dir"] = args.input
    if args.output:
        cfg["output_dir"] = args.output
    if args.model:
        cfg["model"] = args.model
    if args.bg is not None:
        cfg["bg"] = None if args.bg.lower() == "null" else args.bg
    if args.output_format:
        cfg["output_format"] = args.output_format
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
