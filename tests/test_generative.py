"""
test_generative.py — Tests for generative AI skills.

Tools under test:
  clawvace     (video-editing)       — Wan2.1-VACE video inpainting

All require CUDA GPU with significant VRAM. Tests are auto-skipped when GPU
is unavailable or VRAM is insufficient.

Note: clawanimate (image-to-video / LTX-Video) is excluded — model weights
are ~20 GB and impractical to keep in the local test cache.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import (
    requires_gpu,
    requires_hf_model,
    run_skill,
    uv_sync,
    video_info,
    CLIP_WIDTH,
    CLIP_HEIGHT,
    CLIP_DURATION_S,
)


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
    MODEL = "Wan-AI/Wan2.1-VACE-1.3B-diffusers"

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

    @requires_hf_model("Wan-AI/Wan2.1-VACE-1.3B-diffusers")
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

    @requires_hf_model("Wan-AI/Wan2.1-VACE-1.3B-diffusers")
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

    @requires_hf_model("Wan-AI/Wan2.1-VACE-1.3B-diffusers")
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

    @requires_hf_model("Wan-AI/Wan2.1-VACE-1.3B-diffusers")
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
        assert abs(info["duration"] - CLIP_DURATION_S) < 0.5

    @requires_hf_model("Wan-AI/Wan2.1-VACE-1.3B-diffusers")
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


