"""
enhance.py — Pre-process videos for Instagram before captioning.

Applies sharpening + colour grading via ffmpeg-python, then normalises
audio to -14 LUFS (EBU R128) via ffmpeg-normalize.
"""

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

PRESETS: dict[str, dict] = {
    "natural": {
        "unsharp": (3, 3, 0.8),
        "eq": {"brightness": 0.02, "contrast": 1.05, "saturation": 1.1},
        "colorbalance": None,
    },
    "cinematic": {
        # Instagram-ready: sharp, vibrant, warm
        "unsharp": (5, 5, 2.0),
        "eq": {"brightness": 0.02, "contrast": 1.2, "saturation": 1.35},
        # Boost reds/suppress blues in shadows + midtones for warmth
        "colorbalance": {"rs": 0.15, "gs": 0.03, "bs": -0.18,
                         "rm": 0.10, "gm": 0.02, "bm": -0.12},
    },
    "vivid": {
        "unsharp": (5, 5, 1.5),
        "eq": {"brightness": 0.05, "contrast": 1.2, "saturation": 1.4},
        "colorbalance": None,
    },
}


def enhance_video(input_path: Path, output_path: Path, preset_name: str) -> bool:
    """
    Enhance a video using a named preset.

    Steps:
      1. Apply unsharp + eq filters (ffmpeg-python) → temp file
      2. Normalise audio to -14 LUFS (ffmpeg-normalize) → output_path
      3. Clean up temp file

    Returns True on success, False on failure.
    """
    if preset_name not in PRESETS:
        raise ValueError(
            f"Unknown preset '{preset_name}'. Available: {', '.join(PRESETS)}"
        )

    preset = PRESETS[preset_name]
    unsharp = preset["unsharp"]
    eq = preset["eq"]
    colorbalance = preset.get("colorbalance")

    tmp_path = input_path.parent / (input_path.stem + f".{preset_name}_filtered.mp4")

    try:
        _apply_filters(input_path, tmp_path, unsharp, eq, colorbalance)
        _normalise_audio(tmp_path, output_path)
        return True
    except Exception as exc:
        log.error("Enhancement failed for %s: %s", input_path.name, exc, exc_info=True)
        return False
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _apply_filters(
    input_path: Path,
    output_path: Path,
    unsharp: tuple,
    eq: dict,
    colorbalance: dict | None = None,
) -> None:
    """Apply unsharp mask, eq colour grading, and optional warmth via ffmpeg-python."""
    import ffmpeg  # type: ignore

    luma_x, luma_y, luma_amount = unsharp

    stream = (
        ffmpeg
        .input(str(input_path))
        .video
        .filter("unsharp", luma_msize_x=luma_x, luma_msize_y=luma_y, luma_amount=luma_amount)
        .filter(
            "eq",
            brightness=eq["brightness"],
            contrast=eq["contrast"],
            saturation=eq["saturation"],
        )
    )

    if colorbalance is not None:
        stream = stream.filter("colorbalance", **colorbalance)

    audio = ffmpeg.input(str(input_path)).audio

    (
        ffmpeg
        .output(stream, audio, str(output_path), acodec="copy")
        .overwrite_output()
        .run(quiet=True)
    )
    log.info("Filters applied: %s → %s", input_path.name, output_path.name)


def _normalise_audio(input_path: Path, output_path: Path) -> None:
    """Normalise audio to -14 LUFS EBU R128, true peak -1 dBTP."""
    from ffmpeg_normalize import FFmpegNormalize  # type: ignore

    normalizer = FFmpegNormalize(
        normalization_type="ebu",
        target_level=-14.0,
        true_peak=-1.0,
        loudness_range_target=7.0,
        audio_codec="aac",
        video_disable=False,
        output_format="mp4",
    )
    normalizer.add_media_file(str(input_path), str(output_path))
    normalizer.run_normalization()
    log.info("Audio normalised: %s → %s", input_path.name, output_path.name)
