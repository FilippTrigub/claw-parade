#!/usr/bin/env python3
"""
portrait.py — clawportrait: animate a portrait photo using a driving video.

Uses LivePortrait to transfer facial expressions and head motion from a
driver video onto a source portrait image. Model weights are downloaded
once and cached locally.

Requires a CUDA GPU with at least 4 GB free VRAM. Blocks with a clear error
if VRAM is insufficient.

Usage:
  python scripts/portrait.py [--config config.json]
  python scripts/portrait.py \
      --portrait ./input/headshot.jpg \
      --driver ./input/driver.mp4 \
      --output ./output/animated.mp4
"""

import argparse
import json
import sys
from pathlib import Path

MIN_VRAM_GB = 4.0


# ---------------------------------------------------------------------------
# GPU check
# ---------------------------------------------------------------------------

def check_gpu(required_gb: float = MIN_VRAM_GB) -> None:
    import torch
    if not torch.cuda.is_available():
        print("Error: clawportrait requires a CUDA-capable GPU.", file=sys.stderr)
        print(f"  Required VRAM: {required_gb:.1f} GB", file=sys.stderr)
        print("  No CUDA device detected.", file=sys.stderr)
        sys.exit(1)
    free, total = torch.cuda.mem_get_info()
    free_gb = free / 1024 ** 3
    total_gb = total / 1024 ** 3
    if free_gb < required_gb:
        used_gb = total_gb - free_gb
        print("Error: insufficient GPU VRAM for clawportrait.", file=sys.stderr)
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
    portrait = cfg.get("portrait")
    driver = cfg.get("driver")
    if not portrait:
        errors.append("'portrait' path is required (source face image)")
    if not driver:
        errors.append("'driver' path is required (driving video)")
    if portrait and not Path(portrait).exists():
        errors.append(f"portrait file not found: {portrait}")
    if driver and not Path(driver).exists():
        # driver might be a directory; check both
        if not Path(driver).exists():
            errors.append(f"driver file/directory not found: {driver}")
    if errors:
        print("Config errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    return cfg


# ---------------------------------------------------------------------------
# LivePortrait inference
# ---------------------------------------------------------------------------

def run_liveportrait(
    portrait_path: Path,
    driver_path: Path,
    output_path: Path,
    flag_relative_motion: bool,
    flag_pasteback: bool,
    flag_crop_driving_video: bool,
) -> None:
    """
    Run LivePortrait using its Python API.
    LivePortrait downloads model weights from HuggingFace on first run.
    """
    try:
        from liveportrait.live_portrait_pipeline import LivePortraitPipeline
        from liveportrait.config.argument_config import ArgumentConfig
        from liveportrait.config.inference_config import InferenceConfig
        from liveportrait.config.crop_config import CropConfig
    except ImportError:
        print("Error: liveportrait is not installed.", file=sys.stderr)
        print("  Run: uv sync", file=sys.stderr)
        sys.exit(1)

    infer_cfg = InferenceConfig(
        flag_use_half_precision=True,
        flag_relative_motion=flag_relative_motion,
        flag_pasteback=flag_pasteback,
        flag_crop_driving_video=flag_crop_driving_video,
    )
    crop_cfg = CropConfig()

    pipeline = LivePortraitPipeline(inference_cfg=infer_cfg, crop_cfg=crop_cfg)

    # LivePortrait accepts source image path and driving video path
    # and writes the result video to a specified path
    args = ArgumentConfig(
        source_image=str(portrait_path),
        driving_video=str(driver_path),
        output_dir=str(output_path.parent),
    )

    pipeline.execute(args)

    # LivePortrait writes to output_dir/<source_stem>--<driver_stem>.mp4
    # Find and rename if needed
    expected_name = f"{portrait_path.stem}--{driver_path.stem}.mp4"
    expected = output_path.parent / expected_name
    if expected.exists() and expected != output_path:
        expected.rename(output_path)


def run_liveportrait_batch(
    portrait_path: Path,
    driver_dir: Path,
    output_dir: Path,
    cfg: dict,
) -> tuple[int, list]:
    """Animate one portrait against multiple driver videos."""
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
    drivers = sorted(
        p for p in driver_dir.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not drivers:
        print(f"No driver videos found in {driver_dir}", file=sys.stderr)
        return 0, []

    succeeded, failed = 0, []
    for driver in drivers:
        out_path = output_dir / f"{portrait_path.stem}--{driver.stem}.mp4"
        print(f"  Driver: {driver.name}")
        try:
            run_liveportrait(
                portrait_path, driver, out_path,
                cfg.get("flag_relative_motion", True),
                cfg.get("flag_pasteback", True),
                cfg.get("flag_crop_driving_video", True),
            )
            print(f"  → {out_path}")
            succeeded += 1
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            failed.append(driver.name)

    return succeeded, failed


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process(config_path: Path) -> None:
    cfg = validate_config(load_config(config_path))
    check_gpu()

    portrait_path = Path(cfg["portrait"])
    driver_path = Path(cfg["driver"])
    output_dir = Path(cfg.get("output_dir", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Portrait: {portrait_path}")
    print(f"Driver:   {driver_path}")
    print()

    if driver_path.is_dir():
        print(f"Batch mode: animating portrait against all videos in {driver_path}")
        succeeded, failed = run_liveportrait_batch(
            portrait_path, driver_path, output_dir, cfg
        )
    else:
        out_path = output_dir / f"{portrait_path.stem}--{driver_path.stem}.mp4"
        try:
            run_liveportrait(
                portrait_path, driver_path, out_path,
                cfg.get("flag_relative_motion", True),
                cfg.get("flag_pasteback", True),
                cfg.get("flag_crop_driving_video", True),
            )
            print(f"→ {out_path}")
            succeeded, failed = 1, []
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            succeeded, failed = 0, [driver_path.name]

    print()
    total = succeeded + len(failed)
    print(f"Done: {succeeded}/{total} succeeded", end="")
    if failed:
        print(f", {len(failed)} failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="clawportrait — talking head animation")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--portrait", help="Override portrait (source face image)")
    parser.add_argument("--driver", help="Override driver (driving video or directory)")
    parser.add_argument("--output", help="Override output_dir")
    parser.add_argument(
        "--no-relative-motion", action="store_true",
        help="Disable relative motion mode (use absolute motion instead)",
    )
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    if args.portrait:
        cfg["portrait"] = args.portrait
    if args.driver:
        cfg["driver"] = args.driver
    if args.output:
        cfg["output_dir"] = args.output
    if args.no_relative_motion:
        cfg["flag_relative_motion"] = False

    validate_config(cfg)

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
