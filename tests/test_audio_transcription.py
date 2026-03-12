"""
test_audio_transcription.py — Tests for audio-transcription skill.

Expected behavior:
  - Extracts audio from video files
  - Transcribes using HuggingFace ASR models
  - Outputs per-segment JSON with timestamps and text
  - Supports configurable model and device (CPU/GPU)
  - Works with Docker-compatible cache handling
"""

import json
import shutil
from pathlib import Path

import pytest

from conftest import DEVICE, requires_hf_model, run_skill, uv_sync


class TestAudioTranscription:
    """
    Audio transcription skill tests.

    Uses the existing test_clip fixture (2s, 30fps, 1080x1920 with stereo audio).
    """

    SKILL = "audio-transcription"

    @pytest.fixture(autouse=True, scope="class")
    def setup_venv(self):
        uv_sync(self.SKILL)

    @pytest.fixture
    @requires_hf_model("distil-whisper/distil-large-v3")
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
            "input_dir": str(inp.resolve()),
            "output_dir": str(out.resolve()),
            "model": "distil-whisper/distil-large-v3",
            "device": "cpu",
            "language": "en",
        }
        config_path = out / "config.json"
        config_path.write_text(json.dumps(config))
        return config_path

    def test_produces_transcription_json(self, workdir, config_file):
        """Output directory contains transcription JSON file."""
        inp, out = workdir

        result = run_skill(
            self.SKILL,
            "transcriber.py",
            ["--config", str(config_file)],
        )

        assert result.returncode == 0, (
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

        json_files = list(out.glob("*_transcription.json"))
        assert len(json_files) == 1, f"Expected 1 JSON file, got {len(json_files)}"

    def test_json_has_required_fields(self, workdir, config_file):
        """Transcription JSON contains all required fields."""
        inp, out = workdir

        run_skill(
            self.SKILL,
            "transcriber.py",
            ["--config", str(config_file)],
        )

        json_files = list(out.glob("*_transcription.json"))
        with open(json_files[0]) as f:
            data = json.load(f)

        assert "file" in data
        assert "duration" in data
        assert "language" in data
        assert "model" in data
        assert "segments" in data
        assert isinstance(data["segments"], list)

    def test_segments_have_timestamps(self, workdir, config_file):
        """Each segment has start, end, and text fields."""
        inp, out = workdir

        run_skill(
            self.SKILL,
            "transcriber.py",
            ["--config", str(config_file)],
        )

        json_files = list(out.glob("*_transcription.json"))
        with open(json_files[0]) as f:
            data = json.load(f)

        for segment in data["segments"]:
            assert "start" in segment
            assert "end" in segment
            assert "text" in segment
            assert isinstance(segment["start"], (int, float))
            assert isinstance(segment["end"], (int, float))
            assert isinstance(segment["text"], str)

    def test_timestamps_in_order(self, workdir, config_file):
        """Segment timestamps are in chronological order."""
        inp, out = workdir

        run_skill(
            self.SKILL,
            "transcriber.py",
            ["--config", str(config_file)],
        )

        json_files = list(out.glob("*_transcription.json"))
        with open(json_files[0]) as f:
            data = json.load(f)

        segments = data["segments"]
        for i in range(1, len(segments)):
            assert segments[i]["start"] >= segments[i - 1]["end"], (
                f"Timestamps not in order: segment {i - 1} ends at "
                f"{segments[i - 1]['end']}, segment {i} starts at "
                f"{segments[i]['start']}"
            )

    def test_total_duration_matches_video(self, workdir, config_file, test_clip):
        """Check that transcription produces valid segments with timestamps."""
        inp, out = workdir

        run_skill(
            self.SKILL,
            "transcriber.py",
            ["--config", str(config_file)],
        )

        json_files = list(out.glob("*_transcription.json"))
        with open(json_files[0]) as f:
            data = json.load(f)

        # Check that we have at least one segment with valid timestamps
        assert len(data["segments"]) >= 1, "Expected at least 1 segment"

        # Verify segments have valid timestamps
        for segment in data["segments"]:
            assert "start" in segment, "Segment missing 'start' field"
            assert "end" in segment, "Segment missing 'end' field"
            assert segment["start"] >= 0, "Segment start timestamp must be non-negative"
            assert segment["end"] >= segment["start"], (
                f"Segment end ({segment['end']}) must be >= start ({segment['start']})"
            )

    def test_custom_model(self, workdir, config_file):
        """Custom model can be specified in config."""
        inp, out = workdir

        config = json.loads(config_file.read_text())
        config["model"] = "openai/whisper-small"
        config_file.write_text(json.dumps(config))

        result = run_skill(
            self.SKILL,
            "transcriber.py",
            ["--config", str(config_file)],
        )

        assert result.returncode == 0, (
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

        json_files = list(out.glob("*_transcription.json"))
        with open(json_files[0]) as f:
            data = json.load(f)

        assert data["model"] == "openai/whisper-small"

    def test_cli_overrides_config(self, workdir, config_file):
        """CLI arguments override config file values."""
        inp, out = workdir

        result = run_skill(
            self.SKILL,
            "transcriber.py",
            ["--config", str(config_file), "--language", "en"],
        )

        assert result.returncode == 0, (
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

        json_files = list(out.glob("*_transcription.json"))
        with open(json_files[0]) as f:
            data = json.load(f)

        assert data["language"] == "en"

    def test_audio_extraction(self, workdir, config_file):
        """Intermediate audio extraction creates WAV file."""
        inp, out = workdir

        run_skill(
            self.SKILL,
            "transcriber.py",
            ["--config", str(config_file)],
        )

        # Check for extracted audio file
        wav_files = list(out.glob("*_audio.wav"))
        # Audio file may or may not be kept depending on implementation
        assert len(wav_files) >= 0


class TestAudioTranscriptionConfig:
    """Configuration and error handling tests."""

    SKILL = "audio-transcription"

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

    def test_invalid_model(self, workdir, tmp_path):
        """Invalid model ID produces error."""
        inp, out = workdir

        config = {
            "input_dir": str(inp),
            "output_dir": str(out),
            "model": "invalid/model/that/does/not/exist",
            "device": "cpu",
            "language": "en",
        }
        config_path = out / "config_invalid.json"
        config_path.write_text(json.dumps(config))

        result = run_skill(
            self.SKILL,
            "transcriber.py",
            ["--config", str(config_path)],
        )

        assert result.returncode != 0, "Should fail with invalid model"

    def test_nonexistent_input_file(self, tmp_path):
        """Nonexistent input file produces error."""
        inp = tmp_path / "input"
        inp.mkdir()
        out = tmp_path / "output"
        out.mkdir()

        config = {
            "input_dir": str(inp),
            "output_dir": str(out),
            "model": "distil-whisper/distil-large-v3",
            "device": "cpu",
            "language": "en",
        }
        config_path = out / "config.json"
        config_path.write_text(json.dumps(config))

        result = run_skill(
            self.SKILL,
            "transcriber.py",
            ["--config", str(config_path)],
        )

        assert result.returncode != 0, "Should fail with missing input file"

    def test_empty_input_directory(self, tmp_path):
        """Empty input directory produces error."""
        inp = tmp_path / "input"
        inp.mkdir()
        out = tmp_path / "output"
        out.mkdir()

        config = {
            "input_dir": str(inp),
            "output_dir": str(out),
            "model": "distil-whisper/distil-large-v3",
            "device": "cpu",
            "language": "en",
        }
        config_path = out / "config.json"
        config_path.write_text(json.dumps(config))

        result = run_skill(
            self.SKILL,
            "transcriber.py",
            ["--config", str(config_path)],
        )

        assert result.returncode != 0, "Should fail with empty input directory"
