#!/usr/bin/env python3
"""
pod_metadata_generator.py
Generates high-converting SEO titles, 3-paragraph emotional sales descriptions,
and character-compliant keyword tags (< 500 chars) for Fine Art America (FAA)
and Print-on-Demand (POD) platforms based on the FAA-prompt.txt guidelines.
"""

import os
import json
import csv
import argparse


def build_faa_item(meta):
    filename = meta["filename"]
    title = meta["title"]
    location = meta.get("location", "Hardegg, Lower Austria, Austria")
    medium = meta.get("medium", "Fine Art Photography")
    visual_elements = meta.get("visual_elements", "")
    dominant_colors = meta.get("dominant_colors", "")
    mood = meta.get("mood", "peaceful, historic, serene")
    rooms = meta.get("rooms", "Living Room, Master Bedroom, Home Office, Executive Suite")

    # 1. Optimized Title (SEO + Decor friendly)
    opt_title = meta.get("optimized_title", title)

    # 2. Sales Description (3 paragraphs)
    desc_p1 = meta.get("desc_p1") or f"This fine art photograph captures the timeless majesty of {visual_elements} in {location}. The composition evokes a deep sense of {mood}, bathing the historic architecture and surrounding nature in natural, atmospheric light. It brings the serene beauty of the Austrian landscape directly into your interior, creating an immediate focal point of elegance and tranquility."
    desc_p2 = meta.get("desc_p2") or f"Perfect for elevating the ambiance of a {rooms}, or professional spaces such as a serene executive office, boutique hotel lobby, or modern healthcare waiting room. The {dominant_colors} harmonize beautifully with both contemporary and traditional interior design palettes, infusing any space with warmth, sophistication, and a calming connection to European heritage."
    desc_p3 = f"Printed to museum-grade standards, this artwork is available in premium formats including archival canvas, framed gallery prints, sleek acrylic, and modern metal prints. Each piece is custom produced by Fine Art America's global fulfillment centers and backed by a 30-day money-back guarantee. Original fine art photography by Angelus H."

    sales_description = f"{desc_p1}\n\n{desc_p2}\n\n{desc_p3}"

    # 3. Comma-separated tags (Strict limit < 500 characters)
    raw_tags = meta.get("tags", [])
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

    # Ensure tags fit within 490 chars
    final_tags_list = []
    char_count = 0
    for tag in raw_tags:
        t_clean = tag.strip().lower()
        if not t_clean:
            continue
        add_len = len(t_clean) + (2 if final_tags_list else 0)
        if char_count + add_len <= 485:
            final_tags_list.append(t_clean)
            char_count += add_len
        else:
            break

    comma_separated_tags = ", ".join(final_tags_list)

    return {
        "filename": filename,
        "optimized_title": opt_title,
        "sales_description": sales_description,
        "comma_separated_tags": comma_separated_tags,
        "tags_length": len(comma_separated_tags),
        "location": location,
        "medium": medium,
        "dominant_colors": dominant_colors
    }


def process_faa_dataset(input_json, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    with open(input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []
    for item in data:
        res = build_faa_item(item)
        results.append(res)

    # Save JSON
    out_json_path = os.path.join(output_dir, "faa_metadata_results.json")
    with open(out_json_path, "w", encoding="utf-8") as jf:
        json.dump(results, jf, indent=2, ensure_ascii=False)

    # Save CSV
    out_csv_path = os.path.join(output_dir, "faa_metadata_results.csv")
    with open(out_csv_path, "w", newline="", encoding="utf-8") as cf:
        writer = csv.writer(cf)
        writer.writerow(["Filename", "Title", "Description", "Keywords", "Location", "Medium"])
        for r in results:
            writer.writerow([
                r["filename"],
                r["optimized_title"],
                r["sales_description"],
                r["comma_separated_tags"],
                r["location"],
                r["medium"]
            ])

    print(f"Successfully generated FAA metadata for {len(results)} artworks!")
    print(f"JSON: {out_json_path}")
    print(f"CSV:  {out_csv_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate FAA and POD metadata based on FAA-prompt.txt guidelines.")
    parser.add_argument("--json", "-j", required=True, help="Input JSON file with artwork metadata definitions")
    parser.add_argument("--output", "-o", required=True, help="Output directory for FAA results")
    args = parser.parse_args()

    process_faa_dataset(args.json, args.output)
