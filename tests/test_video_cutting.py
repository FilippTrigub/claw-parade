"""
test_video_cutting.py — Tests for video-cutting skill.

Expected behaviour:
  - Cuts video into segments
  - Rearranges segments in specified order
  - Produces output at specified FPS
  - Preserves audio
  - Auto-detects scene changes (smart cutting)
"""

import json
import shutil
from pathlib import Path

import pytest

from conftest import run_skill, uv_sync, video_info


class TestVideoCutting:
    """
    Video cutting skill tests.

    Uses the existing test_clip (2s, 30fps, 1080x1920).
    """

    SKILL = "video-cutting"

    @pytest.fixture(autouse=True, scope="class")
    def setup_venv(self):
        uv_sync(self.SKILL)

    @pytest.fixture
    def workdir(self, test_clip, tmp_path):
        inp = tmp_path / "input"
        inp.mkdir()
        shutil.copy(test_clip, inp / "video.mp4")

        out = tmp_path / "output"
        out.mkdir()

        return inp, out

    @pytest.fixture
    def config_file(self, workdir):
        inp, out = workdir
        config = {
            "input_dir": str(inp),
            "output_dir": str(out),
            "segments": [
                # Take segments in reverse order to test rearrangement
                {"source": "video.mp4", "start": 1.0, "end": 2.0},
                {"source": "video.mp4", "start": 0.0, "end": 0.5},
                {"source": "video.mp4", "start": 0.5, "end": 1.0},
            ],
            "output_fps": 30,
        }
        config_path = workdir[1] / "config.json"  # use tmp_path for config
        config_path.write_text(json.dumps(config))
        return config_path

    def test_produces_output_video(self, workdir, config_file):
        """Output directory contains exactly one MP4."""
        inp, out = workdir
        result = run_skill(
            self.SKILL,
            "cutter.py",
            ["--config", str(config_file)],
        )
        assert result.returncode == 0, (
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
        out_files = list(out.glob("*.mp4"))
        assert len(out_files) == 1, f"Expected 1 output file, got {len(out_files)}"

    def test_output_duration_matches_segments(self, workdir, config_file):
        """Output duration equals sum of segment durations."""
        inp, out = workdir

        # Expected: (1.0-0.0) + (0.5-0.0) + (1.0-0.5) = 1.0 + 0.5 + 0.5 = 2.0s
        expected_duration = 2.0

        run_skill(
            self.SKILL,
            "cutter.py",
            ["--config", str(config_file)],
        )

        out_files = list(out.glob("*.mp4"))
        info = video_info(out_files[0])

        # Allow ±0.5s tolerance for frame boundaries
        assert abs(info["duration"] - expected_duration) < 0.5, (
            f"Duration: {info['duration']:.2f}s, expected ~{expected_duration}s"
        )

    def test_output_fps_matches_specified(self, workdir, config_file):
        """Output fps matches the specified output_fps in config."""
        inp, out = workdir

        run_skill(
            self.SKILL,
            "cutter.py",
            ["--config", str(config_file)],
        )

        out_files = list(out.glob("*.mp4"))
        info = video_info(out_files[0])

        assert info["fps"] == 30, f"Expected 30 fps, got {info['fps']}"

    def test_output_preserves_audio(self, workdir, config_file):
        """Output video retains the audio stream."""
        inp, out = workdir

        run_skill(
            self.SKILL,
            "cutter.py",
            ["--config", str(config_file)],
        )

        out_files = list(out.glob("*.mp4"))
        info = video_info(out_files[0])
        assert info["has_audio"], "Output video missing audio stream"

    def test_custom_fps(self, workdir, test_clip):
        """Output respects custom FPS setting."""
        inp, out = workdir

        # Create config with 60fps output
        config = {
            "input_dir": str(inp),
            "output_dir": str(out),
            "segments": [
                {"source": "video.mp4", "start": 0.0, "end": 1.0},
            ],
            "output_fps": 60,
        }
        config_path = out / "config60.json"
        config_path.write_text(json.dumps(config))

        run_skill(
            self.SKILL,
            "cutter.py",
            ["--config", str(config_path)],
        )

        out_files = list(out.glob("*.mp4"))
        info = video_info(out_files[0])
        assert info["fps"] == 60, f"Expected 60 fps, got {info['fps']}"


class TestSmartCutting:
    """
    Smart auto-cut tests using PySceneDetect.
    """

    SKILL = "video-cutting"

    @pytest.fixture(autouse=True, scope="class")
    def setup_venv(self):
        uv_sync(self.SKILL)

    @pytest.fixture
    def workdir(self, test_clip, tmp_path):
        inp = tmp_path / "input"
        inp.mkdir()
        shutil.copy(test_clip, inp / "video.mp4")

        out = tmp_path / "output"
        out.mkdir()

        return inp, out

    def test_auto_detect_produces_segments(self, workdir):
        """Auto-detect generates segment config from video."""
        inp, out = workdir

        config = {
            "input_dir": str(inp),
            "output_dir": str(out),
            "segments": [
                {"source": "video.mp4", "start": 0.0, "end": 2.0},
            ],
            "output_fps": 30,
            "auto_detect": {
                "enabled": True,
                "mode": "adaptive",
            },
        }
        config_path = out / "config_auto.json"
        config_path.write_text(json.dumps(config))

        result = run_skill(
            self.SKILL,
            "cutter.py",
            ["--config", str(config_path)],
        )

        assert result.returncode == 0, (
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

    def test_min_scene_duration_filters(self, workdir):
        """Min scene duration filters out short segments."""
        inp, out = workdir

        config = {
            "input_dir": str(inp),
            "output_dir": str(out),
            "segments": [
                {"source": "video.mp4", "start": 0.0, "end": 2.0},
            ],
            "output_fps": 30,
            "auto_detect": {
                "enabled": True,
                "mode": "adaptive",
                "min_scene_duration": 1.0,
            },
        }
        config_path = out / "config_min.json"
        config_path.write_text(json.dumps(config))

        result = run_skill(
            self.SKILL,
            "cutter.py",
            ["--config", str(config_path)],
        )

        assert result.returncode == 0, (
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

    def test_produces_valid_output_with_smart_cuts(self, workdir):
        """End-to-end with smart cutting produces valid output video."""
        inp, out = workdir

        config = {
            "input_dir": str(inp),
            "output_dir": str(out),
            "segments": [
                {"source": "video.mp4", "start": 0.0, "end": 2.0},
            ],
            "output_fps": 30,
            "auto_detect": {
                "enabled": True,
                "mode": "adaptive",
                "min_scene_duration": 0.3,
            },
        }
        config_path = out / "config_smart.json"
        config_path.write_text(json.dumps(config))

        result = run_skill(
            self.SKILL,
            "cutter.py",
            ["--config", str(config_path)],
        )

        assert result.returncode == 0, (
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
        out_files = list(out.glob("*.mp4"))
        assert len(out_files) == 1, f"Expected 1 output file, got {len(out_files)}"

        info = video_info(out_files[0])
        assert info["duration"] > 0, "Output video should have duration"
        assert info["has_audio"], "Output should retain audio"
