#!/usr/bin/env python3
"""
process_vecteezy_batch.py
Automates copy and AI metadata generation for Vecteezy contributor review.
"""

import os
import sys
import io
import re
import csv
import json
import shutil
import time
from PIL import Image
from google import genai
from google.genai import types

sys.stdout.reconfigure(line_buffering=True)

IMAGES_CONFIG = [
    (r"F:\Képek\Hrad Veveri\final\IMGP0358.jpg", "Hrad Veveri (Veveri Castle), Czech Republic. Historic medieval castle."),
    (r"F:\Képek\Hrad Veveri\final\IMGP1291.jpg", "Hrad Veveri (Veveri Castle), Czech Republic. Historic medieval castle."),
    (r"F:\Képek\Lednice\final\IMGP5248.jpg", "Lednice Castle / Chateau and gardens, UNESCO World Heritage site, South Moravia, Czech Republic."),
    (r"F:\Képek\Lednice\final\IMGP5226.jpg", "Lednice Castle / Chateau and gardens, UNESCO World Heritage site, South Moravia, Czech Republic."),
    (r"F:\Képek\Lednice\final\IMGP4151.jpg", "Lednice Castle / Chateau and gardens, UNESCO World Heritage site, South Moravia, Czech Republic."),
    (r"F:\Képek\Lednice\final\IMGP4231.jpg", "Lednice Castle / Chateau and gardens, UNESCO World Heritage site, South Moravia, Czech Republic."),
    (r"F:\Képek\Lednice\final\IMGP2401.jpg", "Lednice Castle / Chateau and gardens, UNESCO World Heritage site, South Moravia, Czech Republic."),
    (r"F:\Képek\Dolni Kounice\final\_IMG7819.jpg", "Dolni Kounice, Czech Republic. Historical monastery Rosa Coeli ruins / architecture."),
    (r"F:\Képek\Vitochov\final\IMGP0619.jpg", "Vitochov, Czech Republic. St. Michael Church (Kostelik svateho Michaela), stone Romanesque church on a hill."),
    (r"F:\Képek\Hardegg\final\IMGP5505.jpg", "Hardegg Castle (Burg Hardegg), Thayatal valley, Austria near Czech border."),
    (r"F:\Képek\Kozenek\final\IMGP8300.jpg", "Kozenek, Moravia, Czech Republic. Natural hill / scenic landscape."),
    (r"F:\Képek\Vranov\final\IMGP1533.jpg", "Vranov nad Dyji Chateau / Castle, perched on a rock cliff above Dyje river, South Moravia, Czech Republic."),
    (r"F:\Képek\Brno Ossuary\final\IMGP6182.jpg", "Brno Ossuary (Kostnice u sv. Jakuba) under Church of St. James, Brno, Czech Republic. Historical bone vault, skull and bone arrangement."),
    (r"F:\Képek\Brno Ossuary\final\IMGP3734.JPG", "Brno Ossuary (Kostnice u sv. Jakuba) under Church of St. James, Brno, Czech Republic. Historical bone vault, skull and bone arrangement."),
    (r"F:\Képek\Brno Ossuary\final\IMGP6173.jpg", "Brno Ossuary (Kostnice u sv. Jakuba) under Church of St. James, Brno, Czech Republic. Historical bone vault, skull and bone arrangement."),
    (r"F:\Képek\Plant disease\final\IMGP9529.jpg", "Plant disease, agricultural botany, horticulture plant pathology, fungal / bacterial leaf infection or pest damage."),
    (r"F:\Képek\Plant disease\final\IMGP9520.jpg", "Plant disease, agricultural botany, horticulture plant pathology, fungal / bacterial leaf infection or pest damage."),
    (r"F:\Képek\Plant disease\final\IMGP9848.jpg", "Plant disease, agricultural botany, horticulture plant pathology, fungal / bacterial leaf infection or pest damage."),
    (r"F:\Képek\Oburky-Trestenec\final\IMGP9165.jpg", "Oburky-Trestenec, Czech Republic. Spider (pok) close-up macro nature photography."),
    (r"F:\Képek\Kistarcsa\final\IMGP5421.jpg", "Kistarcsa, Hungary. Peach fruit (barack) on peach tree branch in orchard."),
    (r"F:\Képek\Budapest\final\IMGP2050.jpg", "Budapest, Hungary. Keleti Railway Station (Keleti palyaudvar), historic transport architecture."),
    (r"F:\Képek\Budapest\final\IMGP1669.jpg", "Budapest, Cinkota district, Hungary. Historic church / architecture / landscape."),
    (r"F:\Képek\Olomouc\final\IMGP2417.jpg", "Olomouc, Moravia, Czech Republic. Historic city center / architecture."),
    (r"F:\Képek\Pozsony\final\IMGP0183.jpg", "Bratislava (Pozsony), Slovakia. Historic city center / Danube / architecture."),
    (r"F:\Képek\Balatonudvari\final\IMGP9742.jpg", "Balatonudvari, Lake Balaton, Hungary. Historic cemetery with unique heart-shaped gravestones (sziv alaku sirok)."),
    (r"F:\Képek\Tihany\final\IMGP9386.jpg", "Tihany Peninsula, Lake Balaton, Hungary. Historic Benedictine Abbey / scenic view."),
    (r"F:\Képek\Tihany\final\IMGP9381.jpg", "Tihany Peninsula, Lake Balaton, Hungary. Historic Benedictine Abbey / scenic view."),
    (r"F:\Képek\Wind mill\final\IMGP0073.jpg", "Kunkovice windmill (Vetrny mlyn Kunkovice), South Moravia, Czech Republic. Traditional Dutch style historic stone windmill."),
    (r"F:\Képek\Wind mill\final\IMGP9984.jpg", "Windmill near Brankovice / Moravia, Czech Republic. Historic wooden or masonry windmill."),
]

PROHIBITED_WORDS = [
    "beautiful", "stunning", "amazing", "gorgeous", "wonderful",
    "breathtaking", "incredible", "cool", "best", "lovely", "pretty"
]

def load_system_prompt():
    prompt_path = r"G:\repos\angelush-stockforge\stock-video-workflow\prompts\vecteezy-prompt.txt"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()

def clean_text_from_prohibitions(text):
    for word in PROHIBITED_WORDS:
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        text = pattern.sub("", text)
    # clean extra spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text

def sanitize_keywords(keywords_raw):
    if isinstance(keywords_raw, list):
        raw_list = keywords_raw
    else:
        raw_list = str(keywords_raw).split(",")
    
    cleaned = []
    seen = set()
    for kw in raw_list:
        k = kw.strip().lower()
        k = re.sub(r"[^\w\s-]", "", k)
        k = re.sub(r"\s+", " ", k).strip()
        if not k:
            continue
        # Check against prohibited words
        is_prohibited = any(pw in k.split() for pw in PROHIBITED_WORDS)
        if is_prohibited:
            continue
        if k not in seen:
            seen.add(k)
            cleaned.append(k)
    
    # Vecteezy requires strictly between 10 and 30 keywords
    if len(cleaned) > 30:
        cleaned = cleaned[:30]
    return cleaned

def clean_metadata_response(meta, filename):
    title = meta.get("title", "").strip()
    title = clean_text_from_prohibitions(title)
    # Remove file extensions or numeric codes from title
    title = re.sub(r"\.(jpe?g|png|tiff?|eps|ai)\b", "", title, flags=re.IGNORECASE)
    title = re.sub(r"#\d+", "", title).strip()
    title = re.sub(r"\s+", " ", title).strip()

    desc = meta.get("description", "").strip()
    desc = clean_text_from_prohibitions(desc)
    if len(desc) > 495:
        # truncate safely at sentence boundary if possible
        desc = desc[:490].rsplit(".", 1)[0] + "."

    keywords = sanitize_keywords(meta.get("comma_separated_keywords") or meta.get("keywords", ""))
    
    return {
        "filename": filename,
        "title": title,
        "description": desc,
        "keywords": ", ".join(keywords),
        "keyword_count": len(keywords)
    }

def get_thumbnail_bytes(image_path, max_dim=1024):
    with Image.open(image_path) as img:
        img_copy = img.convert("RGB")
        img_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img_copy.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

def call_gemini(client, system_instruction, thumb_bytes, context_hint, filename):
    user_prompt = f"""
[VISUAL_ANALYSIS]: Analyze this photo. Subject context / location: {context_hint}
[IS_AI_GENERATED]: False
[FILE_TYPE]: Photo

Generate Vecteezy metadata JSON strictly according to guidelines.
The filename must be exactly: "{filename}"
"""
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=[
            types.Part.from_bytes(data=thumb_bytes, mime_type="image/jpeg"),
            user_prompt
        ],
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.3
        )
    )
    raw_text = response.text.strip()
    # Strip markdown if any
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)
    return json.loads(raw_text)

def main():
    target_dir = r"G:\upload_temp"
    os.makedirs(target_dir, exist_ok=True)
    
    print(f"Target directory: {target_dir}", flush=True)
    print(f"Total images to process: {len(IMAGES_CONFIG)}", flush=True)
    
    json_path = os.path.join(target_dir, "vecteezy_metadata.json")
    csv_path = os.path.join(target_dir, "vecteezy.csv")
    
    results = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    for item in loaded:
                        results[item["filename"]] = item
                elif isinstance(loaded, dict):
                    results = loaded
            print(f"Loaded {len(results)} existing metadata entries.", flush=True)
        except Exception as e:
            print(f"Could not load existing metadata: {e}", flush=True)
            results = {}

    system_instruction = load_system_prompt()
    client = genai.Client()
    
    for idx, (src_path, context_hint) in enumerate(IMAGES_CONFIG, 1):
        filename = os.path.basename(src_path)
        dest_path = os.path.join(target_dir, filename)
        
        print(f"\n[{idx}/{len(IMAGES_CONFIG)}] Processing: {filename}", flush=True)
        
        # 1. Copy file to target directory
        if not os.path.exists(dest_path) or os.path.getsize(dest_path) != os.path.getsize(src_path):
            print(f"  Copying {src_path} -> {dest_path}", flush=True)
            shutil.copy2(src_path, dest_path)
        else:
            print(f"  Already copied: {filename}", flush=True)

        # Skip Gemini if already processed
        if filename in results:
            print(f"  Already processed metadata for {filename}", flush=True)
            continue
            
        # 2. Get thumbnail for Gemini
        thumb_bytes = get_thumbnail_bytes(src_path)
        
        # 3. Call Gemini with retry
        meta = None
        for attempt in range(3):
            try:
                meta = call_gemini(client, system_instruction, thumb_bytes, context_hint, filename)
                break
            except Exception as e:
                print(f"  Attempt {attempt+1} failed: {e}. Retrying in 2 seconds...", flush=True)
                time.sleep(2)
                
        if not meta:
            print(f"  ERROR: Could not generate metadata for {filename}", flush=True)
            continue
            
        cleaned = clean_metadata_response(meta, filename)
        
        # Check keyword count
        if cleaned["keyword_count"] < 10:
            print(f"  WARNING: Only {cleaned['keyword_count']} keywords generated for {filename}. Augmenting...", flush=True)
            kws = [k.strip() for k in cleaned["keywords"].split(",") if k.strip()]
            extra = ["outdoor", "daylight", "scenic", "heritage", "tourism", "destination", "travel photography"]
            for ek in extra:
                if len(kws) >= 15:
                    break
                if ek not in kws:
                    kws.append(ek)
            cleaned["keywords"] = ", ".join(kws)
            cleaned["keyword_count"] = len(kws)
            
        print(f"  Title: {cleaned['title']}", flush=True)
        print(f"  Keywords ({cleaned['keyword_count']}): {cleaned['keywords'][:80]}...", flush=True)
        results[filename] = cleaned
        
        # Save progress incrementally
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(list(results.values()), f, indent=2, ensure_ascii=False)
            
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Filename", "Title", "Description", "Keywords"])
            for r in results.values():
                writer.writerow([r["filename"], r["title"], r["description"], r["keywords"]])

    print(f"\n[SUCCESS] Generated Vecteezy CSV: {csv_path}", flush=True)
    print(f"[SUCCESS] Saved metadata JSON: {json_path}", flush=True)
    print(f"Finished processing {len(results)}/{len(IMAGES_CONFIG)} images.", flush=True)

if __name__ == "__main__":
    main()
