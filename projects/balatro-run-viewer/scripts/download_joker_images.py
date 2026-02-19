#!/usr/bin/env python3
"""
Download Balatro joker images from Fandom wiki API.
Updates data/jokers.json with image filenames.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
IMG_DIR = DATA_DIR / "joker_images"
JOKERS_FILE = DATA_DIR / "jokers.json"

FANDOM_API = "https://balatrogame.fandom.com/api.php"

# Some jokers have different file names on the wiki
FILENAME_OVERRIDES = {
    "8 Ball": "8 Ball",
    "Séance": "Séance",
    "Oops! All 6s": "Oops! All 6s",
    "Mr. Bones": "Mr. Bones",
    "Driver's License": "Driver's License",
}


def fandom_get_image_urls(names):
    """Query Fandom API for image URLs. Max 50 titles per request."""
    results = {}
    batch_size = 50

    for i in range(0, len(names), batch_size):
        batch = names[i:i + batch_size]
        titles = "|".join(f"File:{n}.png" for n in batch)
        params = urllib.parse.urlencode({
            "action": "query",
            "titles": titles,
            "prop": "imageinfo",
            "iiprop": "url",
            "format": "json",
        })
        url = f"{FANDOM_API}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"  API error for batch {i}: {e}", file=sys.stderr)
            continue

        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if int(page_id) < 0:
                # Missing page
                continue
            title = page.get("title", "")
            # Extract name from "File:Name.png"
            name = title.replace("File:", "").replace(".png", "")
            imageinfo = page.get("imageinfo", [])
            if imageinfo:
                results[name] = imageinfo[0]["url"]

        time.sleep(0.3)

    return results


def download_image(url, dest):
    """Download image from Fandom static URL."""
    if dest.exists() and dest.stat().st_size > 100:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as e:
        print(f"  WARN: Failed to download {dest.name}: {e}", file=sys.stderr)
        return False


def main():
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    with open(JOKERS_FILE) as f:
        jokers = json.load(f)

    print(f"Loaded {len(jokers)} jokers from {JOKERS_FILE}")

    # Build list of wiki file names to query
    wiki_names = []
    name_to_idx = {}
    for i, j in enumerate(jokers):
        en = j["name_en"]
        wiki_name = FILENAME_OVERRIDES.get(en, en)
        wiki_names.append(wiki_name)
        name_to_idx[wiki_name] = i

    print("Querying Fandom API for image URLs...")
    url_map = fandom_get_image_urls(wiki_names)
    print(f"  Got {len(url_map)} image URLs")

    # Download images
    success = 0
    for wiki_name, url in url_map.items():
        idx = name_to_idx.get(wiki_name)
        if idx is None:
            # Try matching by normalized name
            for wn, i in name_to_idx.items():
                if wn.replace("_", " ") == wiki_name.replace("_", " "):
                    idx = i
                    break
        if idx is None:
            print(f"  WARN: No match for wiki name '{wiki_name}'", file=sys.stderr)
            continue

        j = jokers[idx]
        slug = j["name_en"].lower().replace(" ", "_").replace("'", "").replace(".", "").replace("!", "").replace(",", "").replace("é", "e")
        img_filename = f"{slug}.png"
        img_path = IMG_DIR / img_filename

        if download_image(url, img_path):
            j["image"] = img_filename
            j["image_url"] = url
            success += 1
        time.sleep(0.05)

    # Save updated jokers.json
    with open(JOKERS_FILE, "w", encoding="utf-8") as f:
        json.dump(jokers, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Downloaded {success}/{len(jokers)} images")
    print(f"Updated {JOKERS_FILE}")


if __name__ == "__main__":
    main()
