#!/usr/bin/env python3
"""
generate_stock_csv.py
Generates compliant metadata CSV files for Adobe Stock, Shutterstock, and Vecteezy.
Outputs:
1. 'adobe_stock.csv' (batch upload format)
2. 'shutterstock.csv' (batch upload format)
3. 'vecteezy.csv' (batch upload format - 5 columns)
4. Individual per-image CSV files (<filename>_adobe.csv, <filename>_shutterstock.csv, <filename>_vecteezy.csv)
"""

import os
import csv
import json
import re
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


VECTEEZY_PROHIBITED_WORDS = [
    "beautiful", "stunning", "amazing", "gorgeous", "wonderful",
    "breathtaking", "incredible", "cool", "best", "lovely", "pretty"
]


def clean_vecteezy_title(raw_title):
    t = raw_title.replace('"', '').strip()
    for w in VECTEEZY_PROHIBITED_WORDS:
        t = re.sub(rf"\b{re.escape(w)}\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    words = t.split()
    if len(words) > 8:
        t = " ".join(words[:8]).rstrip(".,- ")
    if t:
        t = t[0].upper() + t[1:]
    return t


def clean_vecteezy_keywords(keywords_input):
    raw_list = clean_keywords(keywords_input)
    cleaned = []
    seen = set()
    for kw in raw_list:
        k = kw.strip().lower()
        k = k.replace("-", " ").replace("_", " ")
        k = re.sub(r"[^\w\s]", "", k)
        k = re.sub(r"\s+", " ", k).strip()
        if not k or len(k) < 2:
            continue
        if any(pw in k.split() for pw in VECTEEZY_PROHIBITED_WORDS):
            continue
        if k not in seen:
            seen.add(k)
            cleaned.append(k)

    people_terms = {"person", "people", "man", "woman", "girl", "boy", "child", "crowd", "face", "portrait", "human"}
    has_people = any(any(pt in kw.split() for pt in people_terms) for kw in cleaned)
    if not has_people and "no people" not in seen and len(cleaned) < 30:
        seen.add("no people")
        cleaned.append("no people")

    return cleaned[:30]


def generate_csvs(items, output_dir, generate_individual=True, strip_vecteezy_ext=False, default_vecteezy_license="pro"):
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

    # 3. Vecteezy Batch CSV (5 columns: Filename, Title, Description, Keywords, License)
    vecteezy_batch_path = os.path.join(output_dir, "vecteezy.csv")
    with open(vecteezy_batch_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Filename", "Title", "Description", "Keywords", "License"])
        for item in items:
            raw_fn = item["filename"]
            fn = os.path.splitext(raw_fn)[0] if strip_vecteezy_ext else raw_fn
            raw_title = (
                item.get("vecteezy_title")
                or item.get("title")
                or item.get("adobe_title")
                or item.get("shutterstock_description")
                or item.get("description", "")
            )
            title = clean_vecteezy_title(raw_title)
            desc = (
                item.get("vecteezy_description")
                or item.get("description")
                or item.get("shutterstock_description")
                or item.get("adobe_title")
                or item.get("title", "")
            ).replace('"', '').strip()
            keywords = clean_vecteezy_keywords(item.get("keywords", []))
            raw_license = str(item.get("vecteezy_license") or item.get("license") or default_vecteezy_license).lower().strip()
            license_val = raw_license if raw_license in ["pro", "free", "editorial"] else default_vecteezy_license

            writer.writerow([fn, title, desc, ", ".join(keywords), license_val])

    print(f"Generated Vecteezy batch CSV: {vecteezy_batch_path}")

    # 4. Individual CSVs
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

            # Vecteezy single
            single_vecteezy = os.path.join(output_dir, f"{base_name}_vecteezy.csv")
            with open(single_vecteezy, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Filename", "Title", "Description", "Keywords", "License"])
                fn = base_name if strip_vecteezy_ext else filename
                raw_title = (
                    item.get("vecteezy_title")
                    or item.get("title")
                    or item.get("adobe_title")
                    or item.get("shutterstock_description")
                    or item.get("description", "")
                )
                title = clean_vecteezy_title(raw_title)
                desc = (
                    item.get("vecteezy_description")
                    or item.get("description")
                    or item.get("shutterstock_description")
                    or item.get("adobe_title")
                    or item.get("title", "")
                ).replace('"', '').strip()
                vkws = clean_vecteezy_keywords(item.get("keywords", []))
                raw_license = str(item.get("vecteezy_license") or item.get("license") or default_vecteezy_license).lower().strip()
                license_val = raw_license if raw_license in ["pro", "free", "editorial"] else default_vecteezy_license
                writer.writerow([fn, title, desc, ", ".join(vkws), license_val])

        print(f"Generated individual per-image CSVs ({len(items)} images) in {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Generate Adobe Stock, Shutterstock, and Vecteezy CSV files from JSON metadata.")
    parser.add_argument("--json", "-j", required=True, help="Path to input JSON file containing image data list")
    parser.add_argument("--output", "-o", required=True, help="Output directory to save CSV files")
    parser.add_argument("--no-individual", action="store_true", help="Skip generating per-image individual CSV files")
    parser.add_argument("--strip-vecteezy-ext", action="store_true", help="Strip file extension for Vecteezy CSV (recommended for SFTP upload)")
    parser.add_argument("--vecteezy-license", default="pro", choices=["pro", "free", "editorial"], help="Default Vecteezy license (pro, free, editorial)")

    args = parser.parse_args()

    with open(args.json, "r", encoding="utf-8") as f:
        items = json.load(f)

    generate_csvs(
        items,
        args.output,
        generate_individual=not args.no_individual,
        strip_vecteezy_ext=args.strip_vecteezy_ext,
        default_vecteezy_license=args.vecteezy_license
    )


if __name__ == "__main__":
    main()
