#!/usr/bin/env python3
import os
import sys
import glob
import json
import csv
import argparse
import time
import re
import google.generativeai as genai
from PIL import Image

def setup_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")
    genai.configure(api_key=api_key)
    
    generation_config = {
      "temperature": 0.4,
      "top_p": 0.95,
      "top_k": 40,
      "max_output_tokens": 8192,
      "response_mime_type": "application/json",
    }
    
    # Use gemini-flash-latest which is listed as supported
    return genai.GenerativeModel(
      model_name="gemini-flash-latest",
      generation_config=generation_config,
    )

def generate_prompt(video_meta):
    loc_city = video_meta.get("location", {}).get("city", "Unknown")
    loc_country = video_meta.get("location", {}).get("country", "Unknown")
    loc_hint = video_meta.get("location", {}).get("hint", "")
    date_rec = video_meta.get("date_recorded", "Unknown Date")
    
    return f"""
You are an expert Commercial Stock Metadata Optimizer. Analyze the provided filmstrip (5 keyframes of a video) and generate metadata for Adobe Stock, Shutterstock, Pond5, and Dreamstime.

# Context (From Video Metadata):
- Location: {loc_city}, {loc_country}
- Additional Location Hint: {loc_hint}
- Date Recorded: {date_rec}
- Time-lapse: If the camera is static but things are moving fast (clouds, traffic), it's a time-lapse. Include "time-lapse" in titles, descriptions, and keywords.

# Editorial vs Commercial Rules:
- If there are recognizable people (faces), license plates, or branded logos/vehicles, it MUST be marked as "Editorial" = true.
- Otherwise "Editorial" = false.

# Platform Specific Rules:
1. **New Filename**: create a descriptive filename. Format: `<city_or_location>_<theme>_<shot>.mp4`. ONLY lowercase ascii, underscores.
2. **Adobe Stock**:
   - Title: 5-200 chars, descriptive, commercial.
   - Category: Select best numeric ID (2=Buildings/Arch, 14=Plants, 20=Transport, 21=Travel, 11=Nature).
3. **Shutterstock**:
   - Description: IF Editorial, strictly use this format: `{loc_city.upper()}, {loc_country.upper()} - {date_rec.split(' ')[0] if date_rec != 'Unknown' else 'JANUARY 01, 2024'}: <description>`. IF Commercial, just write the standard description.
   - Categories: Max 2 categories separated by a comma without spaces. Strictly from official list: Abstract, Animals/Wildlife, Art, Backgrounds/Textures, Beauty/Fashion, Buildings/Landmarks, Business/Finance, Celebrities, Editorial, Education, Food and Drink, Healthcare/Medical, Holidays, Industrial, Miscellaneous, Nature, Objects, Parks/Outdoor, People, Religion, Science, Signs/Symbols, Sports/Recreation, Technology, Transportation, Vintage. (IMPORTANT: 'Travel' DOES NOT EXIST on Shutterstock! Use 'Buildings/Landmarks' or 'Parks/Outdoor' instead).
4. **Pond5**:
   - Title: strictly 40-80 chars. `[Main subject] + [Action] + [Environment] + [Type of shot]`.
   - Description: Similar to Shutterstock but without the strict editorial prefix (though location should be mentioned).
5. **Dreamstime**:
   - Video Name: Short descriptive title.
   - Description: Detailed description.
   - Categories: 3 numeric codes (e.g., 16, 59, 132 for travel/outdoor, 20 for transport).
6. **Keywords**: 25-45 highly relevant lowercase keywords, comma separated. Do not include brands if Commercial. Always include '{loc_city.lower()}, {loc_country.lower()}'.

# JSON Output Format STRICTLY:
{{
    "new_filename": "...",
    "editorial": true/false,
    "keywords": "word1, word2, ...",
    "adobe": {{
        "title": "...",
        "category": "21"
    }},
    "shutterstock": {{
        "description": "...",
        "categories": "Transportation, Travel"
    }},
    "pond5": {{
        "title": "...",
        "description": "..."
    }},
    "dreamstime": {{
        "video_name": "...",
        "description": "...",
        "cat1": "132",
        "cat2": "59",
        "cat3": "0"
    }}
}}
"""

def generate_metadata(model, filmstrip_path, video_meta):
    print(f"Analyzing {os.path.basename(filmstrip_path)} using Gemini...")
    prompt = generate_prompt(video_meta)
    try:
        img = Image.open(filmstrip_path)
        response = model.generate_content([prompt, img])
        return json.loads(response.text)
    except Exception as e:
        print(f"Error on {filmstrip_path}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Generate AI Stock Video Metadata using Gemini")
    parser.add_argument("--input", "-i", required=True, help="Input directory of original videos")
    parser.add_argument("--frames", "-f", default=None, help="Directory containing _temp_frames (default: <input>/_temp_frames)")
    args = parser.parse_args()

    base_dir = os.path.abspath(args.input)
    frames_dir = args.frames if args.frames else os.path.join(base_dir, "_temp_frames")
    out_dir = os.path.join(base_dir, "_metadata")
    os.makedirs(out_dir, exist_ok=True)
    
    metadata_summary_path = os.path.join(frames_dir, "video_metadata_summary.json")
    if not os.path.exists(metadata_summary_path):
        print(f"Error: {metadata_summary_path} not found. Please run extract_video_keyframes.py first.")
        sys.exit(1)
        
    with open(metadata_summary_path, "r", encoding="utf-8") as f:
        video_metadata_list = json.load(f)
        
    # Create lookup dictionary by filename
    meta_lookup = {item["filename"]: item for item in video_metadata_list}

    try:
        model = setup_gemini()
    except Exception as e:
        print(f"Failed to initialize Gemini: {e}")
        sys.exit(1)

    all_videos = [f for f in os.listdir(base_dir) if f.lower().endswith(('.mp4', '.mov', '.mkv')) and not f.startswith('.')]
    
    results = []
    cache_file = os.path.join(out_dir, "ai_metadata_cache.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                results = json.load(f)
        except:
            pass
            
    processed_files = {r["original_filename"] for r in results}
    
    filmstrips = glob.glob(os.path.join(frames_dir, "*_filmstrip.jpg"))
    new_results = 0
    
    # Map filmstrip directly to exact filename matching base_name + extension
    for fs in filmstrips:
        base_name = os.path.basename(fs).replace("_filmstrip.jpg", "")
        
        # Check cache: already processed if any entry has original_filename matching base_name
        cached_entry = next((r for r in results if os.path.splitext(r["original_filename"])[0] == base_name), None)
        if cached_entry:
            continue

        # Match original video strictly with matching extension
        orig_video = next((v for v in all_videos if os.path.splitext(v)[0] == base_name), None)
        if not orig_video:
            continue
            
        vid_meta = meta_lookup.get(orig_video, {})
        
        metadata = generate_metadata(model, fs, vid_meta)
        if metadata:
            orig_ext = os.path.splitext(orig_video)[1]
            new_name = os.path.splitext(metadata["new_filename"])[0] + orig_ext
            new_name = re.sub(r'[^a-z0-9_.]', '', new_name.lower())
            metadata["new_filename"] = new_name
            
            metadata["original_filename"] = orig_video
            results.append(metadata)
            new_results += 1
            
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            time.sleep(2) # rate limit mitigation

    print(f"Finished generating metadata. Newly processed: {new_results}. Total: {len(results)}")
    
    # Ensure unique new_filenames across results to avoid collisions
    seen_names = {}
    for r in results:
        base_target, ext = os.path.splitext(r["new_filename"])
        if r["new_filename"] in seen_names:
            seen_names[r["new_filename"]] += 1
            r["new_filename"] = f"{base_target}_{seen_names[r['new_filename']]}{ext}"
        else:
            seen_names[r["new_filename"]] = 1

    # Save cache with deduplicated filenames
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Renaming of files
    print("\nRenaming original video files...")
    rename_count = 0
    for r in results:
        # The file might have its original name or already be partially renamed
        old_path = os.path.join(base_dir, r["original_filename"])
        new_path = os.path.join(base_dir, r["new_filename"])
        
        if os.path.exists(old_path) and old_path != new_path:
            try:
                os.rename(old_path, new_path)
                rename_count += 1
            except Exception as e:
                print(f"Warning: Failed to rename {r['original_filename']} -> {r['new_filename']}: {e}")
    
    if rename_count > 0:
        print(f"Successfully renamed {rename_count} video files.")
    else:
        print("No files required renaming.")
    
    # CSV Generation
    # 1. Adobe
    adobe_csv = os.path.join(out_dir, "adobe_stock_video.csv")
    with open(adobe_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Title", "Keywords", "Category", "Releases"])
        for r in results:
            w.writerow([r["new_filename"], r["adobe"]["title"], r["keywords"], r["adobe"]["category"], ""])
            
    # Helper to clean and validate Shutterstock categories
    VALID_SHUTTERSTOCK_CATS = {
        "abstract": "Abstract",
        "animals/wildlife": "Animals/Wildlife",
        "animals": "Animals/Wildlife",
        "wildlife": "Animals/Wildlife",
        "art": "Art",
        "backgrounds/textures": "Backgrounds/Textures",
        "backgrounds": "Backgrounds/Textures",
        "textures": "Backgrounds/Textures",
        "beauty/fashion": "Beauty/Fashion",
        "beauty": "Beauty/Fashion",
        "fashion": "Beauty/Fashion",
        "buildings/landmarks": "Buildings/Landmarks",
        "buildings": "Buildings/Landmarks",
        "landmarks": "Buildings/Landmarks",
        "architecture": "Buildings/Landmarks",
        "buildings/architecture": "Buildings/Landmarks",
        "business/finance": "Business/Finance",
        "business": "Business/Finance",
        "finance": "Business/Finance",
        "celebrities": "Celebrities",
        "editorial": "Editorial",
        "education": "Education",
        "food and drink": "Food and Drink",
        "food & drink": "Food and Drink",
        "food": "Food and Drink",
        "healthcare/medical": "Healthcare/Medical",
        "medical": "Healthcare/Medical",
        "healthcare": "Healthcare/Medical",
        "holidays": "Holidays",
        "industrial": "Industrial",
        "industry": "Industrial",
        "miscellaneous": "Miscellaneous",
        "nature": "Nature",
        "objects": "Objects",
        "parks/outdoor": "Parks/Outdoor",
        "parks": "Parks/Outdoor",
        "outdoor": "Parks/Outdoor",
        "people": "People",
        "religion": "Religion",
        "science": "Science",
        "signs/symbols": "Signs/Symbols",
        "sports/recreation": "Sports/Recreation",
        "sports": "Sports/Recreation",
        "technology": "Technology",
        "transportation": "Transportation",
        "transport": "Transportation",
        "vintage": "Vintage",
    }

    def sanitize_shutterstock_categories(cat_str):
        if not cat_str:
            return "Buildings/Landmarks"
        parts = [p.strip() for p in cat_str.replace(";", ",").split(",") if p.strip()]
        valid_cats = []
        for p in parts:
            p_lower = p.lower()
            # If AI hallucinated Travel, replace with Buildings/Landmarks or Parks/Outdoor
            if "travel" in p_lower:
                mapped = "Buildings/Landmarks"
            else:
                mapped = VALID_SHUTTERSTOCK_CATS.get(p_lower)
            if mapped and mapped not in valid_cats:
                valid_cats.append(mapped)
        if not valid_cats:
            valid_cats = ["Buildings/Landmarks"]
        return ",".join(valid_cats[:2])

    # 2. Shutterstock
    shutter_csv = os.path.join(out_dir, "shutterstock_video.csv")
    with open(shutter_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Description", "Keywords", "Categories", "Editorial", "Mature content", "illustration"])
        for r in results:
            ed = "yes" if r["editorial"] else "no"
            shutter_meta = r.get("shutterstock", {})
            cats = sanitize_shutterstock_categories(shutter_meta.get("categories", ""))
            w.writerow([r["new_filename"], shutter_meta.get("description", ""), r["keywords"], cats, ed, "no", "no"])
            
    # 3. Pond5
    pond5_csv = os.path.join(out_dir, "pond5_video.csv")
    with open(pond5_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["originalfilename", "title", "description", "keywords", "editorial"])
        for r in results:
            ed = "yes" if r["editorial"] else "no"
            w.writerow([r["new_filename"], r["pond5"]["title"], r["pond5"]["description"], r["keywords"], ed])
            
    # 4. Dreamstime
    dreamstime_csv = os.path.join(out_dir, "dreamstime_video.csv")
    with open(dreamstime_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Video Name", "Description", "Category 1", "Category 2", "Category 3", "keywords", "W-EL", "SR-EL", "SR-Price", "Editorial", "MR doc Ids", "Pr Docs"])
        for r in results:
            ed_val = "1" if r["editorial"] else "0.0" 
            d = r.get("dreamstime", {})
            w.writerow([r["new_filename"], d.get("video_name", ""), d.get("description", ""), d.get("cat1", ""), d.get("cat2", ""), d.get("cat3", "0"), f'"{r["keywords"]}"', "0.0", "0.0", "0.0", ed_val, "", ""])
            
    print(f"CSVs generated in {out_dir}")

if __name__ == "__main__":
    main()
