#!/usr/bin/env python3
"""
Audio transcription skill using HuggingFace ASR models.
Extracts audio from video and transcribes using transformers library.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import ffmpeg
import librosa

import torch
from transformers import pipeline


def load_config(config_path: str) -> dict:
    """Load configuration from JSON file."""
    with open(config_path, "r") as f:
        return json.load(f)


def extract_audio(video_path: str, output_path: str, sample_rate: int = 16000) -> str:
    """Extract audio from video file using ffmpeg-python."""
    (
        ffmpeg.input(video_path)
        .output(
            output_path, acodec="pcm_s16le", ac=1, ar=str(sample_rate), **{"y": None}
        )
        .run(capture_stdout=True, capture_stderr=True, quiet=True)
    )
    return output_path


def get_cache_dir() -> str:
    """Get HuggingFace cache directory from environment or default."""
    return os.environ.get(
        "HF_HOME",
        os.environ.get(
            "HUGGINGFACE_HUB_CACHE", os.path.expanduser("~/.cache/huggingface")
        ),
    )


def transcribe_audio(
    audio_path: str, model_id: str, device: str, language: str
) -> dict | list:
    # Load audio
    audio, sr = librosa.load(audio_path, sr=16000)

    # Determine dtype
    dtype = torch.float16 if device == "cuda" else torch.float32

    pipe = pipeline(
        "automatic-speech-recognition",
        model=model_id,
        dtype=dtype,
        device=device,
    )

    # Transcribe with timestamps
    result = pipe(
        audio,
        chunk_length_s=30,
        return_timestamps=True,
        generate_kwargs={"language": language} if language else {},
    )

    return result


def format_output(result: dict, file_name: str, model_id: str) -> dict:
    """Format transcription result into standard JSON output."""
    duration: float = result.get("duration", 0)
    segments: list[dict] = []

    if "chunks" in result and isinstance(result["chunks"], list):
        for chunk in result["chunks"]:
            start: float = chunk.get("chunk_start", 0)
            end: float = chunk.get("chunk_end", start)
            text: str = chunk.get("text", "")
            if text.strip():
                segments.append(
                    {
                        "start": round(start, 2),
                        "end": round(end, 2),
                        "text": text.strip(),
                    }
                )
    elif "text" in result:
        # Fallback: single segment for whole file
        segments.append(
            {
                "start": 0.0,
                "end": round(duration, 2),
                "text": str(result["text"]).strip(),
            }
        )

    return {
        "file": file_name,
        "duration": round(duration, 2),
        "language": result.get("language", "en"),
        "model": model_id,
        "segments": segments,
    }


def process_file(
    file_path: str, output_dir: str, model_id: str, device: str, language: str
) -> dict:
    """Process a single input file and return transcription result."""
    file_name = os.path.basename(file_path)
    file_ext = os.path.splitext(file_name)[1].lower()

    # Audio extraction
    if file_ext in [".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"]:
        audio_path = os.path.join(
            output_dir, f"{os.path.splitext(file_name)[0]}_audio.wav"
        )
        extract_audio(file_path, audio_path)
    else:
        audio_path = file_path

    # Transcribe using pipeline (handles model loading automatically)
    result = transcribe_audio(audio_path, model_id, device, language)

    # Format output
    output = format_output(result, file_name, model_id)  # type: ignore

    # Write to file
    output_name = os.path.splitext(file_name)[0] + "_transcription.json"
    output_path = os.path.join(output_dir, output_name)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Output written to: {output_path}")
    return output


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio from video/audio files"
    )
    parser.add_argument("--config", type=str, help="Path to config JSON file")
    parser.add_argument(
        "--input_dir", type=str, default="./input", help="Input directory"
    )
    parser.add_argument(
        "--output_dir", type=str, default="./output", help="Output directory"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="ibm-granite/granite-4.0-1b-speech",
        help="HuggingFace model ID",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="Inference device",
    )
    parser.add_argument(
        "--language", type=str, default="en", help="Language code (ISO 639-1)"
    )
    parser.add_argument("--file", type=str, help="Single file to process")

    args = parser.parse_args()

    # Load config if provided
    if args.config:
        config = load_config(args.config)
        args.input_dir = config.get("input_dir", "./input")
        args.output_dir = config.get("output_dir", "./output")
        args.model = config.get("model", "ibm-granite/granite-4.0-1b-speech")
        args.device = config.get("device", "auto")
        args.language = config.get("language", "en")

    # Convert to absolute paths (for test compatibility)
    args.input_dir = os.path.abspath(args.input_dir)
    args.output_dir = os.path.abspath(args.output_dir)

    # Create output directory if needed
    os.makedirs(args.output_dir, exist_ok=True)

    # Process file(s)
    if args.file:
        files = [args.file]
    else:
        # Find all audio/video files in input_dir
        extensions = [
            "*.mp4",
            "*.mov",
            "*.avi",
            "*.mkv",
            "*.m4v",
            "*.webm",
            "*.mp3",
            "*.wav",
            "*.aac",
            "*.flac",
        ]
        files = []
        for ext in extensions:
            files.extend(Path(args.input_dir).glob(ext))
        files = list(files)

    if not files:
        print(f"No input files found in {args.input_dir}")
        sys.exit(1)

    # Process each file
    for file_path in files:
        print(f"Processing: {file_path}")
        try:
            result = process_file(
                str(file_path), args.output_dir, args.model, args.device, args.language
            )
            print(
                f"  Duration: {result['duration']}s, Segments: {len(result['segments'])}"
            )
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)

    print("Transcription complete.")


if __name__ == "__main__":
    main()
