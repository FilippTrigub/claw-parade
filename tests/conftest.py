"""
conftest.py — shared fixtures and helpers for all skill tests.

Test video: 1080×1920, 30 fps, 5 seconds, stereo AAC audio.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Redirect HuggingFace and Torch model caches to a local writable directory
# (the system ~/.cache/huggingface is owned by root in this environment)
_LOCAL_CACHE = Path(__file__).parent.parent / ".model-cache"
_LOCAL_CACHE.mkdir(exist_ok=True)
_HF_HUB_CACHE = _LOCAL_CACHE / "huggingface" / "hub"
_MODEL_ENV = {
    **os.environ,
    "HF_HOME": str(_LOCAL_CACHE / "huggingface"),
    "TORCH_HOME": str(_LOCAL_CACHE / "torch"),
    "HF_HUB_DISABLE_PROGRESS_BARS": "1",
    # Force offline mode — prevents httpx from trying to connect through the
    # SOCKS proxy (which requires socksio). Models must be pre-cached locally.
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    # suppress uv's VIRTUAL_ENV warning when running from within tests/.venv
    "VIRTUAL_ENV": "",
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
FIXTURES_DIR = Path(__file__).parent / "fixtures"

TEST_CLIP = FIXTURES_DIR / "clip_5s.mp4"
TEST_FRAMES_DIR = FIXTURES_DIR / "frames"

# Known properties of clip_5s.mp4 (actually a 2s clip for fast tests)
CLIP_WIDTH = 1080
CLIP_HEIGHT = 1920
CLIP_FPS = 30
CLIP_DURATION_S = 2.0
CLIP_FRAME_COUNT = 60  # approximate nb_frames


# ---------------------------------------------------------------------------
# GPU detection
# ---------------------------------------------------------------------------

def _gpu_free_gb() -> float:
    """Return free VRAM in GB, or 0.0 if no CUDA GPU is available.

    Uses nvidia-smi so the test venv doesn't need torch installed.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return 0.0
        # nvidia-smi reports in MiB
        free_mib = float(result.stdout.strip().splitlines()[0])
        return free_mib / 1024
    except Exception:
        return 0.0


def requires_gpu(min_gb: float):
    """pytest.mark.skipif that skips when free VRAM < min_gb."""
    return pytest.mark.skipif(
        _gpu_free_gb() < min_gb,
        reason=f"GPU with {min_gb:.1f} GB free VRAM required "
               f"(available: {_gpu_free_gb():.1f} GB)",
    )


# Resolved once at import time — tests use this instead of hardcoding "cpu".
# Keeps GPU tests fast and CPU tests correct on machines without a GPU.
DEVICE = "cuda" if _gpu_free_gb() >= 1.0 else "cpu"


# ---------------------------------------------------------------------------
# HuggingFace model cache detection
# ---------------------------------------------------------------------------

def _hf_model_cached(model_id: str) -> bool:
    """Return True if model weights are fully present in the local HF cache.

    HuggingFace caches models as:
      hub/models--{org}--{name}/snapshots/{hash}/*.safetensors
    A model is considered cached when at least one snapshot contains a
    .safetensors, .bin, or .pt file AND the blobs directory has no
    .incomplete files (which indicate a partial/interrupted download).
    """
    cache_name = "models--" + model_id.replace("/", "--")
    model_cache = _HF_HUB_CACHE / cache_name
    if not model_cache.exists():
        return False
    # Any .incomplete blob means the download was interrupted
    blobs_dir = model_cache / "blobs"
    if blobs_dir.exists() and any(blobs_dir.glob("*.incomplete")):
        return False
    snapshots_dir = model_cache / "snapshots"
    if not snapshots_dir.exists():
        return False
    for snapshot in snapshots_dir.iterdir():
        for ext in ("*.safetensors", "*.bin", "*.pt", "*.pth", "*.onnx"):
            if any(snapshot.rglob(ext)):
                return True
    return False


def requires_hf_model(*model_ids: str):
    """Skip test when any of the given HF model IDs aren't locally cached.

    Use this on tests that call out to transformers/huggingface_hub so they
    skip gracefully instead of failing with a proxy/network error.
    """
    missing = [m for m in model_ids if not _hf_model_cached(m)]
    return pytest.mark.skipif(
        bool(missing),
        reason=f"HF model(s) not in local cache (run outside sandbox to "
               f"pre-download): {', '.join(missing)}",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def skill_dir(name: str) -> Path:
    return SKILLS_DIR / name


def run_skill(skill_name: str, script: str, args: list[str],
              cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a skill script via uv run, with local model cache dirs."""
    cmd = ["uv", "run", "python", f"scripts/{script}"] + args
    result = subprocess.run(
        cmd,
        cwd=cwd or skill_dir(skill_name),
        capture_output=True,
        text=True,
        env=_MODEL_ENV,
    )
    return result


def video_info(path: Path) -> dict:
    """Return dict with width, height, fps, duration, nb_frames, has_audio."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error",
         "-show_streams",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    data = json.loads(probe.stdout)
    info = {"has_audio": False, "has_video": False}
    for s in data.get("streams", []):
        if s["codec_type"] == "video":
            info["has_video"] = True
            info["width"] = s.get("width")
            info["height"] = s.get("height")
            fps_parts = s.get("r_frame_rate", "30/1").split("/")
            info["fps"] = round(int(fps_parts[0]) / int(fps_parts[1]))
            info["duration"] = float(s.get("duration", 0))
            info["nb_frames"] = int(s.get("nb_frames", 0))
        elif s["codec_type"] == "audio":
            info["has_audio"] = True
    return info


def uv_sync(skill_name: str) -> None:
    """Install dependencies for a skill (idempotent)."""
    result = subprocess.run(
        ["uv", "sync"],
        cwd=skill_dir(skill_name),
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"uv sync failed for {skill_name}:\n{result.stderr}")


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_clip() -> Path:
    assert TEST_CLIP.exists(), f"Test clip not found: {TEST_CLIP}"
    return TEST_CLIP


@pytest.fixture(scope="session")
def test_frames() -> list[Path]:
    frames = sorted(TEST_FRAMES_DIR.glob("*.jpg"))
    assert len(frames) >= 3, f"Expected ≥3 test frames in {TEST_FRAMES_DIR}"
    return frames


@pytest.fixture(scope="session")
def portrait_image(test_frames) -> Path:
    """A single JPEG frame usable as portrait source."""
    return test_frames[0]
