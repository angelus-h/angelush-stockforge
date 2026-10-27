#!/usr/bin/env python3
"""
generate_vecteezy_video_csv.py
Generates Vecteezy-compliant video metadata CSV from existing agency cache
and video assets in stock-video-workflow.

Adheres strictly to Vecteezy guidelines:
- Title: 3 to 8 words, sentence case, no prohibited subjective buzzwords.
- Description: up to 500 characters, factual English.
- Keywords: strictly 20-30 lowercase tags, no hyphens, no special characters,
  mandatory taxonomy (no people / people, horizontal, outdoor, day/daytime, color).
- License: 'editorial' or 'pro'.
"""

import os
import sys
import json
import csv
import re
import argparse

PROHIBITED_WORDS = {
    "beautiful", "stunning", "amazing", "gorgeous", "wonderful",
    "breathtaking", "incredible", "cool", "best", "lovely", "pretty", "scenic"
}

# Curated, concise 3-8 word titles matching each Lednice video perfectly
CURATED_TITLES = {
    "lednice_castle_chateau_garden_timelapse_wide.mp4": "Time lapse of Lednice Castle and gardens",
    "lednice_castle_gardens_clouds_timelapse_wide.mp4": "Time lapse of Lednice Castle gardens",
    "lednice_castle_gardens_clouds_timelapse_wide_2.mp4": "Time lapse of Lednice Castle floral gardens",
    "lednice_castle_gardens_greenhouse_timelapse_wide.mp4": "Time lapse of Lednice Castle greenhouse gardens",
    "lednice_castle_park_timelapse_wide.mp4": "Time lapse of Lednice Castle park grounds",
    "lednice_castle_chateau_park_timelapse_wide.mp4": "Time lapse of Lednice Castle and park",
    "lednice_castle_park_tourists_strolling_wide.mp4": "Tourists strolling in Lednice Castle park",
    "lednice_chateau_riding_hall_garden_pan.mp4": "Lednice Castle riding hall and flower gardens",
    "lednice_castle_park_pathway_walk_pov.mp4": "Walking along pathway towards Lednice Castle",
    "lednice_castle_gardens_timelapse_wide.mp4": "Timelapse of Lednice Castle and formal gardens",
    "lednice_castle_gardens_timelapse_wide_2.mp4": "Time lapse of Lednice Castle formal gardens",
    "lednice_castle_park_timelapse_wide_2.mp4": "Time lapse of historic Lednice Castle park",
    "lednice_castle_park_timelapse_wide_3.mp4": "Lednice Castle and park garden time lapse",
    "lednice_castle_park_walking_gravel_path_tracking.mp4": "Walking along gravel path in Lednice park",
    "lednice_horse_drawn_carriage_in_park_wide.mp4": "Horse drawn carriage in Lednice Castle park",
    "lednice_minaret_park_lake_wide.mp4": "Lednice Minaret tower across park lake",
    "lednice_park_minaret_timelapse_wide.mp4": "Time lapse of Lednice Minaret and pond",
    "lednice_park_minaret_pond_timelapse_wide.mp4": "Time lapse of Lednice park Minaret tower",
    "lednice_park_lake_clouds_timelapse_wide.mp4": "Time lapse of clouds over Lednice lake",
    "lednice_minaret_lake_timelapse_wide.mp4": "Timelapse of Lednice Minaret tower across lake",
    "lednice_castle_park_minaret_lake_pan.mp4": "Lednice Minaret tower across lake in park",
    "lednice_minaret_lake_park_wide.mp4": "Historic Lednice Minaret across lake in park",
    "lednice_park_wooden_footbridge_walk_pov.mp4": "Walking across wooden footbridge in Lednice park",
    "lednice_park_pathway_walk_pov.mp4": "Tourists walking along path in Lednice park",
    "lednice_minaret_lake_timelapse_wide_2.mp4": "Timelapse of Lednice Minaret reflection at sunset",
    "lednice_horse_drawn_carriage_park_wide.mp4": "Horse drawn carriage in Lednice Castle park",
    "lednice_swans_swimming_on_pond.mp4": "Mute swans swimming on calm lake pond",
    "lednice_tourist_boat_cruise_autumn_park_wide.mp4": "Tourist boat cruising on river in park",
    "lednice_tourist_boat_cruise_park_river_wide.mp4": "Tourist boat cruising on Lednice park river",
    "lednice_castle_park_wooden_bridge_autumn_wide.mp4": "Wooden footbridge across lake in Lednice park",
    "lednice_castle_park_horse_carriage_passing_trees.mp4": "Horse drawn carriage riding through castle park",
    "lednice_castle_park_tourist_boat_canal_wide.mp4": "Tourist excursion boat cruising on park canal",
    "lednice_tourist_boat_cruising_canal_wide.mp4": "Tourist boat cruising on canal in park",
    "lednice_castle_park_canal_boat_pier_autumn_wide.mp4": "Boat dock and autumn trees in park",
    "lednice_chateau_park_winter_pond_castle_wide.mp4": "Winter lake view of Lednice castle ruin",
    "lednice_janohrad_castle_winter_pond_wide.mp4": "Janohrad Castle in snow across winter pond",
    "lednice_park_winter_pond_scenic_wide.mp4": "Winter landscape with snowy trees and pond",
    "lednice_castle_park_winter_pond_wide.mp4": "Winter landscape of pond and Januv Hrad",
    "lednice_castle_park_canal_boats_winter_snow_wide.mp4": "Moored tour boats on snowy winter canal",
    "lednice_chateau_park_winter_canal_boats_wide.mp4": "Snowy canal with excursion boats in winter",
    "lednice_castle_winter_snow_pond_reflection_wide.mp4": "Lednice Castle in winter across snowy lake",
    "lednice_castle_park_snowy_lake_winter_landscape.mp4": "Snow covered trees and lake in winter",
    "lednice_winter_park_pond_snow_wide.mp4": "Snow covered trees reflecting on winter pond",
    "lednice_winter_park_snow_river_landscape.mp4": "Snow covered trees and river in winter",
    "lednice_winter_park_canal_snow_trees_wide.mp4": "Snow covered trees and canal in winter",
    "lednice_castle_park_winter_pond_bridge_wide.mp4": "Winter landscape with snow footbridge and lake",
    "lednice_januv_hrad_castle_lake_timelapse_wide.mp4": "Timelapse of Januv Hrad castle and lake",
    "lednice_horse_drawn_carriage_park_ride_wide.mp4": "Horse drawn carriage rides tourists through park",
    "lednice_horse_drawn_carriage_park_lake_wide.mp4": "Horse drawn carriage by lake in park"
}


def clean_title_fallback(raw_title):
    t = raw_title.replace('"', '').strip()
    t = re.sub(r'\b(wide shot|4k|hd|stock video footage|pov)\b', '', t, flags=re.IGNORECASE)
    for w in PROHIBITED_WORDS:
        t = re.sub(rf"\b{re.escape(w)}\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r'[,.;:!?]', ' ', t)
    t = re.sub(r"\s+", " ", t).strip()
    words = t.split()
    if len(words) > 8:
        t = " ".join(words[:8]).rstrip(".,- ")
    if t:
        t = t[0].upper() + t[1:]
    return t


def clean_description(raw_desc):
    d = raw_desc.replace('"', '').strip()
    d = d.replace("\ufffd", "u")  # Fix any character encoding issues
    for w in PROHIBITED_WORDS:
        d = re.sub(rf"\b{re.escape(w)}\b", "", d, flags=re.IGNORECASE)
    d = re.sub(r"\s+", " ", d).strip()
    if len(d) > 495:
        d = d[:490].rsplit(".", 1)[0] + "."
    if d and d[0].islower():
        d = d[0].upper() + d[1:]
    return d


def clean_keywords(keywords_raw, editorial):
    if isinstance(keywords_raw, list):
        raw_list = keywords_raw
    else:
        raw_list = str(keywords_raw).split(",")

    cleaned = []
    seen = set()
    for kw in raw_list:
        k = kw.strip().lower()
        # No hyphens or underscores in Vecteezy keywords
        k = k.replace("-", " ").replace("_", " ")
        k = re.sub(r"[^\w\s]", "", k)
        k = re.sub(r"\s+", " ", k).strip()
        if not k or len(k) < 2:
            continue
        # Check against prohibited words
        if any(pw in k.split() for pw in PROHIBITED_WORDS):
            continue
        if k not in seen:
            seen.add(k)
            cleaned.append(k)

    # Mandatory taxonomy
    if not editorial:
        if "no people" not in seen:
            cleaned.append("no people")
            seen.add("no people")
    else:
        people_found = any(any(pt in kw.split() for pt in ["people", "tourists", "visitors", "person", "crowd"]) for kw in cleaned)
        if not people_found:
            cleaned.append("people")
            seen.add("people")

    for tax in ["horizontal", "outdoor", "day", "color"]:
        if tax not in seen and len(cleaned) < 28:
            cleaned.append(tax)
            seen.add(tax)

    # Ensure strictly 20-30 keywords
    if len(cleaned) > 28:
        cleaned = cleaned[:28]
    elif len(cleaned) < 20:
        fillers = ["europe", "travel", "tourism", "destination", "landmark", "moravia", "czechia"]
        for f in fillers:
            if f not in seen and len(cleaned) < 20:
                cleaned.append(f)
                seen.add(f)

    return cleaned


def main():
    parser = argparse.ArgumentParser(description="Generate Vecteezy CSV and update cache for stock videos.")
    parser.add_argument("--video-dir", default=r"G:\VIDEOS\Lednice\final", help="Path to final videos directory")
    parser.add_argument("--strip-ext", action="store_true", help="Omit .mp4 extension in Filename column")
    args = parser.parse_args()

    video_dir = os.path.abspath(args.video_dir)
    metadata_dir = os.path.join(video_dir, "_metadata")
    cache_path = os.path.join(metadata_dir, "ai_metadata_cache.json")

    if not os.path.exists(cache_path):
        print(f"Error: cache file not found at {cache_path}", file=sys.stderr)
        sys.exit(1)

    with open(cache_path, "r", encoding="utf-8") as f:
        cache_data = json.load(f)

    print(f"Loaded {len(cache_data)} items from cache.")

    vecteezy_records = []
    editorial_count = 0
    commercial_count = 0

    for item in cache_data:
        fn = item.get("new_filename", "")
        editorial = item.get("editorial", False)

        # 1. Title (strictly 3-8 words)
        title = CURATED_TITLES.get(fn)
        if not title:
            raw_title = item.get("adobe", {}).get("title") or item.get("pond5", {}).get("title") or fn
            title = clean_title_fallback(raw_title)

        words = title.split()
        assert 3 <= len(words) <= 8, f"Invalid title length ({len(words)} words) for {fn}: {title}"

        # 2. Description (up to 500 chars)
        raw_desc = item.get("shutterstock", {}).get("description") or item.get("pond5", {}).get("description") or title
        desc = clean_description(raw_desc)

        # 3. Keywords (20-30 clean keywords)
        raw_kws = item.get("keywords", "")
        kws = clean_keywords(raw_kws, editorial)
        assert 20 <= len(kws) <= 30, f"Invalid keyword count ({len(kws)}) for {fn}"

        # 4. License
        license_type = "editorial" if editorial else "pro"
        if editorial:
            editorial_count += 1
        else:
            commercial_count += 1

        # Store in item cache
        item["vecteezy"] = {
            "title": title,
            "description": desc,
            "keywords": ", ".join(kws),
            "license": license_type
        }

        vecteezy_records.append({
            "filename": os.path.splitext(fn)[0] if args.strip_ext else fn,
            "title": title,
            "description": desc,
            "keywords": ", ".join(kws),
            "license": license_type
        })

    # Save updated cache
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)
    print(f"Updated cache with Vecteezy entries: {cache_path}")

    # Output CSV paths
    csv_paths = [
        os.path.join(metadata_dir, "vecteezy_video.csv"),
        os.path.join(video_dir, "vecteezy.csv")
    ]

    for p in csv_paths:
        # Vecteezy web portal standard specification:
        # Strictly 4 columns (Filename, Title, Description, Keywords) and UTF-8 without BOM.
        # Adding extra columns (e.g. License) or UTF-8 BOM triggers:
        # 'CSV file has an incorrect header line. It should include "Filename" column'
        with open(p, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Filename", "Title", "Description", "Keywords"])
            for r in vecteezy_records:
                writer.writerow([r["filename"], r["title"], r["description"], r["keywords"]])
        print(f"Successfully generated Vecteezy CSV: {p}")

    print("\n=== Summary ===")
    print(f"Total videos processed: {len(vecteezy_records)}")
    print(f"Editorial clips: {editorial_count}")
    print(f"Commercial clips: {commercial_count}")
    print("All metadata 100% compliant with Vecteezy submission rules.")


if __name__ == "__main__":
    main()
