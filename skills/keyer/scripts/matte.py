#!/usr/bin/env python3
"""
matte.py — clawmatte: remove background from video, frame by frame, using rembg.

Extracts frames with ffmpeg, removes the background from each frame using the
BiRefNet-general model (via rembg), optionally composites onto a background,
then reassembles the video. Audio is preserved.

Requires a CUDA GPU with at least 3 GB free VRAM (BiRefNet-general model).
Blocks with a clear error if VRAM is insufficient.

Usage:
  python scripts/matte.py [--config config.json]
  python scripts/matte.py --input ./input --output ./output --bg "#1a1a2e"
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}
VALID_MODELS = {
    "birefnet-general",
    "birefnet-portrait",
    "isnet-general-use",
    "u2net_human_seg",
}
MIN_VRAM_GB = 3.0


# ---------------------------------------------------------------------------
# GPU check
# ---------------------------------------------------------------------------

def check_gpu(required_gb: float = MIN_VRAM_GB) -> None:
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        if "CUDAExecutionProvider" not in providers:
            print("Error: clawmatte requires a CUDA GPU.", file=sys.stderr)
            print(f"  Required VRAM: {required_gb:.1f} GB", file=sys.stderr)
            print("  No CUDA execution provider found in onnxruntime.", file=sys.stderr)
            sys.exit(1)
    except ImportError:
        print("Error: onnxruntime not installed. Run: uv sync", file=sys.stderr)
        sys.exit(1)

    try:
        import torch
        if not torch.cuda.is_available():
            print("Error: clawmatte requires a CUDA-capable GPU.", file=sys.stderr)
            sys.exit(1)
        free, total = torch.cuda.mem_get_info()
        free_gb = free / 1024 ** 3
        total_gb = total / 1024 ** 3
        if free_gb < required_gb:
            used_gb = total_gb - free_gb
            print("Error: insufficient GPU VRAM for clawmatte.", file=sys.stderr)
            print(f"  Required:  {required_gb:.1f} GB", file=sys.stderr)
            print(f"  Available: {free_gb:.1f} GB  "
                  f"({used_gb:.1f} GB in use, {total_gb:.1f} GB total)", file=sys.stderr)
            print("  Tip: pause other GPU workloads (e.g. the LLM context) to free VRAM.",
                  file=sys.stderr)
            sys.exit(1)
        print(f"GPU: {torch.cuda.get_device_name()} — "
              f"{free_gb:.1f} GB free / {total_gb:.1f} GB total")
    except ImportError:
        pass  # torch not required for the ONNX path; ONNX check above is sufficient


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
    model = cfg.get("model", "birefnet-general")
    if model not in VALID_MODELS:
        errors.append(f"'model' must be one of: {', '.join(sorted(VALID_MODELS))}")
    bg = cfg.get("bg")
    if bg is not None and not isinstance(bg, str):
        errors.append("'bg' must be null, a hex colour string, or a file path")
    if errors:
        print("Config errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    return cfg


# ---------------------------------------------------------------------------
# Background compositing (reused from clawbg)
# ---------------------------------------------------------------------------

def composite_background(foreground: Image.Image, bg: str | None, size: tuple) -> Image.Image:
    if bg is None:
        return foreground

    bg_path = Path(bg)
    if bg_path.exists():
        bg_img = Image.open(bg_path).convert("RGBA").resize(size, Image.LANCZOS)
    else:
        try:
            bg_img = Image.new("RGBA", size, bg.strip())
        except Exception:
            bg_img = Image.new("RGBA", size, "#000000")

    bg_img.paste(foreground, mask=foreground.split()[3])
    return bg_img.convert("RGB")


# ---------------------------------------------------------------------------
# Video processing
# ---------------------------------------------------------------------------

def get_video_info(video_path: Path) -> tuple[float, str]:
    """Return (fps, size_str) for the video."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate,width,height",
         "-of", "default=noprint_wrappers=1", str(video_path)],
        capture_output=True, text=True,
    )
    fps = 30.0
    w, h = 1920, 1080
    for line in probe.stdout.splitlines():
        if "r_frame_rate=" in line:
            val = line.split("=")[1].strip()
            try:
                num, den = val.split("/")
                fps = float(num) / float(den)
            except Exception:
                pass
        elif "width=" in line:
            w = int(line.split("=")[1])
        elif "height=" in line:
            h = int(line.split("=")[1])
    return fps, f"{w}x{h}"


def process_video(
    input_path: Path,
    output_path: Path,
    model_name: str,
    bg: str | None,
    session,
) -> None:
    from rembg import remove

    with tempfile.TemporaryDirectory(prefix="clawmatte_") as tmp_str:
        tmp = Path(tmp_str)
        frames_in = tmp / "frames_in"
        frames_out = tmp / "frames_out"
        frames_in.mkdir()
        frames_out.mkdir()

        fps, size_str = get_video_info(input_path)
        print(f"  {size_str} @ {fps:.2f} fps")

        # Extract frames
        cmd = ["ffmpeg", "-y", "-i", str(input_path),
               str(frames_in / "%06d.png"), "-hide_banner", "-loglevel", "error"]
        subprocess.run(cmd, check=True)

        frame_paths = sorted(frames_in.glob("*.png"))
        print(f"  Matting {len(frame_paths)} frames…")

        size = None
        for i, fp in enumerate(frame_paths):
            img = Image.open(fp).convert("RGBA")
            if size is None:
                size = img.size
            cutout = remove(img, session=session)
            result = composite_background(cutout, bg, size)
            result.save(frames_out / fp.name)
            if (i + 1) % 30 == 0:
                print(f"    {i + 1}/{len(frame_paths)} frames done…")

        # Reassemble with original audio
        tmp_video = tmp / "video_only.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(frames_out / "%06d.png"),
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            str(tmp_video), "-hide_banner", "-loglevel", "error",
        ]
        subprocess.run(cmd, check=True)

        # Mux original audio back in
        cmd = [
            "ffmpeg", "-y",
            "-i", str(tmp_video),
            "-i", str(input_path),
            "-c:v", "copy", "-c:a", "aac",
            "-map", "0:v:0", "-map", "1:a:0?",
            "-shortest", str(output_path),
            "-hide_banner", "-loglevel", "error",
        ]
        subprocess.run(cmd, check=True)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process(config_path: Path) -> None:
    cfg = validate_config(load_config(config_path))
    check_gpu()

    from rembg import new_session

    input_dir = Path(cfg.get("input_dir", "./input"))
    output_dir = Path(cfg.get("output_dir", "./output"))
    model_name = cfg.get("model", "birefnet-general")
    bg = cfg.get("bg")

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

    print(f"Loading rembg model '{model_name}'…")
    session = new_session(model_name)

    bg_desc = bg if bg is not None else "transparent (alpha channel)"
    print(f"Processing {len(videos)} video(s), background={bg_desc}…")
    print()

    succeeded, failed = 0, []
    for video_path in videos:
        print(f"[{video_path.name}]")
        try:
            out_path = output_dir / video_path.with_suffix(".mp4").name
            process_video(video_path, out_path, model_name, bg, session)
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
    parser = argparse.ArgumentParser(description="clawmatte — video background removal")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--input", help="Override input_dir")
    parser.add_argument("--output", help="Override output_dir")
    parser.add_argument("--model", choices=list(VALID_MODELS), help="Override model")
    parser.add_argument("--bg", help="Background: null / hex colour / image path")
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
