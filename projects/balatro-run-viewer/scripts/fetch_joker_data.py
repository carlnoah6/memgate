#!/usr/bin/env python3
"""
Fetch Balatro joker data from Polychrome/data.json (GitHub),
add Chinese translations, download images.
Output: data/jokers.json
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
IMG_DIR = DATA_DIR / "joker_images"

POLYCHROME_URL = "https://raw.githubusercontent.com/dekkerglen/Polychrome/main/data.json"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_image(url, dest):
    """Download image, return True on success."""
    if dest.exists() and dest.stat().st_size > 100:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as e:
        print(f"  WARN: Failed to download {url}: {e}", file=sys.stderr)
        return False


def load_chinese_data():
    """Return dict of english_name -> {name_zh, effect_zh}"""
    p = Path(__file__).resolve().parent / "chinese_joker_data.json"
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching Polychrome data.json...")
    all_data = fetch_json(POLYCHROME_URL)

    # Filter to jokers only
    jokers_raw = [item for item in all_data if item.get("Type") == "Joker"]
    print(f"Found {len(jokers_raw)} jokers in Polychrome data")

    # Load Chinese translations
    zh_data = load_chinese_data()

    jokers = []
    for i, j in enumerate(jokers_raw):
        name = j["Name"]
        slug = name.lower().replace(" ", "_").replace("'", "").replace(".", "").replace("!", "").replace(",", "")

        # Image URL from Polychrome
        img_url = j.get("Appearance", "")
        img_ext = "png"
        img_filename = f"{slug}.{img_ext}"
        img_path = IMG_DIR / img_filename

        # Download image
        if img_url:
            ok = download_image(img_url, img_path)
            if not ok:
                img_filename = None
            time.sleep(0.1)  # be polite
        else:
            img_filename = None

        # Chinese data
        zh = zh_data.get(name, {})

        joker_entry = {
            "id": i + 1,
            "name_en": name,
            "name_zh": zh.get("name_zh", ""),
            "effect_en": j.get("Effect", ""),
            "effect_zh": zh.get("effect_zh", ""),
            "rarity": j.get("Rarity", ""),
            "cost": j.get("Cost", ""),
            "image": img_filename,
            "image_url": img_url,
        }
        jokers.append(joker_entry)

        if (i + 1) % 20 == 0:
            print(f"  Processed {i+1}/{len(jokers_raw)}...")

    # Write output
    out_path = DATA_DIR / "jokers.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(jokers, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {len(jokers)} jokers written to {out_path}")
    print(f"Images in {IMG_DIR}")

    # Stats
    with_zh = sum(1 for j in jokers if j["name_zh"])
    with_img = sum(1 for j in jokers if j["image"])
    print(f"  With Chinese name: {with_zh}/{len(jokers)}")
    print(f"  With image: {with_img}/{len(jokers)}")


if __name__ == "__main__":
    main()
