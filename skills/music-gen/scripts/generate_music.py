#!/usr/bin/env python3
"""
generate_music.py — clawbeat: generate royalty-free background music via MusicGen.

Generates music from a text prompt and either:
  - saves it as a WAV file, or
  - mixes it under a video at a target loudness level (music_volume_lufs).

Models:
  small    — 300M, ~3GB VRAM, fast (default)
  medium   — 1.5B, ~8GB VRAM, higher quality
  melody   — 1.5B, text + reference melody conditioning

Device:
  "auto" / "cuda" → GPU
  "cpu"           → CPU (small model only; very slow, ~10× realtime)

Usage:
  python scripts/generate_music.py [--config config.json]
  python scripts/generate_music.py --prompt "upbeat jazz" --duration 30
  python scripts/generate_music.py --video ./input/clip.mp4 --prompt "lo-fi chill"
  python scripts/generate_music.py --device cpu --model small --duration 15
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

VALID_MODELS = {"small", "medium", "melody", "large"}
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
    model = cfg.get("model", "small")
    if model not in VALID_MODELS:
        errors.append(f"'model' must be one of: {', '.join(sorted(VALID_MODELS))}")
    device = cfg.get("device", "auto")
    if device not in VALID_DEVICES:
        errors.append(f"'device' must be one of: {', '.join(VALID_DEVICES)}")
    if device == "cpu" and model != "small":
        errors.append("CPU mode is only practical with model='small'")
    duration = cfg.get("duration", 30)
    if not isinstance(duration, (int, float)) or duration <= 0 or duration > 300:
        errors.append("'duration' must be a number between 1 and 300 seconds")
    if not cfg.get("prompt"):
        errors.append("'prompt' is required")
    lufs = cfg.get("music_volume_lufs", -20)
    if not isinstance(lufs, (int, float)) or lufs > 0:
        errors.append("'music_volume_lufs' must be a negative number (e.g. -20)")
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
# Generation
# ---------------------------------------------------------------------------

def generate_music(
    prompt: str,
    duration: float,
    model_name: str,
    device: str,
    melody_path: Path | None = None,
) -> tuple["torch.Tensor", int]:
    """Return (audio_tensor, sample_rate) via HuggingFace transformers MusicGen."""
    import torch
    from transformers import AutoProcessor, MusicgenForConditionalGeneration

    hf_model_id = f"facebook/musicgen-{model_name}"
    print(f"Loading MusicGen '{model_name}' on {device}…")
    if device == "cpu":
        print("  Note: CPU mode is very slow (~10× realtime). This may take several minutes.")

    processor = AutoProcessor.from_pretrained(hf_model_id)
    model = MusicgenForConditionalGeneration.from_pretrained(hf_model_id)
    model.to(device)

    # Compute token budget from desired duration and model frame rate
    sampling_rate = model.config.audio_encoder.sampling_rate  # 32000 Hz
    frame_rate = model.config.frame_rate  # tokens per second
    max_new_tokens = int(duration * frame_rate)

    inputs = processor(text=[prompt], padding=True, return_tensors="pt").to(device)
    with torch.no_grad():
        audio_values = model.generate(**inputs, max_new_tokens=max_new_tokens)

    # audio_values: (batch, channels, samples)
    audio = audio_values[0].cpu().float()
    return audio, sampling_rate


def save_wav(audio: "torch.Tensor", path: Path, sample_rate: int = 32000) -> None:
    import scipy.io.wavfile as wav_io
    import numpy as np
    data = audio.numpy()
    if data.ndim == 2:
        data = data.T  # (samples, channels)
    data_int16 = (data * 32767).clip(-32768, 32767).astype(np.int16)
    wav_io.write(str(path), sample_rate, data_int16)


def mix_music_under_video(
    video_path: Path,
    music_path: Path,
    output_path: Path,
    music_volume_lufs: float,
) -> None:
    """
    Mix generated music under the video's existing audio at the target loudness.
    The voice track remains primary; music is ducked to music_volume_lufs.
    Uses ffmpeg loudnorm + amix.
    """
    # Get video duration to know if music needs to loop
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True, text=True,
    )
    try:
        vid_duration = float(probe.stdout.strip())
    except ValueError:
        vid_duration = 0.0

    # Build ffmpeg filter: normalise music loudness, then mix
    filter_complex = (
        f"[1:a]loudnorm=I={music_volume_lufs}:LRA=7:TP=-1[music_norm];"
        "[0:a][music_norm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-stream_loop", "-1", "-i", str(music_path),  # loop music if shorter
        "-filter_complex", filter_complex,
        "-map", "0:v:0",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg mix failed")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process(config_path: Path) -> None:
    cfg = validate_config(load_config(config_path))

    output_dir = Path(cfg.get("output_dir", "./output"))
    prompt = cfg["prompt"]
    duration = float(cfg.get("duration", 30))
    model_name = cfg.get("model", "small")
    device = resolve_device(cfg)
    music_volume_lufs = float(cfg.get("music_volume_lufs", -20))
    video = cfg.get("video")

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f'Generating {duration}s of music: "{prompt}"')
    audio, sample_rate = generate_music(prompt, duration, model_name, device)

    if video:
        video_path = Path(video)
        if not video_path.exists():
            print(f"Error: video file not found: {video_path}", file=sys.stderr)
            sys.exit(1)
        with tempfile.TemporaryDirectory(prefix="clawbeat_") as tmp_str:
            tmp_music = Path(tmp_str) / "music.wav"
            save_wav(audio, tmp_music, sample_rate)
            out_path = output_dir / video_path.name
            print(f"Mixing music under video at {music_volume_lufs} LUFS…")
            mix_music_under_video(video_path, tmp_music, out_path, music_volume_lufs)
        print(f"→ {out_path}")
    else:
        out_path = output_dir / "music.wav"
        save_wav(audio, out_path, sample_rate)
        print(f"→ {out_path}")

    print()
    print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="clawbeat — brand music generation")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--prompt", help="Override prompt")
    parser.add_argument("--duration", type=float, help="Override duration (seconds)")
    parser.add_argument("--model", choices=list(VALID_MODELS), help="Override model")
    parser.add_argument("--device", choices=list(VALID_DEVICES), help="Override device")
    parser.add_argument("--video", help="Override video (mix music under this file)")
    parser.add_argument(
        "--music-volume-lufs", type=float, help="Override music_volume_lufs (negative number)"
    )
    parser.add_argument("--output", help="Override output_dir")
    args = parser.parse_args()

    cfg = validate_config(load_config(Path(args.config)))

    if args.prompt:
        cfg["prompt"] = args.prompt
    if args.duration is not None:
        cfg["duration"] = args.duration
    if args.model:
        cfg["model"] = args.model
    if args.device:
        cfg["device"] = args.device
    if args.video:
        cfg["video"] = args.video
    if args.music_volume_lufs is not None:
        cfg["music_volume_lufs"] = args.music_volume_lufs
    if args.output:
        cfg["output_dir"] = args.output

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
