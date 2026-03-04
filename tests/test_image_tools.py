"""
test_image_tools.py — Tests for CPU-viable image processing skills.

Tools under test:
  clawaes   (aesthetic-selection)  — rank images, copy top-K
  clawdepth (depth-bokeh)          — synthetic bokeh via MiDaS
  clawbg    (bg-removal)           — background removal via rembg
  clawvlm   (vision-caption)       — image captioning via smolvlm

All tests use `uv run` to execute inside each skill's own virtualenv.
Tests run on CPU and skip only when a model download fails.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from conftest import (
    CLIP_HEIGHT,
    CLIP_WIDTH,
    DEVICE,
    skill_dir,
    run_skill,
    uv_sync,
    test_frames,
    requires_hf_model,
)


# ===========================================================================
# clawaes — Aesthetic Auto-Selection
# ===========================================================================

class TestClawAes:
    """
    Expected behaviour:
      - Scores every image in input_dir
      - Copies top-K images to output_dir with rank prefix (01_…, 02_…)
      - Exits 0 on success
    """

    SKILL = "aesthetic-selection"

    @pytest.fixture(autouse=True, scope="class")
    def setup_venv(self):
        uv_sync(self.SKILL)

    @pytest.fixture
    def workdir(self, test_frames, tmp_path):
        inp = tmp_path / "input"
        inp.mkdir()
        for f in test_frames:
            shutil.copy(f, inp)
        out = tmp_path / "output"
        out.mkdir()
        return inp, out

    @requires_hf_model("openai/clip-vit-large-patch14")
    def test_top_3_aesthetic_mode(self, workdir):
        """Copies exactly 3 ranked images in aesthetic mode."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "score.py",
            ["--input", str(inp), "--output", str(out),
             "--mode", "aesthetic", "--top", "3", "--device", DEVICE],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        ranked = sorted(out.glob("*.jpg"))
        assert len(ranked) == 3
        # Files must have numeric rank prefix
        for f in ranked:
            assert f.name[:2].isdigit(), f"Expected rank prefix: {f.name}"

    @requires_hf_model("openai/clip-vit-large-patch14")
    def test_top_1_returns_single_best(self, workdir):
        """With --top 1, only the single best image is copied."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "score.py",
            ["--input", str(inp), "--output", str(out),
             "--mode", "aesthetic", "--top", "1", "--device", DEVICE],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        ranked = sorted(out.glob("*.jpg"))
        assert len(ranked) == 1
        assert ranked[0].name.startswith("01_")

    @requires_hf_model("openai/clip-vit-large-patch14")
    def test_top_exceeds_input_returns_all(self, workdir, test_frames):
        """With --top > number of images, all images are copied."""
        inp, out = workdir
        n = len(test_frames)
        result = run_skill(
            self.SKILL, "score.py",
            ["--input", str(inp), "--output", str(out),
             "--mode", "aesthetic", "--top", str(n + 10), "--device", DEVICE],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        ranked = sorted(out.glob("*.jpg"))
        assert len(ranked) == n

    def test_empty_input_exits_cleanly(self, tmp_path):
        """Empty input dir produces exit 0 with a clear message, no crash."""
        inp = tmp_path / "input"
        inp.mkdir()
        out = tmp_path / "output"
        out.mkdir()
        result = run_skill(
            self.SKILL, "score.py",
            ["--input", str(inp), "--output", str(out),
             "--mode", "aesthetic", "--top", "3", "--device", DEVICE],
        )
        assert result.returncode == 0
        assert not any(out.iterdir())


# ===========================================================================
# clawdepth — Synthetic Bokeh
# ===========================================================================

class TestClawDepth:
    """
    Expected behaviour:
      - Produces one output image per input image
      - Output images are the same resolution as input
      - Output images differ from input (blur has been applied)
      - Exits 0 on success
    """

    SKILL = "depth-bokeh"

    @pytest.fixture(autouse=True, scope="class")
    def setup_venv(self):
        uv_sync(self.SKILL)

    @pytest.fixture
    def workdir(self, test_frames, tmp_path):
        inp = tmp_path / "input"
        inp.mkdir()
        for f in test_frames[:3]:  # 3 images is enough
            shutil.copy(f, inp)
        out = tmp_path / "output"
        out.mkdir()
        return inp, out

    def test_produces_one_output_per_input(self, workdir, test_frames):
        """Output folder has exactly as many images as input folder."""
        inp, out = workdir
        n_in = len(list(inp.glob("*.jpg")))
        result = run_skill(
            self.SKILL, "bokeh.py",
            ["--input", str(inp), "--output", str(out), "--device", DEVICE],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        n_out = len(list(out.glob("*.jpg")))
        assert n_out == n_in

    def test_output_resolution_matches_input(self, workdir):
        """Bokeh does not change image dimensions."""
        inp, out = workdir
        run_skill(
            self.SKILL, "bokeh.py",
            ["--input", str(inp), "--output", str(out), "--device", DEVICE],
        )
        for src in inp.glob("*.jpg"):
            dst = out / src.name
            assert dst.exists()
            with Image.open(src) as s, Image.open(dst) as d:
                assert s.size == d.size, (
                    f"{src.name}: size mismatch {s.size} vs {d.size}"
                )

    def test_output_differs_from_input(self, workdir):
        """Blur is actually applied — output pixels differ from source."""
        import numpy as np
        inp, out = workdir
        run_skill(
            self.SKILL, "bokeh.py",
            ["--input", str(inp), "--output", str(out), "--device", DEVICE],
        )
        for src in inp.glob("*.jpg"):
            dst = out / src.name
            src_arr = np.array(Image.open(src))
            dst_arr = np.array(Image.open(dst))
            diff = np.abs(src_arr.astype(int) - dst_arr.astype(int)).mean()
            assert diff > 0.5, f"{src.name}: output identical to input (diff={diff:.3f})"

    def test_blur_strength_param(self, workdir):
        """Higher blur_strength produces a more blurred output."""
        import numpy as np
        inp, out = workdir
        out_low = out.parent / "out_low"
        out_high = out.parent / "out_high"
        out_low.mkdir()
        out_high.mkdir()

        run_skill(self.SKILL, "bokeh.py",
                  ["--input", str(inp), "--output", str(out_low),
                   "--blur-strength", "5", "--device", DEVICE])
        run_skill(self.SKILL, "bokeh.py",
                  ["--input", str(inp), "--output", str(out_high),
                   "--blur-strength", "30", "--device", DEVICE])

        for f in inp.glob("*.jpg"):
            low = np.array(Image.open(out_low / f.name))
            high = np.array(Image.open(out_high / f.name))
            src = np.array(Image.open(f))
            diff_low = np.abs(src.astype(int) - low.astype(int)).mean()
            diff_high = np.abs(src.astype(int) - high.astype(int)).mean()
            assert diff_high >= diff_low, (
                f"{f.name}: higher blur_strength should produce larger diff"
            )


# ===========================================================================
# clawbg — Background Removal (Images)
# ===========================================================================

class TestClawBg:
    """
    Expected behaviour:
      - Produces one PNG per input image
      - PNG has RGBA mode (4 channels) when bg=null
      - PNG has RGB mode when a hex colour bg is given
      - Output dimensions match input
      - Exits 0 on success
    """

    SKILL = "bg-removal"

    @pytest.fixture(autouse=True, scope="class")
    def setup_venv(self):
        uv_sync(self.SKILL)

    @pytest.fixture
    def workdir(self, test_frames, tmp_path):
        inp = tmp_path / "input"
        inp.mkdir()
        for f in test_frames[:3]:
            shutil.copy(f, inp)
        out = tmp_path / "output"
        out.mkdir()
        return inp, out

    def test_produces_png_per_input(self, workdir):
        """One PNG output per input JPEG."""
        inp, out = workdir
        n_in = len(list(inp.glob("*.jpg")))
        result = run_skill(
            self.SKILL, "rembg_batch.py",
            ["--input", str(inp), "--output", str(out), "--device", DEVICE],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        n_out = len(list(out.glob("*.png")))
        assert n_out == n_in

    def test_transparent_output_has_alpha(self, workdir):
        """Without --bg, output PNGs are RGBA (transparent background)."""
        inp, out = workdir
        run_skill(
            self.SKILL, "rembg_batch.py",
            ["--input", str(inp), "--output", str(out), "--device", DEVICE],
        )
        for png in out.glob("*.png"):
            with Image.open(png) as img:
                assert img.mode == "RGBA", (
                    f"{png.name}: expected RGBA, got {img.mode}"
                )

    def test_hex_bg_produces_rgb_output(self, workdir):
        """With --bg #hex, output is composited to RGB (no alpha needed)."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "rembg_batch.py",
            ["--input", str(inp), "--output", str(out),
             "--bg", "#1a1a2e", "--device", DEVICE],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        for png in out.glob("*.png"):
            with Image.open(png) as img:
                assert img.mode == "RGB", (
                    f"{png.name}: expected RGB after bg composite, got {img.mode}"
                )

    def test_output_dimensions_match_input(self, workdir):
        """Background removal does not change image dimensions."""
        inp, out = workdir
        run_skill(
            self.SKILL, "rembg_batch.py",
            ["--input", str(inp), "--output", str(out), "--device", DEVICE],
        )
        for jpg in inp.glob("*.jpg"):
            png = out / (jpg.stem + ".png")
            assert png.exists()
            with Image.open(jpg) as s, Image.open(png) as d:
                assert s.size == d.size, (
                    f"{jpg.name}: dimension mismatch {s.size} vs {d.size}"
                )


# ===========================================================================
# clawvlm — Vision Captioning (smolvlm, CPU mode)
# ===========================================================================

class TestClawVlm:
    """
    Expected behaviour:
      - Produces one .json sidecar per input image
      - JSON has keys: description, caption, tags
      - description is a non-empty string
      - caption is a non-empty string
      - tags is a list of strings
      - Exits 0 on success

    Note: SmolVLM-256M weights (~1.8 GB) are downloaded on first run.
    """

    SKILL = "vision-caption"

    @pytest.fixture(autouse=True, scope="class")
    def setup_venv(self):
        uv_sync(self.SKILL)

    @pytest.fixture
    def workdir(self, test_frames, tmp_path):
        inp = tmp_path / "input"
        inp.mkdir()
        for f in test_frames[:2]:  # 2 images to keep test fast
            shutil.copy(f, inp)
        out = tmp_path / "output"
        out.mkdir()
        return inp, out

    @requires_hf_model("HuggingFaceTB/SmolVLM-256M-Instruct")
    def test_produces_json_per_image(self, workdir):
        """One JSON sidecar per input image."""
        inp, out = workdir
        n_in = len(list(inp.glob("*.jpg")))
        result = run_skill(
            self.SKILL, "describe.py",
            ["--input", str(inp), "--output", str(out),
             "--model", "smolvlm", "--device", DEVICE],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        n_out = len(list(out.glob("*.json")))
        assert n_out == n_in

    @requires_hf_model("HuggingFaceTB/SmolVLM-256M-Instruct")
    def test_json_has_required_keys(self, workdir):
        """Each JSON contains description, caption, tags."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "describe.py",
            ["--input", str(inp), "--output", str(out),
             "--model", "smolvlm", "--device", DEVICE],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        json_files = list(out.glob("*.json"))
        assert len(json_files) > 0, "No JSON output files produced"
        for js in json_files:
            with js.open() as f:
                data = json.load(f)
            assert "description" in data, f"{js.name}: missing 'description'"
            assert "caption" in data, f"{js.name}: missing 'caption'"
            assert "tags" in data, f"{js.name}: missing 'tags'"

    @requires_hf_model("HuggingFaceTB/SmolVLM-256M-Instruct")
    def test_description_is_nonempty_string(self, workdir):
        """Description field is a non-empty string."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "describe.py",
            ["--input", str(inp), "--output", str(out),
             "--model", "smolvlm", "--device", DEVICE],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        json_files = list(out.glob("*.json"))
        assert len(json_files) > 0, "No JSON output files produced"
        for js in json_files:
            with js.open() as f:
                data = json.load(f)
            assert isinstance(data["description"], str), f"{js.name}: description not str"
            assert len(data["description"]) > 5, f"{js.name}: description too short"

    @requires_hf_model("HuggingFaceTB/SmolVLM-256M-Instruct")
    def test_tags_is_list_of_strings(self, workdir):
        """Tags field is a list (possibly empty) of strings."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "describe.py",
            ["--input", str(inp), "--output", str(out),
             "--model", "smolvlm", "--device", DEVICE],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        json_files = list(out.glob("*.json"))
        assert len(json_files) > 0, "No JSON output files produced"
        for js in json_files:
            with js.open() as f:
                data = json.load(f)
            assert isinstance(data["tags"], list), f"{js.name}: tags not a list"
            for tag in data["tags"]:
                assert isinstance(tag, str), f"{js.name}: tag not a string: {tag!r}"

    def test_phi4_requires_gpu_on_cpu(self, tmp_path):
        """phi4 model on CPU should fail with a clear error (not crash)."""
        inp = tmp_path / "input"
        inp.mkdir()
        shutil.copy(next(TEST_FRAMES_DIR.glob("*.jpg")), inp)
        out = tmp_path / "output"
        out.mkdir()
        result = run_skill(
            self.SKILL, "describe.py",
            ["--input", str(inp), "--output", str(out),
             "--model", "phi4", "--device", "cpu"],  # intentionally forced to test guard
        )
        assert result.returncode != 0
        assert "gpu" in result.stderr.lower() or "cuda" in result.stderr.lower(), (
            f"Expected GPU error message, got: {result.stderr[:200]}"
        )


TEST_FRAMES_DIR = Path(__file__).parent / "fixtures" / "frames"
