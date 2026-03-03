#!/usr/bin/env python3
"""
interpolate.py — clawrife: AI frame interpolation using RAFT optical flow.

Uses torchvision's RAFT model to estimate optical flow between consecutive
frames, then backward-warps each source frame to the intermediate timestep
and blends the two warped results. Supports 2× and 4× multipliers.

Requires a CUDA GPU with at least 2 GB free VRAM. Blocks with a clear error
if VRAM is insufficient.

Usage:
  python scripts/interpolate.py [--config config.json]
  python scripts/interpolate.py --input ./input --output ./output --multiplier 2
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}
VALID_MODELS = {"raft_large", "raft_small"}
VALID_MULTIPLIERS = {2, 4}
MIN_VRAM_GB = 2.0


# ---------------------------------------------------------------------------
# GPU check
# ---------------------------------------------------------------------------

def check_gpu(required_gb: float = MIN_VRAM_GB) -> None:
    import torch
    if not torch.cuda.is_available():
        print("Error: clawrife requires a CUDA-capable GPU.", file=sys.stderr)
        print(f"  Required VRAM: {required_gb:.1f} GB", file=sys.stderr)
        print("  No CUDA device detected.", file=sys.stderr)
        sys.exit(1)
    free, total = torch.cuda.mem_get_info()
    free_gb = free / 1024 ** 3
    total_gb = total / 1024 ** 3
    if free_gb < required_gb:
        used_gb = total_gb - free_gb
        print("Error: insufficient GPU VRAM for clawrife.", file=sys.stderr)
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
    mult = cfg.get("multiplier", 2)
    if mult not in VALID_MULTIPLIERS:
        errors.append(f"'multiplier' must be one of: {sorted(VALID_MULTIPLIERS)}")
    model = cfg.get("model", "raft_large")
    if model not in VALID_MODELS:
        errors.append(f"'model' must be one of: {', '.join(sorted(VALID_MODELS))}")
    if errors:
        print("Config errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    return cfg


# ---------------------------------------------------------------------------
# RAFT optical flow + warping
# ---------------------------------------------------------------------------

def load_raft(model_name: str, device: str):
    import torch
    from torchvision.models.optical_flow import raft_large, raft_small
    from torchvision.models.optical_flow import Raft_Large_Weights, Raft_Small_Weights

    print(f"Loading {model_name} on {device}…")
    if model_name == "raft_small":
        weights = Raft_Small_Weights.DEFAULT
        model = raft_small(weights=weights)
    else:
        weights = Raft_Large_Weights.DEFAULT
        model = raft_large(weights=weights)

    model.to(device).eval()
    return model, weights.transforms()


def frames_to_tensor(frames: list, transform, device: str) -> "torch.Tensor":
    """Convert list of (H,W,3) uint8 numpy arrays to a batched tensor."""
    import torch
    from PIL import Image

    imgs = [Image.fromarray(f) for f in frames]
    # transform expects two PIL images and returns a pair of tensors
    # We'll preprocess each frame individually
    tensors = []
    for img in imgs:
        t = transform(img, img)[0]  # transform returns (img1_t, img2_t); we take img1
        tensors.append(t)
    return torch.stack(tensors).to(device)


def estimate_flow(model, frame1_t: "torch.Tensor", frame2_t: "torch.Tensor") -> "torch.Tensor":
    """Return optical flow from frame1 to frame2. Shape: (1, 2, H, W)."""
    import torch
    with torch.no_grad():
        # raft returns a list of flow predictions; take the last (finest) one
        flows = model(frame1_t.unsqueeze(0), frame2_t.unsqueeze(0))
        return flows[-1]


def warp_frame(frame_t: "torch.Tensor", flow: "torch.Tensor", t: float) -> "torch.Tensor":
    """
    Backward-warp frame_t by t * flow using bilinear grid_sample.
    frame_t: (1, C, H, W) float32
    flow:    (1, 2, H, W) — flow from this frame toward the other frame
    """
    import torch
    import torch.nn.functional as F

    _, _, H, W = frame_t.shape
    scaled_flow = flow * t

    # Build normalised sampling grid
    grid_y, grid_x = torch.meshgrid(
        torch.linspace(-1, 1, H, device=frame_t.device),
        torch.linspace(-1, 1, W, device=frame_t.device),
        indexing="ij",
    )
    base_grid = torch.stack([grid_x, grid_y], dim=-1).unsqueeze(0)  # (1, H, W, 2)

    # Normalise flow to [-1, 1] range
    norm_flow = torch.stack([
        scaled_flow[:, 0] / (W / 2),
        scaled_flow[:, 1] / (H / 2),
    ], dim=-1)  # (1, H, W, 2) — wait, flow is (1, 2, H, W)

    norm_flow = scaled_flow.permute(0, 2, 3, 1).clone()
    norm_flow[..., 0] /= (W / 2)
    norm_flow[..., 1] /= (H / 2)

    sampling_grid = base_grid + norm_flow
    warped = F.grid_sample(frame_t, sampling_grid, mode="bilinear",
                           padding_mode="border", align_corners=True)
    return warped


def interpolate_pair(
    frame1_np: np.ndarray,
    frame2_np: np.ndarray,
    model,
    transform,
    device: str,
    t: float,
) -> np.ndarray:
    """
    Produce one interpolated frame at timestep t ∈ (0, 1) between frame1 and frame2.
    """
    import torch

    f1 = torch.from_numpy(frame1_np).permute(2, 0, 1).float().unsqueeze(0).to(device) / 255.0
    f2 = torch.from_numpy(frame2_np).permute(2, 0, 1).float().unsqueeze(0).to(device) / 255.0

    # Preprocess for RAFT (normalise to [-1,1])
    def preprocess(x: "torch.Tensor") -> "torch.Tensor":
        return (x * 2.0) - 1.0

    f1_pre = preprocess(f1)
    f2_pre = preprocess(f2)

    flow_1_to_2 = estimate_flow(model, f1_pre, f2_pre)
    flow_2_to_1 = estimate_flow(model, f2_pre, f1_pre)

    warped_f1 = warp_frame(f1, flow_1_to_2, t)
    warped_f2 = warp_frame(f2, flow_2_to_1, 1.0 - t)

    blended = warped_f1 * (1.0 - t) + warped_f2 * t
    out_np = (blended.squeeze(0).permute(1, 2, 0).cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    return out_np


# ---------------------------------------------------------------------------
# Video I/O
# ---------------------------------------------------------------------------

def read_video_frames(video_path: Path, tmp_dir: Path) -> tuple[list[np.ndarray], float]:
    """Extract all frames as PNG files; return list of numpy arrays and fps."""
    from PIL import Image

    frames_dir = tmp_dir / "frames_in"
    frames_dir.mkdir()

    # Get fps
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

    # Extract frames
    cmd = ["ffmpeg", "-y", "-i", str(video_path),
           str(frames_dir / "%06d.png"), "-hide_banner", "-loglevel", "error"]
    subprocess.run(cmd, check=True)

    frame_paths = sorted(frames_dir.glob("*.png"))
    frames = [np.array(Image.open(p).convert("RGB")) for p in frame_paths]
    return frames, fps


def write_video_frames(frames: list[np.ndarray], fps: float, tmp_dir: Path, output_path: Path) -> None:
    from PIL import Image

    frames_dir = tmp_dir / "frames_out"
    frames_dir.mkdir()
    for i, frame in enumerate(frames):
        Image.fromarray(frame).save(frames_dir / f"{i:06d}.png")

    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "%06d.png"),
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
        str(output_path), "-hide_banner", "-loglevel", "error",
    ]
    subprocess.run(cmd, check=True)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_video(
    input_path: Path,
    output_path: Path,
    multiplier: int,
    model,
    transform,
    device: str,
) -> None:
    with tempfile.TemporaryDirectory(prefix="clawrife_") as tmp_str:
        tmp = Path(tmp_str)
        print(f"  Extracting frames…")
        frames, fps = read_video_frames(input_path, tmp)
        print(f"  {len(frames)} frames at {fps:.2f} fps → {len(frames) * multiplier - (multiplier - 1)} output frames")

        out_frames: list[np.ndarray] = []
        steps = multiplier  # number of intervals between two source frames

        for i in range(len(frames) - 1):
            out_frames.append(frames[i])
            for k in range(1, steps):
                t = k / steps
                interp = interpolate_pair(frames[i], frames[i + 1], model, transform, device, t)
                out_frames.append(interp)

        out_frames.append(frames[-1])

        out_fps = fps * multiplier
        print(f"  Writing {len(out_frames)} frames at {out_fps:.2f} fps…")
        write_video_frames(out_frames, out_fps, tmp, output_path)


def process(config_path: Path) -> None:
    cfg = validate_config(load_config(config_path))

    check_gpu()

    import torch
    device = "cuda"

    input_dir = Path(cfg.get("input_dir", "./input"))
    output_dir = Path(cfg.get("output_dir", "./output"))
    multiplier = cfg.get("multiplier", 2)
    model_name = cfg.get("model", "raft_large")

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
    model, transform = load_raft(model_name, device)

    print(f"Processing {len(videos)} video(s) at {multiplier}× frame rate…")
    print()

    succeeded, failed = 0, []
    for video_path in videos:
        print(f"[{video_path.name}]")
        try:
            out_path = output_dir / video_path.with_suffix(".mp4").name
            process_video(video_path, out_path, multiplier, model, transform, device)
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
    parser = argparse.ArgumentParser(description="clawrife — AI frame interpolation")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--input", help="Override input_dir")
    parser.add_argument("--output", help="Override output_dir")
    parser.add_argument("--multiplier", type=int, choices=[2, 4], help="Frame rate multiplier")
    parser.add_argument("--model", choices=list(VALID_MODELS), help="Override RAFT model")
    args = parser.parse_args()

    cfg = validate_config(load_config(Path(args.config)))
    if args.input:
        cfg["input_dir"] = args.input
    if args.output:
        cfg["output_dir"] = args.output
    if args.multiplier is not None:
        cfg["multiplier"] = args.multiplier
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
