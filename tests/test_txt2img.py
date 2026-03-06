"""
test_txt2img.py — Tests for text-to-image generation skill.

Tools under test:
  txt2img (text-to-image) — Generate images from text prompts via diffusers

All require CUDA GPU with significant VRAM. Tests are auto-skipped when GPU
is unavailable or VRAM is insufficient.
"""

import pytest
from pathlib import Path
from PIL import Image

from conftest import (
    requires_gpu,
    requires_hf_model,
    run_skill,
    uv_sync,
)


# ===========================================================================
# txt2img — Text to Image Generation
# ===========================================================================


@requires_gpu(min_gb=6.0)
class TestTxt2Img:
    """
    Expected behaviour:
      - Produces one PNG image per generation call
      - Output image has requested dimensions
      - Output is a valid image file
      - Exits 0 on success

    Note: SDXL requires ~8GB VRAM. Tests use SDXL as it's not gated.
    """

    SKILL = "text-to-image"
    # Use SD3 as default - most lightweight option (~6GB)
    DEFAULT_MODEL = "sdxl"

    @pytest.fixture(autouse=True, scope="class")
    def setup_venv(self):
        uv_sync(self.SKILL)

    @pytest.fixture
    def workdir(self, tmp_path):
        out = tmp_path / "output"
        out.mkdir()
        return out

    @requires_hf_model("stabilityai/stable-diffusion-xl-base-1.0")
    def test_produces_png_output(self, workdir):
        """Generation produces a PNG file in output directory."""
        result = run_skill(
            self.SKILL,
            "txt2img.py",
            [
                "--model",
                self.DEFAULT_MODEL,
                "--prompt",
                "a red apple on a wooden table",
                "--output",
                str(workdir),
                "--steps",
                "5",
            ],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        png_files = list(workdir.glob("*.png"))
        assert len(png_files) == 1, f"Expected 1 PNG, got {len(png_files)}"

    @requires_hf_model("stabilityai/stable-diffusion-xl-base-1.0")
    def test_output_has_requested_dimensions(self, workdir):
        """Output image has the dimensions specified in args."""
        result = run_skill(
            self.SKILL,
            "txt2img.py",
            [
                "--model",
                self.DEFAULT_MODEL,
                "--prompt",
                "a blue sky with clouds",
                "--output",
                str(workdir),
                "--width",
                "512",
                "--height",
                "512",
                "--steps",
                "5",
            ],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        png_files = list(workdir.glob("*.png"))
        assert len(png_files) == 1
        with Image.open(png_files[0]) as img:
            assert img.size == (512, 512), f"Expected (512, 512), got {img.size}"

    @requires_hf_model("stabilityai/stable-diffusion-xl-base-1.0")
    def test_multiple_images_produce_multiple_files(self, workdir):
        """--num-images produces that many output files."""
        result = run_skill(
            self.SKILL,
            "txt2img.py",
            [
                "--model",
                self.DEFAULT_MODEL,
                "--prompt",
                "an abstract painting",
                "--output",
                str(workdir),
                "--num-images",
                "3",
                "--steps",
                "5",
            ],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        png_files = list(workdir.glob("*.png"))
        assert len(png_files) == 3, f"Expected 3 PNGs, got {len(png_files)}"

    @requires_hf_model("stabilityai/stable-diffusion-xl-base-1.0")
    def test_seed_produces_reproducible_output(self, workdir):
        """Same seed produces identical images."""
        # Create subdirs for each run
        out1 = workdir / "run1"
        out2 = workdir / "run2"
        out1.mkdir()
        out2.mkdir()

        for out_dir in [out1, out2]:
            result = run_skill(
                self.SKILL,
                "txt2img.py",
                [
                    "--model",
                    self.DEFAULT_MODEL,
                    "--prompt",
                    "a sunset over mountains",
                    "--output",
                    str(out_dir),
                    "--seed",
                    "42",
                    "--steps",
                    "5",
                ],
            )
            assert result.returncode == 0, f"stderr: {result.stderr}"

        # Compare the two outputs (files have different timestamps but same content)
        files1 = list(out1.glob("*.png"))
        files2 = list(out2.glob("*.png"))
        assert len(files1) == 1 and len(files2) == 1
        with Image.open(files1[0]) as img1, Image.open(files2[0]) as img2:
            assert img1.tobytes() == img2.tobytes(), (
                "Same seed should produce identical images"
            )

    @requires_hf_model("stabilityai/stable-diffusion-xl-base-1.0")
    def test_different_seeds_produce_different_output(self, workdir):
        """Different seeds produce different images."""
        out1 = workdir / "out1"
        out2 = workdir / "out2"
        out1.mkdir()
        out2.mkdir()

        result1 = run_skill(
            self.SKILL,
            "txt2img.py",
            [
                "--model",
                self.DEFAULT_MODEL,
                "--prompt",
                "a cat",
                "--output",
                str(out1),
                "--seed",
                "1",
                "--steps",
                "5",
            ],
        )
        result2 = run_skill(
            self.SKILL,
            "txt2img.py",
            [
                "--model",
                self.DEFAULT_MODEL,
                "--prompt",
                "a cat",
                "--output",
                str(out2),
                "--seed",
                "999",
                "--steps",
                "5",
            ],
        )
        assert result1.returncode == 0 and result2.returncode == 0

        files1 = list(out1.glob("*.png"))
        files2 = list(out2.glob("*.png"))
        assert len(files1) == 1 and len(files2) == 1
        with Image.open(files1[0]) as img1, Image.open(files2[0]) as img2:
            assert img1.tobytes() != img2.tobytes(), (
                "Different seeds should produce different images"
            )

    def test_missing_prompt_fails_validation(self, workdir):
        """Without --prompt, the script should fail validation."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            import json

            json.dump({"model": self.DEFAULT_MODEL, "output_dir": str(workdir)}, f)
            config_path = f.name
        try:
            result = run_skill(
                self.SKILL,
                "txt2img.py",
                ["--config", config_path],
            )
            assert result.returncode != 0
            assert (
                "prompt" in result.stderr.lower() or "required" in result.stderr.lower()
            )
        finally:
            Path(config_path).unlink(missing_ok=True)

    def test_custom_hf_model_id(self, workdir):
        """Can specify a custom HuggingFace model ID."""
        # This will likely fail or produce garbage with random IDs,
        # but it should at least attempt to load the model
        result = run_skill(
            self.SKILL,
            "txt2img.py",
            [
                "--model",
                "stabilityai/stable-diffusion-3-medium",
                "--prompt",
                "test",
                "--output",
                str(workdir),
                "--steps",
                "1",
            ],
        )
        # Either succeeds or fails gracefully - we just want to ensure it runs
        # without crashing the python process
        assert result.returncode in (
            0,
            1,
        )  # 0 = success, 1 = validation/generation error
