#!/usr/bin/env python3
"""
Caption Service: Batch-process videos from INPUT_DIR, add captions, save to OUTPUT_DIR.

Usage:
    python caption_service.py [--input DIR] [--output DIR] [--template NAME] [--css FILE]
                               [--preset PRESET] [--watch]

Environment variables:
    INPUT_DIR     - Directory to read videos from  (default: ./input)
    OUTPUT_DIR    - Directory to write videos to   (default: ./output)
    CAPS_TEMPLATE - pycaps template name           (default: minimalist)
    CAPS_CSS      - Path to extra CSS file         (default: none)
    VIDEO_PRESET  - Enhancement preset name        (default: none)
"""

import argparse
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def process_video(
    input_path: Path,
    output_path: Path,
    template: str,
    css: Path | None = None,
    preset: str | None = None,
) -> bool:
    """Optionally enhance a video then add captions. Returns True on success."""
    tmp_dir: str | None = None

    try:
        pycaps_input = input_path

        if preset is not None:
            from enhance import enhance_video  # type: ignore

            tmp_dir = tempfile.mkdtemp(prefix="pycaps_enhance_")
            enhanced_path = Path(tmp_dir) / input_path.name
            log.info("Enhancing with preset '%s': %s", preset, input_path.name)
            if not enhance_video(input_path, enhanced_path, preset):
                log.error("Enhancement failed for %s", input_path.name)
                return False
            pycaps_input = enhanced_path

        return _run_pycaps(pycaps_input, output_path, template, css)

    except Exception as exc:
        log.error("Failed to process %s: %s", input_path.name, exc, exc_info=True)
        return False
    finally:
        if tmp_dir is not None:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _run_pycaps(input_path: Path, output_path: Path, template: str, css: Path | None) -> bool:
    """Add captions to a single video using pycaps. Returns True on success."""
    try:
        from pycaps import TemplateLoader  # type: ignore

        log.info("Captioning: %s → %s", input_path.name, output_path)

        builder = (
            TemplateLoader(template)
            .with_input_video(str(input_path))
            .load(False)
        )

        if css is not None:
            log.info("Applying custom CSS: %s", css)
            builder = builder.add_css(str(css))

        # Override the output path so the result lands in our output dir.
        # CapsPipelineBuilder exposes with_output_video; check if available.
        if hasattr(builder, "with_output_video"):
            builder = builder.with_output_video(str(output_path))

        pipeline = builder.build()

        # Some pycaps versions accept output_path as run() kwarg.
        run_kwargs: dict = {}
        import inspect
        sig = inspect.signature(pipeline.run)
        if "output_path" in sig.parameters:
            run_kwargs["output_path"] = str(output_path)

        pipeline.run(**run_kwargs)

        # pycaps may write the result next to the input; move it if needed.
        if not output_path.exists():
            default_out = input_path.with_stem(input_path.stem + "_captioned")
            if default_out.exists():
                default_out.rename(output_path)
            else:
                # Try common pycaps default: same name, same dir as input
                same_dir_out = input_path.parent / output_path.name
                if same_dir_out.exists() and same_dir_out != output_path:
                    same_dir_out.rename(output_path)
                else:
                    log.warning("Output file not found at expected location.")
                    return False

        log.info("Done: %s", output_path)
        return True

    except ImportError:
        log.error("pycaps is not installed. Run: pip install 'git+https://github.com/francozanardi/pycaps.git#egg=pycaps[all]'")
        return False
    except Exception as exc:
        log.error("Failed to caption %s: %s", input_path.name, exc, exc_info=True)
        return False


def collect_unprocessed(input_dir: Path, output_dir: Path) -> list[Path]:
    """Return video files in input_dir that don't yet have a match in output_dir."""
    pending = []
    for p in sorted(input_dir.iterdir()):
        if p.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        expected_output = output_dir / p.name
        if not expected_output.exists():
            pending.append(p)
    return pending


def run_batch(
    input_dir: Path,
    output_dir: Path,
    template: str,
    css: Path | None = None,
    preset: str | None = None,
) -> tuple[int, int]:
    """Process all pending videos. Returns (success_count, failure_count)."""
    pending = collect_unprocessed(input_dir, output_dir)
    if not pending:
        log.info("No new videos to process in %s", input_dir)
        return 0, 0

    log.info("Found %d video(s) to process.", len(pending))
    success, failure = 0, 0
    for video in pending:
        output_path = output_dir / video.name
        if process_video(video, output_path, template, css, preset):
            success += 1
        else:
            failure += 1

    return success, failure


def watch_loop(
    input_dir: Path,
    output_dir: Path,
    template: str,
    css: Path | None,
    preset: str | None = None,
    interval: int = 10,
) -> None:
    """Poll input_dir every `interval` seconds and process new videos."""
    log.info("Watching %s every %ds. Press Ctrl+C to stop.", input_dir, interval)
    try:
        while True:
            run_batch(input_dir, output_dir, template, css, preset)
            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("Watch mode stopped.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch caption videos with pycaps")
    parser.add_argument(
        "--input",
        default=os.environ.get("INPUT_DIR", "input"),
        help="Input directory containing source videos (default: ./input)",
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("OUTPUT_DIR", "output"),
        help="Output directory for captioned videos (default: ./output)",
    )
    parser.add_argument(
        "--template",
        default=os.environ.get("CAPS_TEMPLATE", "minimalist"),
        help="pycaps template name (default: minimalist)",
    )
    parser.add_argument(
        "--css",
        default=os.environ.get("CAPS_CSS"),
        help="Path to an extra CSS file to overlay on the template",
    )
    parser.add_argument(
        "--preset",
        default=os.environ.get("VIDEO_PRESET"),
        help="Enhancement preset: natural | cinematic | vivid (default: none)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Keep running and watch for new videos",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Polling interval in seconds when --watch is set (default: 10)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_dir = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()

    if not input_dir.exists():
        log.error("Input directory does not exist: %s", input_dir)
        sys.exit(1)

    css_path: Path | None = None
    if args.css:
        css_path = Path(args.css).expanduser().resolve()
        if not css_path.exists():
            log.error("CSS file does not exist: %s", css_path)
            sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Input:    %s", input_dir)
    log.info("Output:   %s", output_dir)
    log.info("Template: %s", args.template)
    if css_path:
        log.info("CSS:      %s", css_path)
    if args.preset:
        log.info("Preset:   %s", args.preset)

    if args.watch:
        watch_loop(input_dir, output_dir, args.template, css_path, args.preset, args.interval)
    else:
        success, failure = run_batch(input_dir, output_dir, args.template, css_path, args.preset)
        log.info("Finished — success: %d, failed: %d", success, failure)
        if failure:
            sys.exit(1)


if __name__ == "__main__":
    main()
