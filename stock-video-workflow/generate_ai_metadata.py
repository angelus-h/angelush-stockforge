#!/usr/bin/env python3
import os
import sys
import glob
import json
import csv
import argparse
import time
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
   - Categories: Max 2 categories (e.g., "Transportation, Travel", or "Nature, Parks").
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
    
    for fs in filmstrips:
        base_name = os.path.basename(fs).replace("_filmstrip.jpg", "")
        # Match original video
        orig_video = next((v for v in all_videos if v.startswith(base_name)), None)
        if not orig_video or orig_video in processed_files:
            continue
            
        vid_meta = meta_lookup.get(orig_video, {})
        
        metadata = generate_metadata(model, fs, vid_meta)
        if metadata:
            metadata["original_filename"] = orig_video
            results.append(metadata)
            processed_files.add(orig_video)
            new_results += 1
            
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            time.sleep(2) # rate limit mitigation

    print(f"Finished generating metadata. Newly processed: {new_results}. Total: {len(results)}")
    
    # CSV Generation
    # 1. Adobe
    adobe_csv = os.path.join(out_dir, "adobe_stock_video.csv")
    with open(adobe_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Title", "Keywords", "Category", "Releases"])
        for r in results:
            w.writerow([r["new_filename"], r["adobe"]["title"], r["keywords"], r["adobe"]["category"], ""])
            
    # 2. Shutterstock
    shutter_csv = os.path.join(out_dir, "shutterstock_video.csv")
    with open(shutter_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Description", "Keywords", "Categories", "Illustration", "Mature content", "Editorial"])
        for r in results:
            ed = "yes" if r["editorial"] else "no"
            w.writerow([r["new_filename"], r["shutterstock"]["description"], r["keywords"], r["shutterstock"]["categories"], "no", "no", ed])
            
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
