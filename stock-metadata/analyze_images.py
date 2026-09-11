import requests
import base64
import sys
import os
import glob
import csv
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim

OLLAMA_URL = "http://localhost:11434/api/generate"
OUTPUT_DIR = r"F:\AI-WORK\ai-workflows\stock-metadata\results"

geolocator = Nominatim(user_agent="stock-metadata-tool")

def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def get_gps_coords(image_path):
    try:
        img = Image.open(image_path)
        exif_data = img._getexif()
        if not exif_data:
            return None, None

        gps_info = {}
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for gps_tag_id, gps_value in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag] = gps_value

        if not gps_info:
            return None, None

        def to_decimal(coords, ref):
            d, m, s = [float(c) for c in coords]
            decimal = d + m / 60 + s / 3600
            if ref in ("S", "W"):
                decimal = -decimal
            return decimal

        lat = to_decimal(gps_info["GPSLatitude"], gps_info["GPSLatitudeRef"])
        lon = to_decimal(gps_info["GPSLongitude"], gps_info["GPSLongitudeRef"])
        return lat, lon
    except Exception:
        return None, None

def get_location_name(lat, lon):
    result = {"name": f"{lat:.4f}, {lon:.4f}", "details": {}}
    for zoom in (18, 16, 14):
        try:
            location = geolocator.reverse(f"{lat}, {lon}", language="en", zoom=zoom)
            if location:
                addr = location.raw.get("address", {})
                if not result["details"]:
                    result["details"] = addr
                parts = []
                for key in ("tourism", "building", "amenity", "historic", "leisure", "shop", "neighbourhood", "suburb", "city", "town", "village", "state", "country"):
                    if key in addr:
                        parts.append(addr[key])
                if parts:
                    result["name"] = ", ".join(parts)
                    return result
        except Exception:
            pass
    return result

def call_ollama(model, prompt, image_b64=None):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    if image_b64:
        payload["images"] = [image_b64]
    response = requests.post(OLLAMA_URL, json=payload, timeout=180)
    if response.status_code == 200:
        return response.json().get("response", "").strip()
    return f"Error: {response.status_code}"

def analyze_image(image_path):
    print(f"\n{'='*60}")
    print(f"  {os.path.basename(image_path)}")
    print(f"{'='*60}")

    # Step 1: Extract GPS location
    lat, lon = get_gps_coords(image_path)
    location = None
    location_name = None
    if lat and lon:
        location = get_location_name(lat, lon)
        location_name = location["name"]
        print(f"  LOCATION:  {location_name}")
        print(f"  GPS:       {lat:.5f}, {lon:.5f}")
    else:
        print(f"  LOCATION:  (no GPS data)")

    # Step 2: Moondream describes the image (with location hint if available)
    img_b64 = encode_image(image_path)
    print("  [1/2] Moondream analyzing image...")
    if location_name:
        vision_prompt = f"This photo was taken in {location_name}. What is in this image? Describe it in detail."
    else:
        vision_prompt = "What is in this image? Describe it in detail."
    description = call_ollama("moondream", vision_prompt, img_b64)
    print(f"  VISION:    {description}")

    # Step 3: Qwen generates stock metadata with full context
    print("  [2/2] Qwen2.5 generating stock metadata...")
    if location_name:
        location_context = f"""

Location: {location_name} (GPS: {lat:.5f}, {lon:.5f})

IMPORTANT: The GPS coordinates and location name are AUTHORITATIVE — they come from the camera's GPS sensor.
The image description above comes from a small AI vision model that may misidentify buildings or landmarks.
If the description conflicts with what you know about this location, TRUST THE GPS LOCATION and use your own knowledge about what is actually at these coordinates.
Use your knowledge about this specific place — landmarks, architecture, history, notable features.
The correct location name should appear naturally in the title and description."""
    else:
        location_context = ""

    metadata_prompt = f"""You are a stock photography metadata expert. Based on the image description and location, generate metadata optimized for stock photo websites (Shutterstock, Adobe Stock, iStock).

Image description: {description}{location_context}

Respond in EXACTLY this format, nothing else:
TITLE: [one short compelling title, include specific location/landmark name if known]
DESCRIPTION: [one detailed sentence, max 200 characters, naturally mention the place]
KEYWORDS: [20 relevant keywords comma-separated, include: location name, country, region, specific landmarks, scene type, mood, season if visible]"""

    metadata = call_ollama("qwen2.5:7b", metadata_prompt)
    print(f"  {metadata}")

    title = ""
    desc_final = ""
    keywords = ""
    for line in metadata.split("\n"):
        line = line.strip()
        if line.upper().startswith("TITLE:"):
            title = line[6:].strip()
        elif line.upper().startswith("DESCRIPTION:"):
            desc_final = line[12:].strip()
        elif line.upper().startswith("KEYWORDS:"):
            keywords = line[9:].strip()

    return {
        "file": os.path.basename(image_path),
        "path": image_path,
        "location": location_name or "",
        "gps": f"{lat:.5f}, {lon:.5f}" if lat else "",
        "title": title,
        "description": desc_final,
        "keywords": keywords,
        "vision_raw": description
    }

def find_images(path):
    extensions = ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG")
    if os.path.isdir(path):
        found = []
        for ext in extensions:
            found.extend(glob.glob(os.path.join(path, "**", ext), recursive=True))
        return sorted(set(found))
    elif os.path.isfile(path):
        return [path]
    return []

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py -3.12 analyze_images.py <image_or_folder> [image2] ...")
        print("  Folder: analyzes first 5 images found")
        sys.exit(1)

    images = []
    for arg in sys.argv[1:]:
        images.extend(find_images(arg))

    if not images:
        print("No images found.")
        sys.exit(1)

    first_arg = sys.argv[1]
    if os.path.isdir(first_arg):
        output_dir = first_arg
    else:
        output_dir = os.path.dirname(first_arg)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(output_dir, f"stock_metadata_{timestamp}.csv")

    print(f"Analyzing {len(images)} image(s)...")
    print(f"  Moondream -> image description")
    print(f"  EXIF GPS  -> location lookup")
    print(f"  Qwen2.5   -> stock metadata")
    print(f"Results: {csv_path}")

    results = []
    for img in images:
        result = analyze_image(img)
        results.append(result)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "path", "location", "gps", "title", "description", "keywords", "vision_raw"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'='*60}")
    print(f"  Done! {len(results)} image(s) analyzed.")
    print(f"  CSV: {csv_path}")
    print(f"{'='*60}")
