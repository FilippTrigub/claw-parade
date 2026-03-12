#!/usr/bin/env python3
"""
cutter.py — Cut, rearrange, and export video segments.

Usage:
    python scripts/cutter.py --config config.json
    python scripts/cutter.py --input ./input --output ./output --fps 30
"""

import argparse
import json
import sys
from pathlib import Path

from moviepy import VideoFileClip, concatenate_videoclips
from scenedetect import open_video, SceneManager
from scenedetect.detectors import AdaptiveDetector, ContentDetector, ThresholdDetector


def detect_scenes(
    video_path: Path,
    mode: str = "adaptive",
    min_scene_duration: float = 1.0,
    max_scene_duration: float = 10.0,
    threshold: float = 27.0,
    adaptive_threshold: float = 3.0,
    window_width: int = 2,
    min_scene_len: int = 15,
    min_content_val: float = 15.0,
) -> list[dict]:
    """
    Detect scene changes in video using PySceneDetect.

    Args:
        video_path: Path to video file
        mode: Detection mode (content, adaptive, threshold)
        min_scene_duration: Minimum scene duration in seconds
        max_scene_duration: Maximum scene duration in seconds
        threshold: Pixel diff threshold for ContentDetector (lower = more sensitive)
        adaptive_threshold: Ratio threshold for AdaptiveDetector (lower = more sensitive)
        window_width: Frames to average before/after (higher = smoother)
        min_scene_len: Minimum frames before a cut can be registered
        min_content_val: Minimum content change to register as new scene

    Returns:
        List of segment dicts with 'source', 'start', 'end'
    """
    video = open_video(str(video_path))
    scene_manager = SceneManager()

    # Create detector based on mode
    if mode == "adaptive":
        detector = AdaptiveDetector(
            adaptive_threshold=adaptive_threshold,
            min_scene_len=min_scene_len,
            window_width=window_width,
            min_content_val=min_content_val,
        )
    elif mode == "threshold":
        detector = ThresholdDetector(
            threshold=threshold,
            min_scene_len=min_scene_len,
        )
    else:  # content (default)
        detector = ContentDetector(
            threshold=threshold,
            min_scene_len=min_scene_len,
        )

    scene_manager.add_detector(detector)
    scene_manager.detect_scenes(video)

    scene_list = scene_manager.get_scene_list()

    if not scene_list:
        print(f"No scenes detected in {video_path}")
        return []

    # Get frame rate for converting frames to seconds
    frame_rate = video.frame_rate

    segments = []
    for scene in scene_list:
        start, end = scene
        start_s = start.get_seconds()
        end_s = end.get_seconds()
        duration = end_s - start_s

        if duration < min_scene_duration:
            print(
                f"Skipping short scene: {start_s:.2f}s -> {end_s:.2f}s "
                f"(duration {duration:.2f}s < {min_scene_duration}s)"
            )
            continue

        if duration > max_scene_duration:
            print(
                f"Skipping long scene: {start_s:.2f}s -> {end_s:.2f}s "
                f"(duration {duration:.2f}s > {max_scene_duration}s)"
            )
            continue

        segments.append(
            {
                "start": start_s,
                "end": end_s,
            }
        )

    return segments


def load_config(config_path: Path) -> dict:
    """Load and validate config from JSON file."""
    if not config_path.exists():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    auto_detect = config.get("auto_detect", {})
    has_auto_detect = auto_detect.get("enabled", False)

    if not has_auto_detect:
        if "segments" not in config or not config["segments"]:
            print(
                "Error: 'segments' is required when auto_detect is not enabled",
                file=sys.stderr,
            )
            sys.exit(1)

    return config


def cut_video(
    input_dir: Path,
    output_dir: Path,
    segments: list[dict],
    output_fps: int = 30,
) -> Path:
    """
    Cut video into segments, rearrange them, and concatenate.

    Args:
        input_dir: Directory containing source videos
        output_dir: Directory for output video
        segments: List of segment dicts with 'source', 'start', 'end'
        output_fps: Output frame rate

    Returns:
        Path to output video
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    clips: list[VideoFileClip] = []

    for i, seg in enumerate(segments):
        source = seg.get("source")
        start = seg.get("start", 0.0)
        end = seg.get("end")

        if not source:
            print(f"Error: segment {i} missing 'source'", file=sys.stderr)
            continue

        if end is None:
            print(f"Error: segment {i} missing 'end'", file=sys.stderr)
            continue

        source_path = input_dir / source
        if not source_path.exists():
            print(f"Error: source video not found: {source_path}", file=sys.stderr)
            continue

        try:
            clip = VideoFileClip(str(source_path))
            # Cut segment (moviepy v2 uses subclipped)
            subclip = clip.subclipped(start, end)
            clips.append(subclip)
            print(f"Added segment {i}: {source} [{start}s -> {end}s]")
        except Exception as e:
            print(f"Error processing segment {i}: {e}", file=sys.stderr)
            continue

    if not clips:
        print("Error: no valid clips to concatenate", file=sys.stderr)
        sys.exit(1)

    # Concatenate clips
    final_clip = concatenate_videoclips(clips, method="compose")

    # Set output FPS
    final_clip = final_clip.with_fps(output_fps)

    # Write output
    output_path = output_dir / "output.mp4"
    final_clip.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        fps=output_fps,
    )

    # Clean up clips
    for clip in clips:
        clip.close()
    final_clip.close()

    print(f"Output written to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Cut and rearrange video segments")
    parser.add_argument("--config", type=Path, help="Path to config JSON file")
    parser.add_argument(
        "--input", type=Path, default=Path("./input"), help="Input directory"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("./output"), help="Output directory"
    )
    parser.add_argument("--fps", type=int, default=30, help="Output FPS")

    args = parser.parse_args()

    if args.config:
        config = load_config(args.config)
        input_dir = Path(config.get("input_dir", args.input))
        output_dir = Path(config.get("output_dir", args.output))
        segments = config.get("segments", [])
        output_fps = config.get("output_fps", args.fps)
        auto_detect = config.get("auto_detect", {})
    else:
        input_dir = args.input
        output_dir = args.output
        segments = []
        output_fps = args.fps
        auto_detect = {}

    auto_detect_enabled = auto_detect.get("enabled", True)

    if auto_detect_enabled:
        # Always run auto-detect when enabled - ignore any pre-defined segments
        if "segments" not in config:
            print(
                "Error: 'segments' must include source video for auto-detect",
                file=sys.stderr,
            )
            sys.exit(1)

        segment_def = config["segments"][0]
        source_video = segment_def.get("source")
        if not source_video:
            print(
                "Error: segments must include 'source' for auto-detect",
                file=sys.stderr,
            )
            sys.exit(1)

        video_path = input_dir / source_video
        if not video_path.exists():
            print(f"Error: source video not found: {video_path}", file=sys.stderr)
            sys.exit(1)

        mode = auto_detect.get("mode", "adaptive")
        min_duration = auto_detect.get("min_scene_duration", 1.0)
        max_duration = auto_detect.get("max_scene_duration", 10.0)
        threshold = auto_detect.get("threshold", 27.0)
        adaptive_threshold = auto_detect.get("adaptive_threshold", 3.0)
        window_width = auto_detect.get("window_width", 2)
        min_scene_len = auto_detect.get("min_scene_len", 15)
        min_content_val = auto_detect.get("min_content_val", 15.0)

        print(f"Detecting scenes in {source_video} (mode: {mode})...")
        detected = detect_scenes(
            video_path,
            mode=mode,
            min_scene_duration=min_duration,
            max_scene_duration=max_duration,
            threshold=threshold,
            adaptive_threshold=adaptive_threshold,
            window_width=window_width,
            min_scene_len=min_scene_len,
            min_content_val=min_content_val,
        )

        segments = [
            {"source": source_video, "start": s["start"], "end": s["end"]}
            for s in detected
        ]
        print(f"Detected {len(segments)} scenes")

    if not segments:
        print(
            "Error: no segments specified. Use --config or provide segments.",
            file=sys.stderr,
        )
        sys.exit(1)

    output_path = cut_video(input_dir, output_dir, segments, output_fps)
    print(f"Done! Output: {output_path}")


if __name__ == "__main__":
    main()
