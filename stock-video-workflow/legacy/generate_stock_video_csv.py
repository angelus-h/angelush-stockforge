#!/usr/bin/env python3
"""
generate_stock_video_csv.py
Generates compliant metadata CSV files for Adobe Stock, Shutterstock, and Pond5
specifically tailored for Stock Video Footage.
"""

import os
import csv
import json
import argparse


def clean_keywords(keywords_input):
    if isinstance(keywords_input, str):
        kws = [k.strip() for k in keywords_input.split(",") if k.strip()]
    elif isinstance(keywords_input, list):
        kws = [str(k).strip() for k in keywords_input if str(k).strip()]
    else:
        kws = []
    
    seen = set()
    cleaned = []
    for k in kws:
        k_lower = k.lower()
        if k_lower not in seen:
            seen.add(k_lower)
            cleaned.append(k)
    return cleaned


def generate_video_csvs(items, output_dir, generate_individual=True):
    os.makedirs(output_dir, exist_ok=True)

    # 1. Adobe Stock Video Batch CSV
    adobe_csv_path = os.path.join(output_dir, "adobe_stock_video.csv")
    with open(adobe_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Filename", "Title", "Keywords", "Category", "Releases"])
        for item in items:
            title = (item.get("adobe_title") or item.get("title") or item.get("description", "")).replace('"', '').strip()
            kw_str = ", ".join(clean_keywords(item.get("keywords", [])))
            cat = str(item.get("adobe_category", "20")) # 20 = Transport, 21 = Travel, 14 = Plants
            writer.writerow([item["filename"], title, kw_str, cat, ""])
    print(f"Generated Adobe Stock video CSV: {adobe_csv_path}")

    # 2. Shutterstock Video Batch CSV
    shutter_csv_path = os.path.join(output_dir, "shutterstock_video.csv")
    with open(shutter_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Filename", "Description", "Keywords", "Categories", "Illustration", "Mature content", "Editorial"])
        for item in items:
            desc = (item.get("shutterstock_description") or item.get("description") or item.get("title", "")).replace('"', '').strip()
            kw_str = ", ".join(clean_keywords(item.get("keywords", [])))
            cat = item.get("shutterstock_categories", "Transportation, Travel")
            editorial = "yes" if str(item.get("editorial", "")).lower() in ["yes", "true", "1", "y"] else "no"
            writer.writerow([item["filename"], desc, kw_str, cat, "no", "no", editorial])
    print(f"Generated Shutterstock video CSV: {shutter_csv_path}")

    # 3. Pond5 Video Batch CSV
    pond5_csv_path = os.path.join(output_dir, "pond5_video.csv")
    with open(pond5_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["originalfilename", "title", "description", "keywords", "editorial"])
        for item in items:
            title = (item.get("title") or item.get("adobe_title", "")).replace('"', '').strip()
            desc = (item.get("pond5_description") or item.get("shutterstock_description") or item.get("description", "")).replace('"', '').strip()
            kw_str = ", ".join(clean_keywords(item.get("keywords", [])))
            editorial = "yes" if str(item.get("editorial", "")).lower() in ["yes", "true", "1", "y"] else "no"
            writer.writerow([item["filename"], title, desc, kw_str, editorial])
    print(f"Generated Pond5 video CSV: {pond5_csv_path}")

    # 4. Individual CSVs
    if generate_individual:
        for item in items:
            filename = item["filename"]
            base_name = os.path.splitext(filename)[0]
            kw_str = ", ".join(clean_keywords(item.get("keywords", [])))
            editorial = "yes" if str(item.get("editorial", "")).lower() in ["yes", "true", "1", "y"] else "no"

            # Adobe single
            with open(os.path.join(output_dir, f"{base_name}_adobe.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Filename", "Title", "Keywords", "Category", "Releases"])
                title = (item.get("adobe_title") or item.get("title", "")).replace('"', '').strip()
                w.writerow([filename, title, kw_str, str(item.get("adobe_category", "20")), ""])

            # Shutterstock single
            with open(os.path.join(output_dir, f"{base_name}_shutterstock.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Filename", "Description", "Keywords", "Categories", "Illustration", "Mature content", "Editorial"])
                desc = (item.get("shutterstock_description") or item.get("description", "")).replace('"', '').strip()
                w.writerow([filename, desc, kw_str, item.get("shutterstock_categories", "Transportation, Travel"), "no", "no", editorial])

            # Pond5 single
            with open(os.path.join(output_dir, f"{base_name}_pond5.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["originalfilename", "title", "description", "keywords", "editorial"])
                title = (item.get("title") or item.get("adobe_title", "")).replace('"', '').strip()
                desc = (item.get("pond5_description") or item.get("shutterstock_description", "")).replace('"', '').strip()
                w.writerow([filename, title, desc, kw_str, editorial])

        print(f"Generated individual per-video CSVs ({len(items)} videos) in {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Generate Adobe Stock, Shutterstock, and Pond5 CSV files from video metadata JSON.")
    parser.add_argument("--json", "-j", required=True, help="Path to JSON file with video entries")
    parser.add_argument("--output", "-o", required=True, help="Output directory to save CSV files")
    parser.add_argument("--no-individual", action="store_true", help="Skip generating per-video individual CSV files")

    args = parser.parse_args()

    with open(args.json, "r", encoding="utf-8") as f:
        items = json.load(f)

    generate_video_csvs(items, args.output, generate_individual=not args.no_individual)


if __name__ == "__main__":
    main()
