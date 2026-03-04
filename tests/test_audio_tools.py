"""
test_audio_tools.py — Tests for audio skills.

Tools under test:
  clawsep   (audio-separation)  — separate vocals from music via Demucs
  clawbeat  (music-gen)         — generate royalty-free music via MusicGen

Both tools support CPU fallback (slow but correct).
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import (
    CLIP_DURATION_S,
    DEVICE,
    skill_dir,
    run_skill,
    uv_sync,
    video_info,
    requires_hf_model,
)


# ===========================================================================
# clawsep — Audio Source Separation (Demucs)
# ===========================================================================

class TestClawSep:
    """
    Expected behaviour:
      - Accepts a video file with audio
      - Separates the requested stem (vocals / no_vocals)
      - Outputs a video file in output_dir with the stem audio replacing original
      - Output video has same or very close duration (±0.5 s)
      - Output has an audio stream
      - Exits 0 on success

    Note: htdemucs weights (~80 MB) downloaded on first run.
    """

    SKILL = "audio-separation"

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

    def test_separates_vocals_stem(self, workdir, test_clip):
        """Output video exists with audio track, duration within ±0.5 s."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "separate.py",
            ["--input", str(inp), "--output", str(out),
             "--stem", "vocals", "--device", DEVICE],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        out_files = list(out.glob("*.mp4"))
        assert len(out_files) == 1, f"Expected 1 output mp4, got {len(out_files)}"

        info = video_info(out_files[0])
        assert info["has_audio"], "Output video missing audio stream"
        assert abs(info["duration"] - CLIP_DURATION_S) < 0.5, (
            f"Duration mismatch: {info['duration']:.2f}s vs expected ~2.0s"
        )

    def test_separates_no_vocals_stem(self, workdir):
        """no_vocals (instrumental) stem also produces valid output."""
        inp, out = workdir
        result = run_skill(
            self.SKILL, "separate.py",
            ["--input", str(inp), "--output", str(out),
             "--stem", "no_vocals", "--device", DEVICE],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        out_files = list(out.glob("*.mp4"))
        assert len(out_files) == 1

    def test_output_has_video_stream(self, workdir):
        """Separated video retains its video stream."""
        inp, out = workdir
        run_skill(
            self.SKILL, "separate.py",
            ["--input", str(inp), "--output", str(out),
             "--stem", "vocals", "--device", DEVICE],
        )
        out_file = next(out.glob("*.mp4"))
        info = video_info(out_file)
        assert info["has_video"], "Output video is missing video stream"

    def test_empty_input_exits_cleanly(self, tmp_path):
        """Empty input dir → exit 0, no crash."""
        inp = tmp_path / "input"
        inp.mkdir()
        out = tmp_path / "output"
        out.mkdir()
        result = run_skill(
            self.SKILL, "separate.py",
            ["--input", str(inp), "--output", str(out), "--stem", "vocals"],
        )
        assert result.returncode == 0


# ===========================================================================
# clawbeat — Music Generation (MusicGen)
# ===========================================================================

class TestClawBeat:
    """
    Expected behaviour:
      - Generates a WAV/MP3 audio file from a text prompt
      - Audio duration is within ±2 s of requested duration
      - When --video is given, output is an MP4 with the music mixed in
      - Exits 0 on success

    Note: musicgen-small weights (~0.3 GB) downloaded on first run.
    CPU mode is accepted with model=small only.
    """

    SKILL = "music-gen"

    @pytest.fixture(autouse=True, scope="class")
    def setup_venv(self):
        uv_sync(self.SKILL)

    def _audio_duration(self, path: Path) -> float:
        """Return duration of an audio/video file in seconds."""
        probe = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True,
        )
        return float(probe.stdout.strip())

    @requires_hf_model("facebook/musicgen-small")
    def test_generates_audio_from_prompt(self, tmp_path):
        """Produces a .wav file of approximately the requested duration."""
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result = run_skill(
            self.SKILL, "generate_music.py",
            ["--prompt", "calm acoustic guitar ambient",
             "--duration", "2",
             "--model", "small",
             "--device", DEVICE,
             "--output", str(out_dir)],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        out = out_dir / "music.wav"
        assert out.exists(), "Output WAV file not created"
        dur = self._audio_duration(out)
        assert abs(dur - 2.0) < 2.0, f"Duration {dur:.1f}s, expected ~2.0s"

    @requires_hf_model("facebook/musicgen-small")
    def test_mixes_music_under_video(self, test_clip, tmp_path):
        """When --video is given, output is an MP4 with audio."""
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result = run_skill(
            self.SKILL, "generate_music.py",
            ["--prompt", "upbeat lo-fi beats",
             "--duration", "2",
             "--model", "small",
             "--device", DEVICE,
             "--video", str(test_clip),
             "--output", str(out_dir)],
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # script names the output after the input video
        out = out_dir / test_clip.name
        assert out.exists(), "Output MP4 not created"
        info = video_info(out)
        assert info["has_video"], "Output MP4 missing video stream"
        assert info["has_audio"], "Output MP4 missing audio stream"

    def test_medium_model_blocked_on_cpu(self, tmp_path):
        """musicgen-medium on CPU should fail with a clear error."""
        out = tmp_path / "music.wav"
        result = run_skill(
            self.SKILL, "generate_music.py",
            ["--prompt", "test",
             "--duration", "3",
             "--model", "medium",
             "--device", "cpu",  # intentionally forced to cpu to test the guard
             "--output", str(out)],
        )
        assert result.returncode != 0, (
            "Expected failure when using medium model on CPU"
        )
        err = (result.stderr + result.stdout).lower()
        assert "gpu" in err or "cuda" in err or "cpu" in err, (
            f"Expected informative error, got: {result.stderr[:200]}"
        )
