#!/usr/bin/env python3
"""
generate_stock_csv.py
Generates compliant metadata CSV files for Adobe Stock and Shutterstock.
Outputs:
1. 'adobe_stock.csv' (batch upload format)
2. 'shutterstock.csv' (batch upload format)
3. Individual per-image CSV files (<filename>_adobe.csv, <filename>_shutterstock.csv)
"""

import os
import csv
import json
import argparse


ADOBE_CATEGORIES = {
    "1": "Animals",
    "2": "Buildings and Architecture",
    "3": "Business",
    "4": "Drinks",
    "5": "The Environment",
    "6": "States of Mind",
    "7": "Food",
    "8": "Graphic Resources",
    "9": "Hobbies and Leisure",
    "10": "Industry",
    "11": "Landscapes",
    "12": "Lifestyle",
    "13": "People",
    "14": "Plants and Flowers",
    "15": "Culture and Religion",
    "16": "Science",
    "17": "Social Issues",
    "18": "Sports",
    "19": "Technology",
    "20": "Transport",
    "21": "Travel"
}


def clean_keywords(keywords_input):
    if isinstance(keywords_input, str):
        kws = [k.strip() for k in keywords_input.split(",") if k.strip()]
    elif isinstance(keywords_input, list):
        kws = [str(k).strip() for k in keywords_input if str(k).strip()]
    else:
        kws = []
    
    # Deduplicate preserving order
    seen = set()
    cleaned = []
    for k in kws:
        k_lower = k.lower()
        if k_lower not in seen:
            seen.add(k_lower)
            cleaned.append(k)
    return cleaned


def generate_csvs(items, output_dir, generate_individual=True):
    os.makedirs(output_dir, exist_ok=True)

    # 1. Adobe Stock Batch CSV
    adobe_batch_path = os.path.join(output_dir, "adobe_stock.csv")
    with open(adobe_batch_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Filename", "Title", "Keywords", "Category", "Releases"])
        for item in items:
            filename = item["filename"]
            title = item.get("adobe_title") or item.get("title") or item.get("description", "")
            # Clean title (no quotes inside unescaped)
            title = title.replace('"', '').strip()
            keywords = clean_keywords(item.get("keywords", []))
            category = str(item.get("adobe_category", "2"))
            releases = item.get("releases", "")
            
            writer.writerow([filename, title, ", ".join(keywords), category, releases])

    print(f"Generated Adobe Stock batch CSV: {adobe_batch_path}")

    # 2. Shutterstock Batch CSV
    shutterstock_batch_path = os.path.join(output_dir, "shutterstock.csv")
    with open(shutterstock_batch_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Filename", "Description", "Keywords", "Categories", "Illustration", "Mature content", "Editorial"])
        for item in items:
            filename = item["filename"]
            desc = item.get("shutterstock_description") or item.get("description") or item.get("title", "")
            desc = desc.replace('"', '').strip()
            keywords = clean_keywords(item.get("keywords", []))
            categories = item.get("shutterstock_categories", "Buildings/Landmarks, Travel")
            illustration = item.get("illustration", "no")
            mature = item.get("mature", "no")
            editorial = "yes" if str(item.get("editorial", "")).lower() in ["yes", "true", "1", "y"] else "no"

            writer.writerow([filename, desc, ", ".join(keywords), categories, illustration, mature, editorial])

    print(f"Generated Shutterstock batch CSV: {shutterstock_batch_path}")

    # 3. Individual CSVs
    if generate_individual:
        for item in items:
            filename = item["filename"]
            base_name = os.path.splitext(filename)[0]
            keywords_str = ", ".join(clean_keywords(item.get("keywords", [])))
            
            # Adobe single
            single_adobe = os.path.join(output_dir, f"{base_name}_adobe.csv")
            with open(single_adobe, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Filename", "Title", "Keywords", "Category", "Releases"])
                title = (item.get("adobe_title") or item.get("title", "")).replace('"', '').strip()
                writer.writerow([filename, title, keywords_str, str(item.get("adobe_category", "2")), item.get("releases", "")])

            # Shutterstock single
            single_shutter = os.path.join(output_dir, f"{base_name}_shutterstock.csv")
            with open(single_shutter, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Filename", "Description", "Keywords", "Categories", "Illustration", "Mature content", "Editorial"])
                desc = (item.get("shutterstock_description") or item.get("description", "")).replace('"', '').strip()
                editorial = "yes" if str(item.get("editorial", "")).lower() in ["yes", "true", "1", "y"] else "no"
                writer.writerow([
                    filename,
                    desc,
                    keywords_str,
                    item.get("shutterstock_categories", "Buildings/Landmarks, Travel"),
                    item.get("illustration", "no"),
                    item.get("mature", "no"),
                    editorial
                ])

        print(f"Generated individual per-image CSVs ({len(items)} images) in {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Generate Adobe Stock and Shutterstock CSV files from JSON metadata.")
    parser.add_argument("--json", "-j", required=True, help="Path to input JSON file containing image data list")
    parser.add_argument("--output", "-o", required=True, help="Output directory to save CSV files")
    parser.add_argument("--no-individual", action="store_true", help="Skip generating per-image individual CSV files")

    args = parser.parse_args()

    with open(args.json, "r", encoding="utf-8") as f:
        items = json.load(f)

    generate_csvs(items, args.output, generate_individual=not args.no_individual)


if __name__ == "__main__":
    main()
