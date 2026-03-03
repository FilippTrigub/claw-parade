#!/usr/bin/env python3
"""
describe.py — clawvlm: auto-describe images using a local vision-language model.

For each image in input_dir, writes a JSON sidecar to output_dir containing:
  - description: one-sentence image description
  - caption:     suggested Instagram caption with hashtags
  - tags:        list of detected themes / keywords

Supported models:
  moondream2  — 2B params, fast, works on CPU (default)
  phi4        — 3.8B multimodal, higher quality, requires GPU

Usage:
  python scripts/describe.py [--config config.json]
  python scripts/describe.py --input ./input --output ./output
  python scripts/describe.py --input ./input --output ./output --device cpu
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

INPUT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VALID_MODELS = {"moondream2", "phi4"}
VALID_DEVICES = {"auto", "cpu", "cuda"}

MOONDREAM_REPO = "vikhyatk/moondream2"
MOONDREAM_REVISION = "2024-07-23"
PHI4_REPO = "microsoft/Phi-4-multimodal-instruct"


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
    model = cfg.get("model", "moondream2")
    if model not in VALID_MODELS:
        errors.append(f"'model' must be one of: {', '.join(VALID_MODELS)}")
    device = cfg.get("device", "auto")
    if device not in VALID_DEVICES:
        errors.append(f"'device' must be one of: {', '.join(VALID_DEVICES)}")
    if model == "phi4" and device == "cpu":
        errors.append("phi4 requires GPU; use model=moondream2 for CPU inference")
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
# Model wrappers
# ---------------------------------------------------------------------------

class Moondream2:
    def __init__(self, device: str):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        print(f"Loading moondream2 on {device}…")
        dtype = "auto" if device == "cuda" else None
        self._model = AutoModelForCausalLM.from_pretrained(
            MOONDREAM_REPO,
            revision=MOONDREAM_REVISION,
            trust_remote_code=True,
            torch_dtype=dtype,
        ).to(device)
        self._model.eval()
        self._tokenizer = AutoTokenizer.from_pretrained(
            MOONDREAM_REPO, revision=MOONDREAM_REVISION, trust_remote_code=True
        )
        self._device = device

    def ask(self, image: Image.Image, question: str) -> str:
        enc = self._model.encode_image(image)
        return self._model.answer_question(enc, question, self._tokenizer)


class Phi4Multimodal:
    def __init__(self, device: str):
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor

        print(f"Loading Phi-4-multimodal on {device}…")
        self._processor = AutoProcessor.from_pretrained(PHI4_REPO, trust_remote_code=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            PHI4_REPO,
            trust_remote_code=True,
            torch_dtype="auto",
        ).to(device)
        self._model.eval()
        self._device = device

    def ask(self, image: Image.Image, question: str) -> str:
        import torch

        messages = [{"role": "user", "content": f"<|image_1|>\n{question}"}]
        prompt = self._processor.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._processor(prompt, [image], return_tensors="pt").to(self._device)
        with torch.no_grad():
            output = self._model.generate(
                **inputs, max_new_tokens=256, do_sample=False
            )
        decoded = self._processor.decode(
            output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )
        return decoded.strip()


def load_model(model_name: str, device: str):
    if model_name == "moondream2":
        return Moondream2(device)
    return Phi4Multimodal(device)


# ---------------------------------------------------------------------------
# Tag extraction (simple heuristic from description)
# ---------------------------------------------------------------------------

TAG_KEYWORDS = [
    "portrait", "landscape", "food", "coffee", "nature", "city", "architecture",
    "street", "people", "animal", "product", "fashion", "interior", "sunset",
    "beach", "forest", "night", "sport", "technology", "art",
]


def extract_tags(description: str, caption: str) -> list[str]:
    combined = (description + " " + caption).lower()
    return [kw for kw in TAG_KEYWORDS if kw in combined]


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process(config_path: Path) -> None:
    cfg = validate_config(load_config(config_path))

    input_dir = Path(cfg.get("input_dir", "./input"))
    output_dir = Path(cfg.get("output_dir", "./output"))
    model_name = cfg.get("model", "moondream2")
    prompt_desc = cfg.get("prompt_description", "Describe this image in one sentence.")
    prompt_cap = cfg.get(
        "prompt_caption",
        "Write an engaging Instagram caption for this image. Include 3-5 relevant hashtags.",
    )
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
    vlm = load_model(model_name, device)

    print(f"Processing {len(images)} image(s) with {model_name} on {device}…")
    print()

    succeeded, failed = 0, []

    for img_path in images:
        print(f"[{img_path.name}]")
        try:
            image = Image.open(img_path).convert("RGB")
            description = vlm.ask(image, prompt_desc)
            caption = vlm.ask(image, prompt_cap)
            tags = extract_tags(description, caption)

            out = {
                "description": description,
                "caption": caption,
                "tags": tags,
            }

            out_path = output_dir / (img_path.stem + ".json")
            with out_path.open("w") as f:
                json.dump(out, f, indent=2, ensure_ascii=False)

            print(f"  description: {description[:80]}{'…' if len(description) > 80 else ''}")
            print(f"  → {out_path}")
            succeeded += 1
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            failed.append(img_path.name)

    print()
    print(f"Done: {succeeded}/{len(images)} succeeded", end="")
    if failed:
        print(f", {len(failed)} failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="clawvlm — vision-language image captioner")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--input", help="Override input_dir")
    parser.add_argument("--output", help="Override output_dir")
    parser.add_argument("--model", choices=list(VALID_MODELS), help="Override model")
    parser.add_argument("--device", choices=list(VALID_DEVICES), help="Override device")
    parser.add_argument("--prompt-description", help="Override prompt_description")
    parser.add_argument("--prompt-caption", help="Override prompt_caption")
    args = parser.parse_args()

    cfg = validate_config(load_config(Path(args.config)))

    if args.input:
        cfg["input_dir"] = args.input
    if args.output:
        cfg["output_dir"] = args.output
    if args.model:
        cfg["model"] = args.model
    if args.device:
        cfg["device"] = args.device
    if args.prompt_description:
        cfg["prompt_description"] = args.prompt_description
    if args.prompt_caption:
        cfg["prompt_caption"] = args.prompt_caption

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
