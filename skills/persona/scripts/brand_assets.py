#!/usr/bin/env python3
"""Brand asset management for Claw-Parade."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


SKILL_DIR = Path(__file__).parent.parent.resolve()
ASSETS_DIR = SKILL_DIR / "brand-assets"
IMAGES_DIR = ASSETS_DIR / "images"
FONTS_DIR = ASSETS_DIR / "fonts"
MANIFEST_PATH = ASSETS_DIR / "asset-manifest.json"

VALID_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
VALID_FONT_EXTENSIONS = {".ttf", ".otf", ".woff", ".woff2"}


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {
            "version": "1.0",
            "brand": "brand-awareness",
            "updated": datetime.now(timezone.utc).isoformat(),
            "images": [],
            "fonts": [],
        }
    with MANIFEST_PATH.open() as f:
        return json.load(f)


def save_manifest(manifest: dict) -> None:
    manifest["updated"] = datetime.now(timezone.utc).isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")


def find_by_name(manifest: dict, asset_type: str, name: str) -> dict | None:
    for asset in manifest.get(asset_type, []):
        if asset.get("name") == name:
            return asset
    return None


def find_by_tag(manifest: dict, asset_type: str, tag: str) -> list[dict]:
    return [
        asset for asset in manifest.get(asset_type, []) if tag in asset.get("tags", [])
    ]


def store_image(
    input_path: Path, name: str, tags: list[str], force: bool = False
) -> None:
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if input_path.suffix.lower() not in VALID_IMAGE_EXTENSIONS:
        print(
            f"Error: Invalid image extension: {', '.join(sorted(VALID_IMAGE_EXTENSIONS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    dest_name = f"{name}{input_path.suffix.lower()}"
    dest_path = IMAGES_DIR / dest_name

    if dest_path.exists() and not force:
        print(f"Error: Asset '{name}' exists. Use --force.", file=sys.stderr)
        sys.exit(1)

    shutil.copy2(input_path, dest_path)

    manifest = load_manifest()
    existing = find_by_name(manifest, "images", name)
    if existing:
        manifest["images"].remove(existing)

    manifest["images"].append(
        {
            "name": name,
            "path": f"images/{dest_name}",
            "tags": tags,
            "added": datetime.now(timezone.utc).isoformat(),
        }
    )

    save_manifest(manifest)
    print(f"Stored image: {name} -> {dest_path}")


def store_font(
    input_path: Path, name: str, tags: list[str], force: bool = False
) -> None:
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if input_path.suffix.lower() not in VALID_FONT_EXTENSIONS:
        print(
            f"Error: Invalid font extension: {', '.join(sorted(VALID_FONT_EXTENSIONS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    dest_name = f"{name}{input_path.suffix.lower()}"
    dest_path = FONTS_DIR / dest_name

    if dest_path.exists() and not force:
        print(f"Error: Asset '{name}' exists. Use --force.", file=sys.stderr)
        sys.exit(1)

    shutil.copy2(input_path, dest_path)

    manifest = load_manifest()
    existing = find_by_name(manifest, "fonts", name)
    if existing:
        manifest["fonts"].remove(existing)

    manifest["fonts"].append(
        {
            "name": name,
            "path": f"fonts/{dest_name}",
            "tags": tags,
            "added": datetime.now(timezone.utc).isoformat(),
        }
    )

    save_manifest(manifest)
    print(f"Stored font: {name} -> {dest_path}")


def list_assets(asset_type: str | None, tag: str | None) -> None:
    manifest = load_manifest()
    results: list[tuple[str, dict]] = []

    if asset_type in (None, "images"):
        for img in manifest.get("images", []):
            if tag is None or tag in img.get("tags", []):
                results.append(("image", img))

    if asset_type in (None, "fonts"):
        for font in manifest.get("fonts", []):
            if tag is None or tag in font.get("tags", []):
                results.append(("font", font))

    if not results:
        print("No assets found.")
        return

    print(f"Brand Assets ({len(results)}):\n")
    for atype, asset in results:
        print(f"  [{atype.upper()}] {asset['name']}")
        print(f"    Path: {ASSETS_DIR / asset['path']}")
        if asset.get("tags"):
            print(f"    Tags: {', '.join(asset['tags'])}")
        print()


def get_asset_path(name: str | None, tag: str | None) -> None:
    if not name and not tag:
        print("Error: Specify --name or --tag", file=sys.stderr)
        sys.exit(1)

    manifest = load_manifest()

    if name:
        asset = find_by_name(manifest, "images", name)
        if not asset:
            asset = find_by_name(manifest, "fonts", name)
        if asset:
            print(ASSETS_DIR / asset["path"])
            return
        print(f"Error: Asset '{name}' not found.", file=sys.stderr)
        sys.exit(1)

    if tag:
        assets = find_by_tag(manifest, "images", tag)
        if not assets:
            assets = find_by_tag(manifest, "fonts", tag)
        if assets:
            print(ASSETS_DIR / assets[0]["path"])
            return
        print(f"Error: No asset with tag '{tag}'.", file=sys.stderr)
        sys.exit(1)


def remove_asset(name: str) -> None:
    manifest = load_manifest()

    asset = find_by_name(manifest, "images", name)
    if asset:
        (ASSETS_DIR / asset["path"]).unlink(missing_ok=True)
        manifest["images"].remove(asset)
        save_manifest(manifest)
        print(f"Removed image: {name}")
        return

    asset = find_by_name(manifest, "fonts", name)
    if asset:
        (ASSETS_DIR / asset["path"]).unlink(missing_ok=True)
        manifest["fonts"].remove(asset)
        save_manifest(manifest)
        print(f"Removed font: {name}")
        return

    print(f"Error: Asset '{name}' not found.", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Brand asset management")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_store_image = subparsers.add_parser("store-image", help="Store a brand image")
    p_store_image.add_argument("--input", "-i", required=True, type=Path)
    p_store_image.add_argument("--name", "-n", required=True)
    p_store_image.add_argument("--tags", "-t", default="")
    p_store_image.add_argument("--force", "-f", action="store_true")

    p_store_font = subparsers.add_parser("store-font", help="Store a brand font")
    p_store_font.add_argument("--input", "-i", required=True, type=Path)
    p_store_font.add_argument("--name", "-n", required=True)
    p_store_font.add_argument("--tags", "-t", default="")
    p_store_font.add_argument("--force", "-f", action="store_true")

    p_list = subparsers.add_parser("list", help="List brand assets")
    p_list.add_argument("--type", choices=["images", "fonts"])
    p_list.add_argument("--tag", "-t")

    p_get = subparsers.add_parser("get-path", help="Get asset path")
    p_get.add_argument("--name", "-n")
    p_get.add_argument("--tag", "-t")

    p_remove = subparsers.add_parser("remove", help="Remove an asset")
    p_remove.add_argument("--name", "-n", required=True)

    args = parser.parse_args()
    tags = (
        [t.strip() for t in args.tags.split(",") if t.strip()]
        if hasattr(args, "tags")
        else []
    )

    match args.command:
        case "store-image":
            store_image(args.input, args.name, tags, args.force)
        case "store-font":
            store_font(args.input, args.name, tags, args.force)
        case "list":
            list_assets(args.type, args.tag)
        case "get-path":
            get_asset_path(args.name, args.tag)
        case "remove":
            remove_asset(args.name)


if __name__ == "__main__":
    main()
