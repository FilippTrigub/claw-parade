#!/usr/bin/env python3
"""Download all model weights needed by the test suite into the local cache."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from conftest import _HF_HUB_CACHE

os.environ["HF_HOME"] = str(_HF_HUB_CACHE)
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "0"
os.environ["HF_HUB_OFFLINE"] = "0"

HF_MODELS = [
    "stabilityai/stable-diffusion-xl-base-1.0",
    "Wan-AI/Wan2.1-VACE-1.3B-diffusers",
    "facebook/musicgen-small",
    "openai/clip-vit-large-patch14",
    "HuggingFaceTB/SmolVLM-256M-Instruct",
]

from huggingface_hub import snapshot_download


def main():
    for model_id in HF_MODELS:
        print(f"\n{'=' * 60}")
        print(f"Downloading {model_id} …")
        print(f"{'=' * 60}")
        try:
            path = snapshot_download(model_id, cache_dir=_HF_HUB_CACHE)
            print(f"✓ Saved to {path}")
        except Exception as e:
            print(f"✗ Failed: {e}")

    print("\nDone.")
    print(f"\nModels cached at: {_HF_HUB_CACHE}")


if __name__ == "__main__":
    main()
