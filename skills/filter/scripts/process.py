#!/usr/bin/env python3
"""
process.py — clawimig pipeline orchestrator

Reads a config file, processes all images from input_dir through:
  Stage 1: sharp (resize.js) — geometry, padding, format conversion
  Stage 2: pilgram          — Instagram filter application

Usage:
  python process.py [--config config.json]
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image

FORMATS = {
    "square":    (1080, 1080),
    "portrait":  (1080, 1350),
    "landscape": (1080, 566),
}

VALID_FILTERS = {
    "_1977", "aden", "brannan", "brooklyn", "clarendon", "earlybird",
    "gingham", "hudson", "inkwell", "kelvin", "lark", "lofi", "maven",
    "mayfair", "moon", "nashville", "perpetua", "reyes", "rise", "slumber",
    "stinson", "toaster", "valencia", "walden", "willow", "xpro2",
}

VALID_FIT = {"contain", "cover", "fill"}
VALID_OUTPUT_FORMATS = {"jpeg", "png", "webp"}
INPUT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

SCRIPT_DIR = Path(__file__).parent
RESIZE_JS = SCRIPT_DIR / "resize.js"
TMP_DIR = SCRIPT_DIR / "tmp"


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    with config_path.open() as f:
        return json.load(f)


def validate_config(cfg: dict) -> dict:
    errors = []

    fmt = cfg.get("format", "portrait")
    if fmt not in FORMATS and fmt != "custom":
        errors.append(f"'format' must be one of: {', '.join(FORMATS)} or 'custom'")

    if fmt == "custom":
        custom = cfg.get("custom_dimensions")
        if not custom or "width" not in custom or "height" not in custom:
            errors.append("'custom_dimensions' must have 'width' and 'height' when format is 'custom'")

    fit = cfg.get("fit", "contain")
    if fit not in VALID_FIT:
        errors.append(f"'fit' must be one of: {', '.join(VALID_FIT)}")

    output_format = cfg.get("output_format", "jpeg")
    if output_format not in VALID_OUTPUT_FORMATS:
        errors.append(f"'output_format' must be one of: {', '.join(VALID_OUTPUT_FORMATS)}")

    quality = cfg.get("quality", 90)
    if not isinstance(quality, int) or not (1 <= quality <= 100):
        errors.append("'quality' must be an integer between 1 and 100")

    filt = cfg.get("filter")
    if filt is not None and filt not in VALID_FILTERS:
        errors.append(f"'filter' must be one of: {', '.join(sorted(VALID_FILTERS))}, or null")

    if errors:
        print("Config validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    return cfg


def resolve_dimensions(cfg: dict) -> tuple[int, int]:
    fmt = cfg.get("format", "portrait")
    if fmt == "custom":
        d = cfg["custom_dimensions"]
        return d["width"], d["height"]
    return FORMATS[fmt]


def apply_filter(image_path: Path, filter_name: str, output_path: Path) -> None:
    import pilgram
    img = Image.open(image_path).convert("RGB")
    filter_fn = getattr(pilgram, filter_name)
    filtered = filter_fn(img)
    filtered.save(output_path)


def run_resize(input_path: Path, output_path: Path, width: int, height: int, cfg: dict) -> None:
    cmd = [
        "node", str(RESIZE_JS),
        "--input", str(input_path),
        "--output", str(output_path),
        "--width", str(width),
        "--height", str(height),
        "--fit", cfg.get("fit", "contain"),
        "--bg", cfg.get("background_color", "#ffffff"),
        "--format", cfg.get("output_format", "jpeg"),
        "--quality", str(cfg.get("quality", 90)),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "resize.js failed with no error message")
    if result.stdout:
        print(f"  {result.stdout.strip()}")


def output_filename(original: Path, output_format: str) -> str:
    ext_map = {"jpeg": ".jpg", "png": ".png", "webp": ".webp"}
    return original.stem + ext_map[output_format]


def process(config_path: Path) -> None:
    cfg = validate_config(load_config(config_path))

    input_dir = Path(cfg.get("input_dir", "./input"))
    output_dir = Path(cfg.get("output_dir", "./output"))

    if not input_dir.exists():
        print(f"Error: input_dir does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    width, height = resolve_dimensions(cfg)
    output_format = cfg.get("output_format", "jpeg")
    filt = cfg.get("filter")

    images = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in INPUT_EXTENSIONS
    )

    if not images:
        print(f"No images found in {input_dir} (supported: {', '.join(INPUT_EXTENSIONS)})")
        return

    print(f"Processing {len(images)} image(s): {width}x{height}, fit={cfg.get('fit','contain')}, filter={filt or 'none'}")
    print()

    succeeded = 0
    failed = []

    for img_path in images:
        out_name = output_filename(img_path, output_format)
        tmp_path = TMP_DIR / out_name
        final_path = output_dir / out_name

        print(f"[{img_path.name}]")
        try:
            run_resize(img_path, tmp_path, width, height, cfg)

            if filt:
                apply_filter(tmp_path, filt, final_path)
                print(f"  filter: {filt}")
            else:
                tmp_path.rename(final_path)

            print(f"  → {final_path}")
            succeeded += 1
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            failed.append(img_path.name)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    print()
    print(f"Done: {succeeded}/{len(images)} succeeded", end="")
    if failed:
        print(f", {len(failed)} failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="clawimig — Instagram image pipeline")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to config JSON file (default: config.json)",
    )
    args = parser.parse_args()
    process(Path(args.config))


if __name__ == "__main__":
    main()
