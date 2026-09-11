#!/usr/bin/env python3
"""
audit_lednice_editorial.py
Audits all videos in /run/media/mgreczi/SSD/VIDEOS/Lednice/ using Gemini Vision
specifically looking for any humans/people/tourists in the 5-frame filmstrips.
Updates editorial=True where people are detected, formats agency metadata,
and regenerates all 4 agency CSVs.
"""

import os
import sys
import json
import csv
import re
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import google.generativeai as genai
from PIL import Image

LEDNICE_DIR = "/run/media/mgreczi/SSD/VIDEOS/Lednice"
METADATA_DIR = os.path.join(LEDNICE_DIR, "_metadata")
FRAMES_DIR = os.path.join(LEDNICE_DIR, "_temp_frames")
CACHE_FILE = os.path.join(METADATA_DIR, "ai_metadata_cache.json")
BACKUP_FILE = os.path.join(METADATA_DIR, "ai_metadata_cache.json.bak")
AUDIT_CACHE_FILE = os.path.join(METADATA_DIR, "people_audit_cache.json")
VMETA_FILE = os.path.join(FRAMES_DIR, "video_metadata_summary.json")

def format_editorial_date(date_str):
    if not date_str or date_str == "Unknown":
        return "September 29, 2024"
    try:
        dt = datetime.strptime(date_str.split(' ')[0], "%Y-%m-%d")
        return dt.strftime("%B %d, %Y")
    except Exception:
        return "September 29, 2024"

def format_pond5_editorial_date(date_str):
    if not date_str or date_str == "Unknown":
        return "2024/09/29"
    try:
        dt = datetime.strptime(date_str.split(' ')[0], "%Y-%m-%d")
        return dt.strftime("%Y/%m/%d")
    except Exception:
        return "2024/09/29"

def setup_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    genai.configure(api_key=api_key)
    
    generation_config = {
        "temperature": 0.2,
        "top_p": 0.9,
        "max_output_tokens": 2048,
        "response_mime_type": "application/json"
    }
    return genai.GenerativeModel("gemini-flash-latest", generation_config=generation_config)

def detect_people_in_filmstrip(model, filmstrip_path, item_name):
    prompt = """
Analyze the 5 frames in this filmstrip very carefully and strictly.
Our goal is to determine whether ANY human beings appear in ANY form in ANY of the frames.
Stock agencies reject commercial submissions if any person is visible without a signed model release.

Check for:
1. Tourists, visitors, walkers, strollers, cyclists, joggers
2. People sitting on benches, standing in courtyards or gardens
3. People in the background, distant figures, silhouettes, shadows with recognizable human shape
4. Passengers or crew/drivers in boats on canals or lakes
5. Drivers or passengers in horse-drawn carriages
6. Partial human body parts: hands holding cameras/phones, legs or bodies entering the frame, walking POV where limbs or reflections are visible
7. Any blurred or motion-blurred human figures

Respond strictly in JSON:
{
  "people_visible": true or false,
  "confidence": "high" or "medium" or "low",
  "explanation": "concise explanation of where and who the people are, or explicit confirmation that no human is present",
  "editorial_description": "If people_visible is true: write a factual English description answering Who, What, Where, When, Why (e.g. Tourists walk along a tree-lined avenue in Lednice Castle Park). If false: empty string"
}
"""
    for attempt in range(3):
        try:
            img = Image.open(filmstrip_path)
            res = model.generate_content([prompt, img])
            text = res.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            data = json.loads(text.strip())
            return data
        except Exception as e:
            time.sleep((attempt + 1) * 3)
    return None

def main():
    print("=== Starting Lednice Editorial & People Audit ===")
    
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache_data = json.load(f)
    print(f"Loaded cache data: {len(cache_data)} items")
    
    with open(VMETA_FILE, "r", encoding="utf-8") as f:
        vmeta_data = json.load(f)
    vmeta_lookup = {item["filename"]: item for item in vmeta_data}

    # Backup cache if not yet backed up
    if not os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        print(f"Backup created at {BACKUP_FILE}")

    audit_cache = {}
    if os.path.exists(AUDIT_CACHE_FILE):
        try:
            with open(AUDIT_CACHE_FILE, "r", encoding="utf-8") as f:
                audit_cache = json.load(f)
        except Exception:
            audit_cache = {}

    model = setup_gemini()
    
    # Audit each item
    updated_to_editorial = 0
    already_editorial = 0
    kept_commercial = 0

    items_to_check = []
    for idx, item in enumerate(cache_data):
        orig_fn = item.get("original_filename", "")
        new_fn = item.get("new_filename", orig_fn)
        base_orig = os.path.splitext(orig_fn)[0]
        
        # Find matching filmstrip
        filmstrip_name = f"{base_orig}_filmstrip.jpg"
        filmstrip_path = os.path.join(FRAMES_DIR, filmstrip_name)
        if not os.path.exists(filmstrip_path):
            # Try searching in frames dir
            for fs in os.listdir(FRAMES_DIR):
                if fs.startswith(base_orig) and fs.endswith("_filmstrip.jpg"):
                    filmstrip_path = os.path.join(FRAMES_DIR, fs)
                    break
        
        items_to_check.append((idx, item, orig_fn, new_fn, filmstrip_path))

    import threading
    audit_lock = threading.Lock()

    def get_audit_result(task_info):
        idx, item, orig_fn, new_fn, fs_path = task_info
        if item.get("editorial", False):
            return new_fn, {"people_visible": True, "already": True}
        if not os.path.exists(fs_path):
            return new_fn, {"people_visible": False, "missing": True}
        
        with audit_lock:
            if new_fn in audit_cache:
                return new_fn, audit_cache[new_fn]
                
        res = detect_people_in_filmstrip(model, fs_path, new_fn)
        if res:
            with audit_lock:
                audit_cache[new_fn] = res
                with open(AUDIT_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(audit_cache, f, indent=2, ensure_ascii=False)
        return new_fn, res

    print(f"\nAnalyzing {len(items_to_check)} videos with ThreadPoolExecutor (5 workers)...")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(get_audit_result, t): t for t in items_to_check}
        for future in as_completed(futures):
            t = futures[future]
            new_fn, res = future.result()
            if res and res.get("people_visible") and not res.get("already"):
                print(f"[FOUND] People in {new_fn}: {res.get('explanation')}")

    # Now apply the results in order
    for idx, item, orig_fn, new_fn, fs_path in items_to_check:
        is_ed = item.get("editorial", False)
        if is_ed:
            already_editorial += 1
            continue
            
        audit_res = audit_cache.get(new_fn)
        if audit_res and audit_res.get("people_visible"):
            updated_to_editorial += 1
            item["editorial"] = True
            
            # Update descriptions and platform metadata to Editorial
            vid_meta = vmeta_lookup.get(orig_fn, {})
            date_rec = vid_meta.get("date_recorded", "2024-09-29 12:00:00")
            city = "Lednice"
            country = "Czech Republic"
            ed_date = format_editorial_date(date_rec)
            p5_date = format_pond5_editorial_date(date_rec)
            
            # Detailed base description from audit or existing
            new_ed_desc = audit_res.get("editorial_description", "").strip()
            if not new_ed_desc:
                new_ed_desc = item.get("shutterstock", {}).get("description", "").strip()
                new_ed_desc = re.sub(r'^[A-Za-z\s/,-]+-\s*[A-Za-z]+\s+\d{1,2},\s*\d{4}:\s*', '', new_ed_desc)
            if not new_ed_desc:
                new_ed_desc = "Visitors explore the historic park and grounds of Lednice Castle."

            if not any(k in new_ed_desc.lower() for k in ["tourist", "visitor", "people", "walk", "passenger", "carriage"]):
                new_ed_desc = f"Tourists and visitors explore the area: {new_ed_desc}"

            # Shutterstock
            shutter_desc = f"{city}, {country} - {ed_date}: {new_ed_desc}"
            shutter_cats = item.get("shutterstock", {}).get("categories", "nature,buildings/landmarks")
            if "people" not in shutter_cats:
                cat_parts = [c.strip() for c in shutter_cats.split(",") if c.strip()]
                if cat_parts:
                    shutter_cats = f"people,{cat_parts[0]}"
                else:
                    shutter_cats = "people,nature"
            item.setdefault("shutterstock", {})["description"] = shutter_desc
            item["shutterstock"]["categories"] = shutter_cats
            
            # Pond5
            p5_prefix = f"{city}, {country} {p5_date}: "
            short_action = re.sub(r'[,.;:!?"]', '', new_ed_desc)
            if len(short_action) > 35:
                short_action = short_action[:35].rsplit(' ', 1)[0]
            p5_title = (p5_prefix + short_action).strip()
            if len(p5_title) > 80:
                p5_title = p5_title[:80].rsplit(' ', 1)[0]
            if len(p5_title) < 40:
                p5_title = (p5_title + " Scene").strip()
            
            item.setdefault("pond5", {})["title"] = p5_title
            item["pond5"]["description"] = f"{city}, {country} {p5_date}: {new_ed_desc}"
            
            # Dreamstime
            dt_prefix = f"{city}, {country} - {ed_date}: "
            dt_name = (dt_prefix + short_action).strip()
            item.setdefault("dreamstime", {})["video_name"] = dt_name
            item["dreamstime"]["description"] = f"{city}, {country} - {ed_date}: {new_ed_desc}"
            
            # Keywords
            kw_list = [k.strip().lower() for k in item.get("keywords", "").split(",") if k.strip()]
            for extra in ["tourists", "visitors", "people", "travelers", "walking", "leisure"]:
                if extra not in kw_list:
                    kw_list.append(extra)
            item["keywords"] = ", ".join(kw_list[:45])
            
        else:
            kept_commercial += 1

    print("\n=== Audit Results ===")
    print(f"Already Editorial: {already_editorial}")
    print(f"Updated from Commercial -> Editorial: {updated_to_editorial}")
    print(f"Remaining Commercial (no people found): {kept_commercial}")
    print(f"Total Editorial now: {already_editorial + updated_to_editorial} / {len(cache_data)}")

    # Save updated cache
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)
    print(f"Updated cache saved to {CACHE_FILE}")

    # Regenerate all CSVs
    regenerate_csvs(cache_data, vmeta_lookup)

def sanitize_adobe_title(title):
    t = re.sub(r'[,.;:!?]', ' ', title or '')
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) > 70:
        t = t[:70].rsplit(' ', 1)[0]
    return t

def regenerate_csvs(results, meta_lookup):
    print("\nRegenerating agency CSV files...")
    
    # 1. Adobe
    adobe_csv = os.path.join(METADATA_DIR, "adobe_stock_video.csv")
    with open(adobe_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Title", "Keywords", "Category", "Releases"])
        for r in results:
            clean_title = sanitize_adobe_title(r["adobe"]["title"])
            w.writerow([r["new_filename"], clean_title, r["keywords"], r["adobe"]["category"], ""])

    # 2. Shutterstock
    shutter_csv = os.path.join(METADATA_DIR, "shutterstock_video.csv")
    with open(shutter_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Description", "Keywords", "Categories", "Editorial", "Mature content", "illustration"])
        for r in results:
            ed = "yes" if r["editorial"] else "no"
            shutter_meta = r.get("shutterstock", {})
            desc = shutter_meta.get("description", "")
            cats = shutter_meta.get("categories", "buildings/landmarks")
            w.writerow([r["new_filename"], desc, r["keywords"], cats, ed, "no", "no"])

    # 3. Pond5
    pond5_csv = os.path.join(METADATA_DIR, "pond5_video.csv")
    with open(pond5_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["originalfilename", "title", "description", "keywords", "editorial"])
        for r in results:
            ed = "yes" if r["editorial"] else "no"
            p5_meta = r.get("pond5", {})
            w.writerow([r["new_filename"], p5_meta.get("title", ""), p5_meta.get("description", ""), r["keywords"], ed])

    # 4. Dreamstime
    dreamstime_csv = os.path.join(METADATA_DIR, "dreamstime_video.csv")
    with open(dreamstime_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Video Name", "Description", "Category 1", "Category 2", "Category 3", "keywords", "W-EL", "SR-EL", "SR-Price", "Editorial", "MR doc Ids", "Pr Docs"])
        for r in results:
            ed_val = "1" if r["editorial"] else "0.0"
            d = r.get("dreamstime", {})
            c1 = str(d.get("cat1", "70"))
            c2 = str(d.get("cat2", "59"))
            c3 = str(d.get("cat3", "72"))
            if c1 == "2": c1 = "70"
            if c2 == "2": c2 = "70"
            if c3 == "2": c3 = "70"
            w.writerow([r["new_filename"], d.get("video_name", ""), d.get("description", ""), c1, c2, c3, r["keywords"], "0.0", "0.0", "0.0", ed_val, "", ""])

    print(f"All 4 CSVs regenerated successfully in {METADATA_DIR}")

if __name__ == "__main__":
    main()
