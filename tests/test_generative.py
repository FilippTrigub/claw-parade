"""
test_generative.py — Tests for generative AI skills.

Tools under test:
  clawanimate  (image-to-video)      — LTX-Video image → video clip
  clawvace     (video-editing)       — Wan2.1-VACE video inpainting
  clawportrait (portrait-animation)  — LivePortrait talking-head animation

All require CUDA GPU with significant VRAM. Tests are auto-skipped when GPU
is unavailable or VRAM is insufficient.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import (
    requires_gpu,
    run_skill,
    uv_sync,
    video_info,
    CLIP_WIDTH,
    CLIP_HEIGHT,
)


# ===========================================================================
# clawanimate — Image to Video (LTX-Video)
# ===========================================================================

@requires_gpu(min_gb=8.0)
class TestClawAnimate:
    """
    Expected behaviour:
      - Produces one MP4 per input image
      - Output is a valid video with at least 9 frames
      - Output has the requested width × height (or default 768×512)
      - Exits 0 on success

    Note: LTX-Video weights (~8 GB) downloaded on first run.
    """

    SKILL = "image-to-video"

    @pytest.fixture(autouse=True, scope="class")
    def setup_venv(self):
        uv_sync(self.SKILL)

    @pytest.fixture
    def workdir(self, test_frames, tmp_path):
        inp = tmp_path / "input"
        inp.mkdir()
        shutil.copy(test_frames[0], inp)
        out = tmp_path / "output"
        out.mkdir()
        return inp, out

    def test_produces_video_per_image(self, workdir):
        """Output dir contains one MP4 for each input image."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "img2vid.py",
            ["--input", str(inp), "--output", str(out),
             "--prompt", "gentle camera drift, soft morning light",
             "--num-frames", "25",  # minimal for speed
             "--width", "512", "--height", "512",
             "--steps", "10"],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        out_files = list(out.glob("*.mp4"))
        assert len(out_files) == 1

    def test_output_is_valid_video(self, workdir):
        """Output MP4 has a playable video stream with ≥9 frames."""
        inp, out = workdir
        run_skill(
            self.SKILL, "img2vid.py",
            ["--input", str(inp), "--output", str(out),
             "--prompt", "slow zoom in",
             "--num-frames", "25",
             "--width", "512", "--height", "512",
             "--steps", "10"],
        )
        info = video_info(next(out.glob("*.mp4")))
        assert info["has_video"]
        assert info["nb_frames"] >= 9

    def test_output_respects_requested_resolution(self, workdir):
        """Output video has the requested dimensions."""
        inp, out = workdir
        run_skill(
            self.SKILL, "img2vid.py",
            ["--input", str(inp), "--output", str(out),
             "--prompt", "subtle motion",
             "--num-frames", "9",
             "--width", "512", "--height", "512",
             "--steps", "5"],
        )
        info = video_info(next(out.glob("*.mp4")))
        assert info["width"] == 512
        assert info["height"] == 512

    def test_invalid_num_frames_rejected(self, workdir):
        """num_frames < 9 should be rejected before inference."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "img2vid.py",
            ["--input", str(inp), "--output", str(out),
             "--prompt", "test",
             "--num-frames", "3"],
        )
        assert result.returncode != 0
        err = (result.stderr + result.stdout).lower()
        assert "num_frames" in err or "frames" in err


# ===========================================================================
# clawvace — Video Inpainting (Wan2.1-VACE)
# ===========================================================================

@requires_gpu(min_gb=8.0)
class TestClawVace:
    """
    Expected behaviour:
      - Produces one MP4 per input video
      - Output has same dimensions as input
      - Output duration is within ±0.5 s of input
      - Original audio is preserved
      - Exits 0 on success

    Note: Wan2.1-VACE-1.3B weights (~3 GB) downloaded on first run.
    """

    SKILL = "video-editing"

    @pytest.fixture(autouse=True, scope="class")
    def setup_venv(self):
        uv_sync(self.SKILL)

    @pytest.fixture
    def workdir(self, test_clip, tmp_path):
        inp = tmp_path / "input"
        inp.mkdir()
        shutil.copy(test_clip, inp)
        out = tmp_path / "output"
        out.mkdir()
        return inp, out

    def test_background_mode_produces_output(self, workdir):
        """Background inpainting produces a valid MP4."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "vace.py",
            ["--input", str(inp), "--output", str(out),
             "--mask", "background",
             "--prompt", "modern minimalist studio",
             "--steps", "10"],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        out_files = list(out.glob("*.mp4"))
        assert len(out_files) == 1

    def test_region_mode_requires_mask_region(self, workdir):
        """mask=region without mask_region should fail validation."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "vace.py",
            ["--input", str(inp), "--output", str(out),
             "--mask", "region",
             "--prompt", "clear blue sky"],
        )
        assert result.returncode != 0
        err = (result.stderr + result.stdout).lower()
        assert "mask_region" in err or "region" in err

    def test_region_mode_with_mask_produces_output(self, workdir):
        """Region mode with a valid mask_region produces output."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "vace.py",
            ["--input", str(inp), "--output", str(out),
             "--mask", "region",
             "--mask-region", "0.0,0.0,1.0,0.3",
             "--prompt", "clear blue sky",
             "--steps", "10"],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert list(out.glob("*.mp4"))

    def test_output_preserves_dimensions(self, workdir):
        """Inpainting does not change video resolution."""
        inp, out = workdir
        run_skill(
            self.SKILL, "vace.py",
            ["--input", str(inp), "--output", str(out),
             "--mask", "background",
             "--prompt", "cosy home office",
             "--steps", "5"],
        )
        info = video_info(next(out.glob("*.mp4")))
        assert info["width"] == CLIP_WIDTH
        assert info["height"] == CLIP_HEIGHT

    def test_output_preserves_duration(self, workdir):
        """Inpainting preserves video duration (±0.5 s)."""
        inp, out = workdir
        run_skill(
            self.SKILL, "vace.py",
            ["--input", str(inp), "--output", str(out),
             "--mask", "background",
             "--prompt", "studio backdrop",
             "--steps", "5"],
        )
        info = video_info(next(out.glob("*.mp4")))
        assert abs(info["duration"] - 5.0) < 0.5

    def test_audio_preserved(self, workdir):
        """Output video retains the original audio track."""
        inp, out = workdir
        run_skill(
            self.SKILL, "vace.py",
            ["--input", str(inp), "--output", str(out),
             "--mask", "background",
             "--prompt", "professional office",
             "--steps", "5"],
        )
        info = video_info(next(out.glob("*.mp4")))
        assert info["has_audio"]

    def test_invalid_strength_rejected(self, workdir):
        """Strength > 1.0 should be rejected by config validation."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "vace.py",
            ["--input", str(inp), "--output", str(out),
             "--prompt", "test", "--strength", "1.5"],
        )
        assert result.returncode != 0


# ===========================================================================
# clawportrait — Portrait Animation (LivePortrait)
# ===========================================================================

@requires_gpu(min_gb=4.0)
class TestClawPortrait:
    """
    Expected behaviour:
      - Produces one MP4 per portrait × driver combination
      - Output is a valid video
      - Output duration ≈ driver video duration (±0.5 s)
      - Batch mode: one output per driver in the driver directory
      - Exits 0 on success

    Note: LivePortrait weights (~1.5 GB) downloaded on first run.
    """

    SKILL = "portrait-animation"

    @pytest.fixture(autouse=True, scope="class")
    def setup_venv(self):
        uv_sync(self.SKILL)

    def test_single_driver_produces_output(self, portrait_image, test_clip, tmp_path):
        """One portrait + one driver → one output MP4."""
        out = tmp_path / "output"
        out.mkdir()
        result = run_skill(
            self.SKILL, "portrait.py",
            ["--portrait", str(portrait_image),
             "--driver", str(test_clip),
             "--output", str(out)],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        out_files = list(out.glob("*.mp4"))
        assert len(out_files) == 1

    def test_output_is_valid_video(self, portrait_image, test_clip, tmp_path):
        """Output MP4 has a playable video stream."""
        out = tmp_path / "output"
        out.mkdir()
        run_skill(
            self.SKILL, "portrait.py",
            ["--portrait", str(portrait_image),
             "--driver", str(test_clip),
             "--output", str(out)],
        )
        info = video_info(next(out.glob("*.mp4")))
        assert info["has_video"]
        assert info["nb_frames"] > 0

    def test_output_duration_matches_driver(self, portrait_image, test_clip, tmp_path):
        """Animated video duration matches the driver video (±0.5 s)."""
        out = tmp_path / "output"
        out.mkdir()
        run_skill(
            self.SKILL, "portrait.py",
            ["--portrait", str(portrait_image),
             "--driver", str(test_clip),
             "--output", str(out)],
        )
        info = video_info(next(out.glob("*.mp4")))
        assert abs(info["duration"] - 5.0) < 0.5

    def test_output_filename_pattern(self, portrait_image, test_clip, tmp_path):
        """Output file is named <portrait_stem>--<driver_stem>.mp4."""
        out = tmp_path / "output"
        out.mkdir()
        run_skill(
            self.SKILL, "portrait.py",
            ["--portrait", str(portrait_image),
             "--driver", str(test_clip),
             "--output", str(out)],
        )
        portrait_stem = portrait_image.stem
        driver_stem = test_clip.stem
        expected_name = f"{portrait_stem}--{driver_stem}.mp4"
        assert (out / expected_name).exists(), (
            f"Expected output file: {expected_name}; "
            f"found: {[f.name for f in out.glob('*.mp4')]}"
        )

    def test_batch_mode_processes_all_drivers(self, portrait_image, test_clip, tmp_path):
        """Batch mode (driver = directory) creates one output per driver."""
        driver_dir = tmp_path / "drivers"
        driver_dir.mkdir()
        # Copy the same clip twice to simulate multiple drivers
        shutil.copy(test_clip, driver_dir / "driver_a.mp4")
        shutil.copy(test_clip, driver_dir / "driver_b.mp4")

        out = tmp_path / "output"
        out.mkdir()
        result = run_skill(
            self.SKILL, "portrait.py",
            ["--portrait", str(portrait_image),
             "--driver", str(driver_dir),
             "--output", str(out)],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        out_files = list(out.glob("*.mp4"))
        assert len(out_files) == 2

    def test_missing_portrait_exits_cleanly(self, test_clip, tmp_path):
        """Non-existent portrait path gives a clear error, not a traceback."""
        out = tmp_path / "output"
        out.mkdir()
        result = run_skill(
            self.SKILL, "portrait.py",
            ["--portrait", str(tmp_path / "nonexistent.jpg"),
             "--driver", str(test_clip),
             "--output", str(out)],
        )
        assert result.returncode != 0
        err = (result.stderr + result.stdout).lower()
        assert "not found" in err or "portrait" in err or "error" in err
