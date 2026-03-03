#!/usr/bin/env python3
"""
score.py — clawaes: score images by visual quality and copy the top-K to output.

Two modes:
  aesthetic  — ranks by a fixed "high quality" vs "low quality" CLIP contrast
               (no prompt needed)
  pick       — ranks by cosine similarity to a user-supplied prompt via
               PickScore (yuvalkirstain/PickScore_v1)

Usage:
  python scripts/score.py [--config config.json]
  python scripts/score.py --input ./input --output ./output --top 5
  python scripts/score.py --input ./input --output ./output --device cpu
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

INPUT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VALID_MODES = {"aesthetic", "pick"}
VALID_DEVICES = {"auto", "cpu", "cuda"}

# Prompts used for the aesthetic mode CLIP contrast
POSITIVE_PROMPTS = [
    "a high quality photograph, professional photography, beautiful, sharp focus",
    "award winning photography, stunning, vibrant colors",
]
NEGATIVE_PROMPTS = [
    "a low quality photo, blurry, bad composition, ugly, dark",
    "out of focus, overexposed, underexposed, poor lighting",
]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(path: Path) -> dict:
    if not path.exists():
        print(f"Error: config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open() as f:
        return json.load(f)


def validate_config(cfg: dict) -> dict:
    errors = []
    mode = cfg.get("mode", "aesthetic")
    if mode not in VALID_MODES:
        errors.append(f"'mode' must be one of: {', '.join(VALID_MODES)}")
    if mode == "pick" and not cfg.get("prompt"):
        errors.append("'prompt' is required when mode is 'pick'")
    top = cfg.get("top", 3)
    if not isinstance(top, int) or top < 1:
        errors.append("'top' must be a positive integer")
    device = cfg.get("device", "auto")
    if device not in VALID_DEVICES:
        errors.append(f"'device' must be one of: {', '.join(VALID_DEVICES)}")
    if errors:
        print("Config errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    return cfg


def resolve_device(cfg: dict) -> str:
    device = cfg.get("device", "auto")
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_aesthetic(image_paths: list[Path], device: str) -> list[float]:
    """Score images using CLIP cosine similarity (positive vs negative prompts)."""
    import torch
    from transformers import CLIPProcessor, CLIPModel

    print(f"Loading CLIP model on {device}…")
    model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14").to(device)
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")
    model.eval()

    all_prompts = POSITIVE_PROMPTS + NEGATIVE_PROMPTS
    text_inputs = processor(text=all_prompts, return_tensors="pt", padding=True).to(device)

    scores = []
    with torch.no_grad():
        raw = model.get_text_features(**text_inputs)
        # In newer transformers versions get_text_features() may return a
        # dataclass rather than a plain tensor; unwrap if needed.
        text_features = raw if isinstance(raw, torch.Tensor) else (
            raw.text_embeds if hasattr(raw, "text_embeds") else raw.pooler_output
        )
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        for img_path in image_paths:
            image = Image.open(img_path).convert("RGB")
            img_inputs = processor(images=image, return_tensors="pt").to(device)
            raw_img = model.get_image_features(**img_inputs)
            img_features = raw_img if isinstance(raw_img, torch.Tensor) else (
                raw_img.image_embeds if hasattr(raw_img, "image_embeds") else raw_img.pooler_output
            )
            img_features = img_features / img_features.norm(dim=-1, keepdim=True)

            sims = (img_features @ text_features.T).squeeze(0).cpu().tolist()
            n_pos = len(POSITIVE_PROMPTS)
            pos_score = sum(sims[:n_pos]) / n_pos
            neg_score = sum(sims[n_pos:]) / len(NEGATIVE_PROMPTS)
            scores.append(pos_score - neg_score)

    return scores


def score_pick(image_paths: list[Path], prompt: str, device: str) -> list[float]:
    """Score images by similarity to a text prompt using PickScore."""
    import torch
    from transformers import AutoProcessor, AutoModel

    print(f"Loading PickScore model on {device}…")
    processor = AutoProcessor.from_pretrained("laion/CLIP-ViT-H-14-laion2B-s32B-b79K")
    model = AutoModel.from_pretrained("yuvalkirstain/PickScore_v1").to(device)
    model.eval()

    scores = []
    with torch.no_grad():
        text_inputs = processor(
            text=prompt, return_tensors="pt", padding=True, truncation=True
        ).to(device)
        text_features = model.get_text_features(**text_inputs)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        for img_path in image_paths:
            image = Image.open(img_path).convert("RGB")
            img_inputs = processor(images=image, return_tensors="pt").to(device)
            img_features = model.get_image_features(**img_inputs)
            img_features = img_features / img_features.norm(dim=-1, keepdim=True)
            score = (img_features @ text_features.T).item()
            scores.append(score)

    return scores


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process(config_path: Path) -> None:
    cfg = validate_config(load_config(config_path))

    input_dir = Path(cfg.get("input_dir", "./input"))
    output_dir = Path(cfg.get("output_dir", "./output"))
    top = cfg.get("top", 3)
    mode = cfg.get("mode", "aesthetic")
    prompt = cfg.get("prompt")
    device = resolve_device(cfg)

    if not input_dir.exists():
        print(f"Error: input_dir does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)

    images = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in INPUT_EXTENSIONS
    )
    if not images:
        print(f"No images found in {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scoring {len(images)} image(s) [{mode} mode] on {device}…")
    print()

    if mode == "aesthetic":
        scores = score_aesthetic(images, device)
    else:
        scores = score_pick(images, prompt, device)

    ranked = sorted(zip(scores, images), reverse=True)
    selected = ranked[:top]

    print()
    print(f"Top {top} of {len(images)}:")
    for rank, (score, path) in enumerate(selected, 1):
        dest = output_dir / f"{rank:02d}_{path.name}"
        shutil.copy2(path, dest)
        print(f"  [{rank}] {path.name}  score={score:.4f}  → {dest.name}")

    print()
    rejected = len(images) - len(selected)
    print(f"Done: {len(selected)} selected, {rejected} not copied.")


def main() -> None:
    parser = argparse.ArgumentParser(description="clawaes — aesthetic image selector")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--input", help="Override input_dir")
    parser.add_argument("--output", help="Override output_dir")
    parser.add_argument("--top", type=int, help="Override top")
    parser.add_argument("--mode", choices=list(VALID_MODES), help="Override mode")
    parser.add_argument("--prompt", help="Override prompt (used with mode=pick)")
    parser.add_argument("--device", choices=list(VALID_DEVICES), help="Override device")
    args = parser.parse_args()

    config_path = Path(args.config)
    cfg = validate_config(load_config(config_path))

    # CLI args override config
    if args.input:
        cfg["input_dir"] = args.input
    if args.output:
        cfg["output_dir"] = args.output
    if args.top is not None:
        cfg["top"] = args.top
    if args.mode:
        cfg["mode"] = args.mode
    if args.prompt:
        cfg["prompt"] = args.prompt
    if args.device:
        cfg["device"] = args.device

    # Re-validate after overrides
    validate_config(cfg)

    # Write merged config back to a temp object and process
    import tempfile, json as _json
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        _json.dump(cfg, tmp)
        tmp_path = Path(tmp.name)

    try:
        process(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
