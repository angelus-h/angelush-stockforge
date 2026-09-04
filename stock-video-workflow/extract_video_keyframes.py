#!/usr/bin/env python3
"""
extract_video_keyframes.py
Extracts keyframes at 10%, 25%, 50%, 75%, and 90% from video files,
extracts GPS coordinates & video technical metadata, and creates
composite filmstrip contact sheets for rapid visual analysis.
"""

import os
import sys
import re
import json
import argparse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
import cv2
import numpy as np
from PIL import Image


def get_gps_from_file(file_path):
    """Extracts ISO 6709 GPS coordinates from MP4 file headers or tail moov atom."""
    try:
        with open(file_path, 'rb') as f:
            # Read first 2MB
            head = f.read(2 * 1024 * 1024)
            m = re.search(rb'([+-]\d{2,3}\.\d{3,})([+-]\d{2,3}\.\d{3,})', head)
            if m:
                lat = float(m.group(1).decode('ascii', errors='ignore'))
                lon = float(m.group(2).decode('ascii', errors='ignore'))
                if abs(lat) <= 90 and abs(lon) <= 180 and not (lat == 0.0 and lon == 0.0):
                    return lat, lon

            # Read last 2MB
            size = os.path.getsize(file_path)
            f.seek(max(0, size - 2 * 1024 * 1024))
            tail = f.read()
            m = re.search(rb'([+-]\d{2,3}\.\d{3,})([+-]\d{2,3}\.\d{3,})', tail)
            if m:
                lat = float(m.group(1).decode('ascii', errors='ignore'))
                lon = float(m.group(2).decode('ascii', errors='ignore'))
                if abs(lat) <= 90 and abs(lon) <= 180 and not (lat == 0.0 and lon == 0.0):
                    return lat, lon
    except Exception:
        pass
    return None, None


KNOWN_CLUSTERS = [
    # (lat_min, lat_max, lon_min, lon_max, city, country, landmark_hint)
    (47.45, 47.55, 19.00, 19.12, "Budapest", "Hungary", "Budapest city center, Danube river"),
    (47.48, 47.55, 19.13, 19.28, "Budapest / Pest County", "Hungary", "Eastern Budapest / Godollo hills"),
    (47.65, 47.72, 19.05, 19.12, "Szentendre", "Hungary", "Danube promenade / Szentendre"),
    (47.75, 47.85, 18.85, 19.00, "Visegrad / Esztergom", "Hungary", "Danube Bend / Castle"),
    (47.15, 47.25, 18.38, 18.48, "Szekesfehervar", "Hungary", "Bory Castle / Historic center"),
    (46.65, 46.85, 16.20, 16.60, "Orseg", "Hungary", "Orseg National Park"),
    (48.10, 48.20, 17.05, 17.20, "Bratislava", "Slovakia", "Bratislava Old Town / Danube"),
    (48.78, 48.83, 16.78, 16.85, "Lednice", "Czech Republic", "Lednice Castle and Park UNESCO World Heritage site, South Moravia"),
    (48.70, 48.85, 16.55, 16.90, "Lednice-Valtice / Mikulov", "Czech Republic", "South Moravia / Lednice UNESCO"),
    (48.80, 48.95, 15.75, 16.10, "Znojmo / Vranov nad Dyji", "Czech Republic", "South Moravia / Vranov Castle & Reservoir"),
    (48.84, 48.87, 15.84, 15.87, "Hardegg", "Austria", "Hardegg Castle / Thayatal National Park"),
    (49.15, 49.22, 15.40, 15.50, "Telc", "Czech Republic", "Telc UNESCO historic center / Chateau / Namesti Zachariase z Hradce"),
    (49.15, 49.25, 16.55, 16.70, "Brno", "Czech Republic", "Brno city center / Spilberk Castle"),
    (49.17, 49.21, 16.74, 16.79, "Tvarozna", "Czech Republic", "Tvarozna, Santon Hill, Battle of Austerlitz (Slavkov) historical Napoleonic battlefield reenactment, South Moravia"),
    (49.18, 49.23, 16.13, 16.18, "Namest nad Oslavou", "Czech Republic", "Namest nad Oslavou Castle & Square"),
    (49.30, 49.50, 16.60, 16.80, "Moravian Karst (Moravsky kras)", "Czech Republic", "Moravia caves and nature"),
    (49.43, 49.48, 16.30, 16.36, "Pernstejn / Nedvedice", "Czech Republic", "Pernstejn Castle / Nedvedice"),
    (49.44, 49.48, 17.00, 17.05, "Plumlov", "Czech Republic", "Plumlov Castle & Reservoir / Prostejov"),
    (49.55, 49.65, 17.20, 17.35, "Olomouc", "Czech Republic", "Olomouc historic center"),
    (50.00, 50.15, 14.35, 14.55, "Prague", "Czech Republic", "Prague Old Town / Charles Bridge")
]


def resolve_location(lat, lon):
    if lat is None or lon is None:
        return {"city": "Unknown", "country": "Unknown", "hint": ""}
    for (lat_min, lat_max, lon_min, lon_max, city, country, hint) in KNOWN_CLUSTERS:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return {"city": city, "country": country, "hint": hint, "lat": lat, "lon": lon}
    return {"city": "Europe", "country": "Europe", "hint": "", "lat": lat, "lon": lon}


import subprocess

def extract_frames_from_video(video_path, output_dir, max_thumb_dim=640):
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    contact_sheet_path = os.path.join(output_dir, f"{base_name}_filmstrip.jpg")
    video_temp_dir = os.path.join(output_dir, base_name)
    
    cmd_probe = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path]
    probe_res = subprocess.run(cmd_probe, capture_output=True, text=True)
    if probe_res.returncode != 0:
        return None
    try:
        data = json.loads(probe_res.stdout)
    except Exception:
        return None

    v_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    width = int(v_stream.get("width", 0))
    height = int(v_stream.get("height", 0))
    duration = float(data.get("format", {}).get("duration", 0))
    
    fps_eval = v_stream.get("r_frame_rate", "30/1")
    if "/" in fps_eval:
        num, den = fps_eval.split("/")
        fps = float(num) / float(den) if float(den) > 0 else 30.0
    else:
        fps = float(fps_eval) if fps_eval else 30.0
    total_frames = int(v_stream.get("nb_frames") or (duration * fps))

    if duration <= 0:
        return None

    # Date parsing from filename if standard YYYYMMDD_HHMMSS
    date_str = "Unknown"
    date_match = re.search(r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', base_name)
    if date_match:
        year, month, day, hour, minute, second = date_match.groups()
        date_str = f"{year}-{month}-{day} {hour}:{minute}:{second}"

    lat, lon = get_gps_from_file(video_path)
    loc_info = resolve_location(lat, lon)

    if os.path.exists(contact_sheet_path):
        return {
            "filename": os.path.basename(video_path),
            "resolution": f"{width}x{height}",
            "is_4k": width >= 3840,
            "duration_seconds": round(duration, 2),
            "fps": round(fps, 2),
            "total_frames": total_frames,
            "date_recorded": date_str,
            "gps_latitude": lat,
            "gps_longitude": lon,
            "location": loc_info,
            "contact_sheet": contact_sheet_path,
            "frame_dir": video_temp_dir
        }

    percentages = [10, 25, 50, 75, 90]
    extracted_frames = []
    os.makedirs(video_temp_dir, exist_ok=True)

    for p in percentages:
        timestamp = (p / 100.0) * duration
        out_frame_path = os.path.join(video_temp_dir, f"frame_{p}pct.jpg")
        cmd_ffmpeg = [
            "ffmpeg", "-y", "-ss", f"{timestamp:.3f}", "-i", video_path,
            "-vframes", "1", "-update", "1", "-vf", f"scale='min({max_thumb_dim},iw)':-1",
            "-q:v", "2", out_frame_path
        ]
        subprocess.run(cmd_ffmpeg, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(out_frame_path):
            img_data = cv2.imread(out_frame_path)
            if img_data is not None:
                extracted_frames.append((p, img_data, out_frame_path))

    # Create a 5-frame filmstrip contact sheet (grid or horizontal strip)
    contact_sheet_path = None
    if len(extracted_frames) == 5:
        thumb_h, thumb_w = extracted_frames[0][1].shape[:2]
        strip = np.zeros((thumb_h + 30, thumb_w * 5 + 40, 3), dtype=np.uint8)
        strip[:] = (30, 30, 30) # dark gray background

        for i, (pct, img_data, _) in enumerate(extracted_frames):
            x_offset = 10 + i * (thumb_w + 6)
            strip[25:25+thumb_h, x_offset:x_offset+thumb_w] = img_data
            cv2.putText(strip, f"{pct}%", (x_offset + 10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)

        contact_sheet_path = os.path.join(output_dir, f"{base_name}_filmstrip.jpg")
        cv2.imwrite(contact_sheet_path, strip, [cv2.IMWRITE_JPEG_QUALITY, 85])

    return {
        "filename": os.path.basename(video_path),
        "resolution": f"{width}x{height}",
        "is_4k": width >= 3840,
        "duration_seconds": round(duration, 2),
        "fps": round(fps, 2),
        "total_frames": total_frames,
        "date_recorded": date_str,
        "gps_latitude": lat,
        "gps_longitude": lon,
        "location": loc_info,
        "contact_sheet": contact_sheet_path,
        "frame_dir": video_temp_dir
    }


def process_video_directory(input_dir, output_dir=None, limit=None):
    input_dir = os.path.abspath(input_dir)
    if output_dir is None:
        output_dir = os.path.join(input_dir, "_temp_frames")
    os.makedirs(output_dir, exist_ok=True)

    files = [f for f in sorted(os.listdir(input_dir)) if f.lower().endswith(('.mp4', '.mov', '.mkv')) and not f.startswith('.')]
    if limit:
        files = files[:limit]

    print(f"Extracting keyframes (10%, 25%, 50%, 75%, 90%) for {len(files)} videos...")
    results = []

    def _worker(f):
        vpath = os.path.join(input_dir, f)
        res = extract_frames_from_video(vpath, output_dir)
        return f, res

    processed_count = 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_file = {executor.submit(_worker, f): f for f in files}
        for future in as_completed(future_to_file):
            f, res = future.result()
            processed_count += 1
            if res:
                results.append(res)
                print(f"[{processed_count}/{len(files)}] Processed: {f} ({res['resolution']}, {res['duration_seconds']}s, Loc: {res['location']['city']})")
            else:
                print(f"[{processed_count}/{len(files)}] Failed to read: {f}")

    # Sort results by original filename
    results.sort(key=lambda x: x["filename"])

    json_path = os.path.join(output_dir, "video_metadata_summary.json")
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(results, jf, indent=2, ensure_ascii=False)

    print(f"\nAll keyframes and metadata extracted successfully! Saved to: {json_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract 10/25/50/75/90% keyframes and GPS metadata from stock footage.")
    parser.add_argument("--input", "-i", required=True, help="Input directory of video files")
    parser.add_argument("--output", "-o", default=None, help="Output directory for frames (default: <input>/_temp_frames)")
    parser.add_argument("--limit", "-l", type=int, default=None, help="Limit number of videos to process for testing")

    args = parser.parse_args()
    process_video_directory(args.input, args.output, args.limit)
