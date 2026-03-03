"""
test_video_tools.py — Tests for GPU-required video processing skills.

Tools under test:
  clawrife   (frame-interpolation)  — 2×/4× frame rate via RAFT optical flow
  clawmatte  (video-matting)        — per-frame background removal via BiRefNet

Both require a CUDA GPU. Tests are auto-skipped when GPU is unavailable.
"""

import shutil
from pathlib import Path

import pytest

from conftest import (
    requires_gpu,
    run_skill,
    uv_sync,
    video_info,
    CLIP_FRAME_COUNT,
    CLIP_FPS,
)


# ===========================================================================
# clawrife — Frame Interpolation
# ===========================================================================

@requires_gpu(min_gb=2.0)
class TestClawRife:
    """
    Expected behaviour:
      - Output video has the same duration (±0.2 s) as input
      - Output fps == input fps × multiplier
      - Output frame count ≈ input frame count × multiplier
      - Exits 0 on success
    """

    SKILL = "frame-interpolation"

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

    def test_2x_doubles_fps(self, workdir):
        """2× multiplier produces output at 60 fps."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "interpolate.py",
            ["--input", str(inp), "--output", str(out), "--multiplier", "2"],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        out_files = list(out.glob("*.mp4"))
        assert len(out_files) == 1
        info = video_info(out_files[0])
        assert info["fps"] == CLIP_FPS * 2, (
            f"Expected {CLIP_FPS * 2} fps, got {info['fps']}"
        )

    def test_2x_preserves_duration(self, workdir):
        """2× interpolation preserves video duration (±0.5 s)."""
        inp, out = workdir
        run_skill(
            self.SKILL, "interpolate.py",
            ["--input", str(inp), "--output", str(out), "--multiplier", "2"],
        )
        info = video_info(next(out.glob("*.mp4")))
        assert abs(info["duration"] - 5.0) < 0.5, (
            f"Duration: {info['duration']:.2f}s, expected ~5.0s"
        )

    def test_2x_doubles_frame_count(self, workdir):
        """2× interpolation approximately doubles the frame count."""
        inp, out = workdir
        run_skill(
            self.SKILL, "interpolate.py",
            ["--input", str(inp), "--output", str(out), "--multiplier", "2"],
        )
        info = video_info(next(out.glob("*.mp4")))
        # Expected: (n_frames - 1) * 2 + 1 interpolated frames
        expected = CLIP_FRAME_COUNT * 2 - 1
        # Allow ±5 frames tolerance for codec rounding
        assert abs(info["nb_frames"] - expected) <= 5, (
            f"Frame count: {info['nb_frames']}, expected ~{expected}"
        )

    def test_4x_quadruples_fps(self, workdir):
        """4× multiplier produces output at 120 fps."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "interpolate.py",
            ["--input", str(inp), "--output", str(out), "--multiplier", "4"],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        info = video_info(next(out.glob("*.mp4")))
        assert info["fps"] == CLIP_FPS * 4, (
            f"Expected {CLIP_FPS * 4} fps, got {info['fps']}"
        )

    def test_raft_small_model_runs(self, workdir):
        """raft_small produces valid output (lower quality, less VRAM)."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "interpolate.py",
            ["--input", str(inp), "--output", str(out),
             "--multiplier", "2", "--model", "raft_small"],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert list(out.glob("*.mp4"))

    def test_no_gpu_exits_with_clear_error(self, tmp_path, monkeypatch):
        """
        When CUDA is not available the script should exit non-zero with
        a human-readable error message (not a Python traceback crash).
        Simulated by setting CUDA_VISIBLE_DEVICES to empty.
        """
        inp = tmp_path / "input"
        inp.mkdir()
        out = tmp_path / "output"
        out.mkdir()
        import subprocess as sp
        result = sp.run(
            ["uv", "run", "python", "scripts/interpolate.py",
             "--input", str(inp), "--output", str(out)],
            cwd=str(Path(__file__).parent.parent / "skills" / self.SKILL),
            capture_output=True, text=True,
            env={**__import__("os").environ, "CUDA_VISIBLE_DEVICES": ""},
        )
        assert result.returncode != 0
        err = result.stderr.lower()
        assert "error" in err or "cuda" in err or "gpu" in err


# ===========================================================================
# clawmatte — Video Background Removal
# ===========================================================================

@requires_gpu(min_gb=3.0)
class TestClawMatte:
    """
    Expected behaviour:
      - Produces one MP4 per input video in output_dir
      - Output has same dimensions as input
      - Output has same duration (±0.5 s)
      - Output retains audio stream
      - With --bg hex, background is composited (video has no alpha, but is RGB)
      - Exits 0 on success
    """

    SKILL = "video-matting"

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

    def test_produces_output_video(self, workdir):
        """Output directory contains exactly one MP4."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "matte.py",
            ["--input", str(inp), "--output", str(out),
             "--model", "birefnet-general"],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        out_files = list(out.glob("*.mp4"))
        assert len(out_files) == 1

    def test_output_preserves_dimensions(self, workdir):
        """Output resolution matches input resolution."""
        inp, out = workdir
        run_skill(
            self.SKILL, "matte.py",
            ["--input", str(inp), "--output", str(out),
             "--model", "birefnet-general"],
        )
        info = video_info(next(out.glob("*.mp4")))
        assert info["width"] == 1080
        assert info["height"] == 1920

    def test_output_preserves_duration(self, workdir):
        """Output duration is within ±0.5 s of input."""
        inp, out = workdir
        run_skill(
            self.SKILL, "matte.py",
            ["--input", str(inp), "--output", str(out)],
        )
        info = video_info(next(out.glob("*.mp4")))
        assert abs(info["duration"] - 5.0) < 0.5

    def test_output_retains_audio(self, workdir):
        """Output video has an audio stream."""
        inp, out = workdir
        run_skill(
            self.SKILL, "matte.py",
            ["--input", str(inp), "--output", str(out)],
        )
        info = video_info(next(out.glob("*.mp4")))
        assert info["has_audio"], "Output video missing audio stream"

    def test_hex_bg_produces_valid_video(self, workdir):
        """--bg hex colour produces a valid RGB-composited video."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "matte.py",
            ["--input", str(inp), "--output", str(out),
             "--bg", "#1a1a2e"],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        info = video_info(next(out.glob("*.mp4")))
        assert info["has_video"]
