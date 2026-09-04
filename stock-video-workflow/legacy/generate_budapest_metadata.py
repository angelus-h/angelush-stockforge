#!/usr/bin/env python3
import os
import glob
import json
import csv
import re
import time
import google.generativeai as genai
from PIL import Image

# Configure Gemini
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not set")
genai.configure(api_key=api_key)

generation_config = {
  "temperature": 0.4,
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 8192,
  "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
  model_name="gemini-3.6-flash",
  generation_config=generation_config,
)

prompt_template = """
You are an expert Commercial Stock Metadata Optimizer. Analyze the provided filmstrip (5 keyframes of a video) and generate metadata for Adobe Stock, Shutterstock, Pond5, and Dreamstime.

# Context:
- The video was taken in Budapest, Hungary. It may contain people, traffic, public transport (BKK, MAV), cityscapes, etc.
- If there are recognizable people, faces, license plates, or branded logos/vehicles (like BKK trams/buses, MAV trains, store logos), it MUST be marked as "Editorial" = true. Otherwise "Editorial" = false.
- Time-lapse: If the camera is static but things are moving fast, it's a time-lapse (mention "time-lapse" in titles/descriptions/keywords).

# Outputs needed per platform rules:
1. **New Filename**: rename the video based on content. Format: `budapest_<theme>_<shot>.mp4`. ONLY lowercase ascii, underscores.
2. **Adobe**:
   - Title: 5-200 chars, descriptive, commercial.
   - Category: 2 (Buildings/Arch), 14 (Plants), 20 (Transport), 21 (Travel)
3. **Shutterstock**:
   - Description: IF Editorial, use exact format: `BUDAPEST, HUNGARY - MONTH DAY, YEAR: <description>`. (Use "MAY 24, 2024" as a placeholder date). IF Commercial, just standard description.
   - Categories: e.g. "Transportation, Travel", or "Buildings/Landmarks, Travel". Max 2.
4. **Pond5**:
   - Title: strictly 40-80 chars. `[Main subject] + [Action] + [Environment] + [Type of shot]`.
   - Description: Similar to Shutterstock but without the strictly editorial prefix (though good to have location).
5. **Dreamstime**:
   - Video Name: Short descriptive title.
   - Description: Detailed description.
   - Categories: 3 numeric codes (e.g., 16, 59, 132 for travel/outdoor, 20 for transport). 
6. **Keywords**: 25-45 highly relevant lowercase keywords, comma separated. Do not include brands if Commercial. Include 'budapest, hungary'.

# JSON Output Format STRICTLY:
{
    "new_filename": "budapest_...",
    "editorial": true/false,
    "keywords": "word1, word2, ...",
    "adobe": {
        "title": "...",
        "category": "21"
    },
    "shutterstock": {
        "description": "...",
        "categories": "Transportation, Travel"
    },
    "pond5": {
        "title": "...",
        "description": "..."
    },
    "dreamstime": {
        "video_name": "...",
        "description": "...",
        "cat1": "132",
        "cat2": "59",
        "cat3": "0"
    }
}
"""

def generate_metadata(filmstrip_path):
    print(f"Analyzing {filmstrip_path}...")
    try:
        img = Image.open(filmstrip_path)
        response = model.generate_content([prompt_template, img])
        return json.loads(response.text)
    except Exception as e:
        print(f"Error on {filmstrip_path}: {e}")
        return None

def main():
    base_dir = "/run/media/mgreczi/SSD/VIDEOS/Budapest"
    frames_dir = os.path.join(base_dir, "_temp_frames")
    out_dir = os.path.join(base_dir, "_metadata")
    os.makedirs(out_dir, exist_ok=True)
    
    # Check what videos exist
    all_videos = [f for f in os.listdir(base_dir) if f.lower().endswith(('.mp4', '.mov')) and not f.startswith('.')]
    
    results = []
    cache_file = os.path.join(out_dir, "ai_metadata_cache.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            results = json.load(f)
            
    processed_files = {r["original_filename"] for r in results}
    
    # Process only completed filmstrips
    filmstrips = glob.glob(os.path.join(frames_dir, "*_filmstrip.jpg"))
    
    for fs in filmstrips:
        base_name = os.path.basename(fs).replace("_filmstrip.jpg", "")
        # Find original video
        orig_video = next((v for v in all_videos if v.startswith(base_name)), None)
        if not orig_video or orig_video in processed_files:
            continue
            
        metadata = generate_metadata(fs)
        if metadata:
            metadata["original_filename"] = orig_video
            results.append(metadata)
            processed_files.add(orig_video)
            
            # Save progressively
            with open(cache_file, "w") as f:
                json.dump(results, f, indent=2)
            time.sleep(2) # rate limit mitigation
            
    print(f"Total processed videos: {len(results)}")
    
    # Generate CSVs
    # 1. Adobe
    with open(os.path.join(out_dir, "adobe_stock_video.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Title", "Keywords", "Category", "Releases"])
        for r in results:
            w.writerow([r["new_filename"], r["adobe"]["title"], r["keywords"], r["adobe"]["category"], ""])
            
    # 2. Shutterstock
    with open(os.path.join(out_dir, "shutterstock_video.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Description", "Keywords", "Categories", "Illustration", "Mature content", "Editorial"])
        for r in results:
            ed = "yes" if r["editorial"] else "no"
            w.writerow([r["new_filename"], r["shutterstock"]["description"], r["keywords"], r["shutterstock"]["categories"], "no", "no", ed])
            
    # 3. Pond5
    with open(os.path.join(out_dir, "pond5_video.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["originalfilename", "title", "description", "keywords", "editorial"])
        for r in results:
            ed = "yes" if r["editorial"] else "no"
            w.writerow([r["new_filename"], r["pond5"]["title"], r["pond5"]["description"], r["keywords"], ed])
            
    # 4. Dreamstime
    with open(os.path.join(out_dir, "dreamstime_video.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Video Name", "Description", "Category 1", "Category 2", "Category 3", "keywords", "W-EL", "SR-EL", "SR-Price", "Editorial", "MR doc Ids", "Pr Docs"])
        for r in results:
            ed_val = "1" if r["editorial"] else "0.0" # Dreamstime uses 1 for editorial maybe? Prompt says 0.0 if not. Let's use 0.0 or 1.
            d = r["dreamstime"]
            w.writerow([r["new_filename"], d["video_name"], d["description"], d["cat1"], d["cat2"], d.get("cat3", "0"), f'"{r["keywords"]}"', "0.0", "0.0", "0.0", ed_val, "", ""])
            
    print(f"CSVs generated in {out_dir}")
    
    # Optionally, rename files if requested
    print("Files can be renamed by running a simple mv loop from the cache JSON.")

if __name__ == "__main__":
    main()
