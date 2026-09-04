#!/usr/bin/env python3
import os
import sys
import glob
import json
import csv
import argparse
import time
import re
from datetime import datetime
import google.generativeai as genai
from PIL import Image

def format_editorial_date(date_str):
    if not date_str or date_str == "Unknown":
        return "September 29, 2024"
    try:
        dt = datetime.strptime(date_str.split(' ')[0], "%Y-%m-%d")
        return dt.strftime("%B %d, %Y")
    except Exception:
        return "September 29, 2024"

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

def generate_prompt(video_meta, custom_context="", force_editorial=False):
    loc_city = video_meta.get("location", {}).get("city", "Unknown")
    loc_country = video_meta.get("location", {}).get("country", "Unknown")
    loc_hint = video_meta.get("location", {}).get("hint", "")
    date_rec = video_meta.get("date_recorded", "Unknown Date")
    editorial_date = format_editorial_date(date_rec)
    
    editorial_rule = """# Editorial vs Commercial Rules:
- If there are recognizable people (faces), license plates, or branded logos/vehicles, it MUST be marked as "Editorial" = true.
- Otherwise "Editorial" = false."""
    if force_editorial:
        editorial_rule = f"""# Editorial Requirement (STRICT):
- All footage in this batch MUST be marked as "Editorial" = true.
- Descriptions MUST strictly begin with: `{loc_city}, {loc_country} - {editorial_date}: ` (do NOT use all caps) followed by a factual description answering the 5 Ws (Who, What, Where, When, Why)."""

    context_section = f"""# Context (From Video Metadata):
- Location: {loc_city}, {loc_country}
- Additional Location Hint: {loc_hint}
- Date Recorded: {date_rec}"""
    if custom_context:
        context_section += f"\n- Event & Specific Context: {custom_context}"
    context_section += "\n- Time-lapse: If the camera is static but things are moving fast (clouds, traffic), it's a time-lapse. Include 'time-lapse' in titles, descriptions, and keywords."

    return f"""
You are an expert Commercial & Editorial Stock Metadata Optimizer. Analyze the provided filmstrip (5 keyframes of a video) and generate metadata for Adobe Stock, Shutterstock, Pond5, and Dreamstime.

{context_section}

{editorial_rule}

# Platform Specific Rules:
1. **New Filename**: create a descriptive filename. Format: `<city_or_location>_<theme>_<shot>.mp4`. ONLY lowercase ascii, underscores (e.g. `tvarozna_austerlitz_soldiers_marching_wide.mp4`).
2. **Adobe Stock**:
   - Title: strictly 15-70 characters, clear, factual, search-optimized description. NO commas, NO periods, plain text only. NO brand names.
   - Category: Select best numeric ID (2=Buildings/Arch, 14=Plants, 20=Transport, 21=Travel, 11=Nature, 3=People/Lifestyle).
3. **Shutterstock**:
   - Description: IF Editorial, strictly use this format: `{loc_city}, {loc_country} - {editorial_date}: <factual description>`. DO NOT use ALL CAPS for city/country/date. IF Commercial, just write the standard description.
   - Categories: Max 2 categories separated by a comma without spaces. Strictly from official list: abstract, animals/wildlife, art, backgrounds/textures, beauty/fashion, buildings/landmarks, business/finance, celebrities, editorial, education, food and drink, healthcare/medical, holidays, industrial, miscellaneous, nature, objects, parks/outdoor, people, religion, science, signs/symbols, sports/recreation, technology, transportation, vintage. (IMPORTANT: 'travel' DOES NOT EXIST on Shutterstock! For historic/military/reenactment scenes use 'editorial,vintage' or 'editorial,people' or 'buildings/landmarks,editorial').
4. **Pond5**:
   - Title: strictly 40-80 characters. Formula: `[Main subject] [Action] [Environment] [Type of shot]` (e.g. `Battle of Austerlitz Reenactment Soldiers Marching Field Tvarozna`).
   - Description: Similar to Shutterstock but without the strict editorial prefix (though event and location should be mentioned).
5. **Dreamstime**:
   - Video Name: Short descriptive title.
   - Description: IF Editorial, STRICTLY follow Dreamstime official guidelines answering the 5 Ws (Who, What, Where, When, Why): `{loc_city}, {loc_country} - {editorial_date}: [Who] [What] [Where] [Why/How]`. DO NOT use ALL CAPS for city/country/date. (e.g. `{loc_city}, {loc_country} - {editorial_date}: Historical reenactment soldiers in Napoleonic military uniforms march in formation during the Battle of Austerlitz commemoration event.`). IF Commercial, just write the standard description.
   - Categories: 3 numeric codes strictly from Dreamstime official list:
     * 70: Arts & Architecture -> Landmarks
     * 71: Arts & Architecture -> Generic architecture
     * 72: Arts & Architecture -> Outdoor
     * 132: Arts & Architecture -> Historic buildings
     * 59: Travel -> Europe
     * 61: Travel -> Destination scenics
     * 65: Travel -> Arts & Architecture
     * 16: Nature -> Lakes and rivers
     * 146: Nature -> Landscapes
     * 98: Industries -> Transportation
     * 108: People -> Celebrations / Events
     * (STRICT RULE: Category ID 2 DOES NOT EXIST on Dreamstime! Do NOT use 2!).
6. **Keywords**: 25-45 highly relevant lowercase keywords, comma separated. Always include location and event keywords: '{loc_city.lower()}, {loc_country.lower()}'. If depicting Battle of Austerlitz / Napoleonic reenactment, include 'austerlitz, battle of austerlitz, slavkov, napoleon, napoleonic, napoleonic wars, reenactment, historical reenactment, soldiers, historical uniform, period costume, military, 1805, battle, moravia'.

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
        "categories": "editorial,vintage"
    }},
    "pond5": {{
        "title": "...",
        "description": "..."
    }},
    "dreamstime": {{
        "video_name": "...",
        "description": "...",
        "cat1": "108",
        "cat2": "59",
        "cat3": "72"
    }}
}}
"""

def generate_metadata(model, filmstrip_path, video_meta, custom_context="", force_editorial=False, max_retries=3):
    print(f"Analyzing {os.path.basename(filmstrip_path)} using Gemini...")
    prompt = generate_prompt(video_meta, custom_context=custom_context, force_editorial=force_editorial)
    
    for attempt in range(max_retries):
        try:
            img = Image.open(filmstrip_path)
            response = model.generate_content([prompt, img])
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            data = json.loads(text)
            return data
        except Exception as e:
            wait_time = (attempt + 1) * 5
            print(f"Attempt {attempt + 1} failed for {os.path.basename(filmstrip_path)}: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            
    print(f"Failed all retries for {filmstrip_path}")
    return None

def main():
    parser = argparse.ArgumentParser(description="Generate AI Stock Video Metadata using Gemini")
    parser.add_argument("--input", "-i", required=True, help="Input directory of original videos")
    parser.add_argument("--frames", "-f", default=None, help="Directory containing _temp_frames (default: <input>/_temp_frames)")
    parser.add_argument("--force-editorial", action="store_true", help="Force all videos to Editorial category")
    parser.add_argument("--context", "-c", default="", help="Specific event or additional context for metadata generation")
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
        
        metadata = generate_metadata(model, fs, vid_meta, custom_context=args.context, force_editorial=args.force_editorial)
        if metadata:
            orig_ext = os.path.splitext(orig_video)[1]
            new_name = os.path.splitext(metadata["new_filename"])[0] + orig_ext
            new_name = re.sub(r'[^a-z0-9_.]', '', new_name.lower())
            metadata["new_filename"] = new_name
            
            if args.force_editorial:
                metadata["editorial"] = True
                loc_city = vid_meta.get("location", {}).get("city", "Unknown")
                loc_country = vid_meta.get("location", {}).get("country", "Unknown")
                date_rec = vid_meta.get("date_recorded", "Unknown Date")
                ed_date = format_editorial_date(date_rec)
                prefix = f"{loc_city.upper()}, {loc_country.upper()} - {ed_date}: "
                shutter_desc = metadata.get("shutterstock", {}).get("description", "")
                if not shutter_desc.startswith(f"{loc_city.upper()}, {loc_country.upper()}"):
                    metadata.setdefault("shutterstock", {})["description"] = prefix + shutter_desc
            
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
    def sanitize_adobe_title(title):
        t = re.sub(r'[,.;:!?]', ' ', title or '')
        t = re.sub(r'\s+', ' ', t).strip()
        if len(t) > 70:
            t = t[:70].rsplit(' ', 1)[0]
        return t

    def sanitize_pond5_title(title):
        t = (title or '').strip()
        if len(t) > 80:
            t = t[:80].rsplit(' ', 1)[0]
        if len(t) < 40:
            t = (t + " 4k stock video footage").strip()
            if len(t) > 80:
                t = t[:80]
        return t

    # 1. Adobe
    adobe_csv = os.path.join(out_dir, "adobe_stock_video.csv")
    with open(adobe_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Title", "Keywords", "Category", "Releases"])
        for r in results:
            clean_title = sanitize_adobe_title(r["adobe"]["title"])
            w.writerow([r["new_filename"], clean_title, r["keywords"], r["adobe"]["category"], ""])
            
    # Helper to clean and validate Shutterstock categories
    VALID_SHUTTERSTOCK_CATS = {
        "abstract": "abstract",
        "animals/wildlife": "animals/wildlife",
        "animals": "animals/wildlife",
        "wildlife": "animals/wildlife",
        "art": "art",
        "backgrounds/textures": "backgrounds/textures",
        "backgrounds": "backgrounds/textures",
        "textures": "backgrounds/textures",
        "beauty/fashion": "beauty/fashion",
        "beauty": "beauty/fashion",
        "fashion": "beauty/fashion",
        "buildings/landmarks": "buildings/landmarks",
        "buildings": "buildings/landmarks",
        "landmarks": "buildings/landmarks",
        "architecture": "buildings/landmarks",
        "buildings/architecture": "buildings/landmarks",
        "business/finance": "business/finance",
        "business": "business/finance",
        "finance": "business/finance",
        "celebrities": "celebrities",
        "editorial": "editorial",
        "education": "education",
        "food and drink": "food and drink",
        "food & drink": "food and drink",
        "food": "food and drink",
        "healthcare/medical": "healthcare/medical",
        "medical": "healthcare/medical",
        "healthcare": "healthcare/medical",
        "holidays": "holidays",
        "industrial": "industrial",
        "industry": "industrial",
        "miscellaneous": "miscellaneous",
        "nature": "nature",
        "objects": "objects",
        "parks/outdoor": "parks/outdoor",
        "parks": "parks/outdoor",
        "outdoor": "parks/outdoor",
        "people": "people",
        "religion": "religion",
        "science": "science",
        "signs/symbols": "signs/symbols",
        "sports/recreation": "sports/recreation",
        "sports": "sports/recreation",
        "technology": "technology",
        "transportation": "transportation",
        "transport": "transportation",
        "vintage": "vintage",
    }

    def sanitize_shutterstock_categories(cat_str):
        if not cat_str:
            return "buildings/landmarks"
        parts = [p.strip() for p in cat_str.replace(";", ",").split(",") if p.strip()]
        valid_cats = []
        for p in parts:
            p_lower = p.lower()
            # If AI hallucinated Travel, replace with buildings/landmarks or parks/outdoor
            if "travel" in p_lower:
                mapped = "buildings/landmarks"
            else:
                mapped = VALID_SHUTTERSTOCK_CATS.get(p_lower)
            if mapped and mapped not in valid_cats:
                valid_cats.append(mapped)
        if not valid_cats:
            valid_cats = ["buildings/landmarks"]
        return ",".join(valid_cats[:2])

    # Helper to clean and format editorial descriptions without ALL CAPS
    def get_clean_editorial_description(desc, city, country, date_recorded):
        ed_date = format_editorial_date(date_recorded)
        dateline = f"{city}, {country} - {ed_date}: "
        # Strip any existing dateline (ALL CAPS or Mixed Case)
        clean_desc = re.sub(r'^[A-Za-z\s/,-]+-\s*[A-Za-z]+\s+\d{1,2},\s*\d{4}:\s*', '', desc or '').strip()
        if not clean_desc:
            clean_desc = desc or ''
        return dateline + clean_desc

    # 2. Shutterstock
    shutter_csv = os.path.join(out_dir, "shutterstock_video.csv")
    with open(shutter_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Description", "Keywords", "Categories", "Editorial", "Mature content", "illustration"])
        for r in results:
            ed = "yes" if r["editorial"] else "no"
            shutter_meta = r.get("shutterstock", {})
            desc = shutter_meta.get("description", "")
            if r["editorial"]:
                orig_file = r.get("original_filename", "")
                loc_info = meta_lookup.get(orig_file, {}).get("location", {})
                city = loc_info.get("city", "Tvarozna")
                country = loc_info.get("country", "Czech Republic")
                dt_str = meta_lookup.get(orig_file, {}).get("date_recorded", "")
                desc = get_clean_editorial_description(desc, city, country, dt_str)
            cats = sanitize_shutterstock_categories(shutter_meta.get("categories", ""))
            w.writerow([r["new_filename"], desc, r["keywords"], cats, ed, "no", "no"])
            
    # 3. Pond5
    pond5_csv = os.path.join(out_dir, "pond5_video.csv")
    with open(pond5_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["originalfilename", "title", "description", "keywords", "editorial"])
        for r in results:
            ed = "yes" if r["editorial"] else "no"
            p5_title = sanitize_pond5_title(r["pond5"]["title"])
            w.writerow([r["new_filename"], p5_title, r["pond5"]["description"], r["keywords"], ed])
            
    # 4. Dreamstime
    dreamstime_csv = os.path.join(out_dir, "dreamstime_video.csv")
    with open(dreamstime_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Video Name", "Description", "Category 1", "Category 2", "Category 3", "keywords", "W-EL", "SR-EL", "SR-Price", "Editorial", "MR doc Ids", "Pr Docs"])
        for r in results:
            ed_val = "1" if r["editorial"] else "0.0" 
            d = r.get("dreamstime", {})
            desc = d.get("description", "")
            
            # For Editorial on Dreamstime, strictly follow official 5 Ws format with dateline (not all caps)
            if r["editorial"]:
                orig_file = r.get("original_filename", "")
                loc_info = meta_lookup.get(orig_file, {}).get("location", {})
                city = loc_info.get("city", "Tvarozna")
                country = loc_info.get("country", "Czech Republic")
                dt_str = meta_lookup.get(orig_file, {}).get("date_recorded", "")
                
                # If Dreamstime description is too short, take the detailed shutterstock description base
                base_desc = desc
                shutter_desc = r.get("shutterstock", {}).get("description", "")
                if len(base_desc) < 30 and len(shutter_desc) >= 30:
                    base_desc = shutter_desc
                desc = get_clean_editorial_description(base_desc, city, country, dt_str)
                
            c1 = str(d.get("cat1", "132"))
            c2 = str(d.get("cat2", "59"))
            c3 = str(d.get("cat3", "0"))
            
            # Category 2 is Adobe Architecture ID, on Dreamstime 70 is Landmarks / 71 Generic Architecture
            if c1 == "2": c1 = "70"
            if c2 == "2": c2 = "70"
            if c3 == "2": c3 = "70"
            
            w.writerow([r["new_filename"], d.get("video_name", ""), desc, c1, c2, c3, r["keywords"], "0.0", "0.0", "0.0", ed_val, "", ""])
            
    print(f"CSVs generated in {out_dir}")

if __name__ == "__main__":
    main()
