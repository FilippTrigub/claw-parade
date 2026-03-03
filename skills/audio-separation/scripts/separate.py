#!/usr/bin/env python3
"""
separate.py — clawsep: separate audio stems from video or audio files via Demucs.

For video inputs: extracts audio, separates stems, then remuxes the chosen
stem back into the video. The original video track is kept unchanged.
For audio inputs: writes the separated stems as WAV files.

Stems:
  vocals     — isolated voice track (removes music)
  no_vocals  — instrumental / music without vocals
  drums      — drum track only
  bass       — bass track only
  other      — everything that isn't drums, bass, or vocals

Device:
  "auto" / "cuda" → GPU
  "cpu"           → CPU (~3–5× realtime, fully functional)

Usage:
  python scripts/separate.py [--config config.json]
  python scripts/separate.py --input ./input --output ./output --stem vocals
  python scripts/separate.py --input ./input --output ./output --device cpu
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"}
VALID_STEMS = {"vocals", "no_vocals", "drums", "bass", "other"}
VALID_DEVICES = {"auto", "cpu", "cuda"}
VALID_MODELS = {"htdemucs", "htdemucs_ft", "htdemucs_6s", "mdx_extra", "mdx_extra_q"}


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
    stem = cfg.get("stem", "vocals")
    if stem not in VALID_STEMS:
        errors.append(f"'stem' must be one of: {', '.join(sorted(VALID_STEMS))}")
    model = cfg.get("model", "htdemucs")
    if model not in VALID_MODELS:
        errors.append(f"'model' must be one of: {', '.join(sorted(VALID_MODELS))}")
    device = cfg.get("device", "auto")
    if device not in VALID_DEVICES:
        errors.append(f"'device' must be one of: {', '.join(VALID_DEVICES)}")
    bitrate = cfg.get("mp3_bitrate", 320)
    if not isinstance(bitrate, int) or bitrate <= 0:
        errors.append("'mp3_bitrate' must be a positive integer")
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
# Separation
# ---------------------------------------------------------------------------

def _demucs_two_stem(stem: str) -> str:
    """Map our stem name to Demucs --two-stems value."""
    if stem == "no_vocals":
        return "vocals"   # Demucs splits into vocals / no_vocals
    return stem


def separate_audio(
    audio_path: Path,
    out_dir: Path,
    stem: str,
    model: str,
    device: str,
) -> Path:
    """
    Run Demucs on audio_path. Returns path to the requested stem WAV.
    Demucs writes: out_dir/<model>/<audio_stem>/<stem>.wav
    """
    two_stems = _demucs_two_stem(stem)
    cmd = [
        sys.executable, "-m", "demucs",
        "--two-stems", two_stems,
        "--name", model,
        "--device", device,
        "--out", str(out_dir),
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "demucs failed")

    # Locate the output file
    stem_wav = out_dir / model / audio_path.stem / f"{stem}.wav"
    if not stem_wav.exists():
        # Demucs may use slightly different folder names — find it
        matches = list(out_dir.rglob(f"{stem}.wav"))
        if not matches:
            raise FileNotFoundError(
                f"Could not find separated stem '{stem}.wav' in {out_dir}"
            )
        stem_wav = matches[0]

    return stem_wav


def remux_audio_into_video(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
) -> None:
    """Replace the audio track in video_path with audio_path, write to output_path."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg remux failed")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_file(
    input_path: Path,
    output_dir: Path,
    stem: str,
    model: str,
    device: str,
) -> None:
    is_video = input_path.suffix.lower() in VIDEO_EXTENSIONS
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="clawsep_") as tmp_str:
        tmp = Path(tmp_str)

        if is_video:
            # Extract audio from video first
            raw_audio = tmp / (input_path.stem + "_audio.wav")
            cmd = [
                "ffmpeg", "-y", "-i", str(input_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "44100",
                str(raw_audio),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "ffmpeg audio extract failed")
            source_audio = raw_audio
        else:
            source_audio = input_path

        # Separate
        stem_wav = separate_audio(source_audio, tmp / "demucs_out", stem, model, device)

        if is_video:
            out_path = output_dir / input_path.name
            remux_audio_into_video(input_path, stem_wav, out_path)
        else:
            out_path = output_dir / (input_path.stem + f"_{stem}.wav")
            shutil.copy2(stem_wav, out_path)

    print(f"  → {out_path}")


def process(config_path: Path) -> None:
    cfg = validate_config(load_config(config_path))

    input_dir = Path(cfg.get("input_dir", "./input"))
    output_dir = Path(cfg.get("output_dir", "./output"))
    stem = cfg.get("stem", "vocals")
    model = cfg.get("model", "htdemucs")
    device = resolve_device(cfg)

    if not input_dir.exists():
        print(f"Error: input_dir does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)

    all_ext = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS
    files = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in all_ext
    )
    if not files:
        print(f"No video or audio files found in {input_dir}")
        return

    print(f"Processing {len(files)} file(s): stem={stem}, model={model}, device={device}")
    if device == "cpu":
        print("  Note: CPU mode is ~3–5× realtime — may take a few minutes per file.")
    print()

    succeeded, failed = 0, []

    for file_path in files:
        print(f"[{file_path.name}]")
        try:
            process_file(file_path, output_dir, stem, model, device)
            succeeded += 1
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            failed.append(file_path.name)

    print()
    print(f"Done: {succeeded}/{len(files)} succeeded", end="")
    if failed:
        print(f", {len(failed)} failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="clawsep — audio source separation")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--input", help="Override input_dir")
    parser.add_argument("--output", help="Override output_dir")
    parser.add_argument("--stem", choices=list(VALID_STEMS), help="Override stem")
    parser.add_argument("--model", choices=list(VALID_MODELS), help="Override Demucs model")
    parser.add_argument("--device", choices=list(VALID_DEVICES), help="Override device")
    args = parser.parse_args()

    cfg = validate_config(load_config(Path(args.config)))

    if args.input:
        cfg["input_dir"] = args.input
    if args.output:
        cfg["output_dir"] = args.output
    if args.stem:
        cfg["stem"] = args.stem
    if args.model:
        cfg["model"] = args.model
    if args.device:
        cfg["device"] = args.device

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
