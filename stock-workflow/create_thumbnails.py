#!/usr/bin/env python3
"""
create_thumbnails.py
Creates downscaled preview images in a '_temp' subfolder to save bandwidth and LLM tokens,
and extracts EXIF / XMP / GPS metadata from the original images into a JSON file.
"""

import os
import sys
import json
import argparse
import re
from PIL import Image, ExifTags


def get_decimal_from_dms(dms, ref):
    if not dms:
        return None
    try:
        degrees = float(dms[0])
        minutes = float(dms[1]) / 60.0
        seconds = float(dms[2]) / 3600.0
        if ref in ['S', 'W']:
            degrees = -degrees
            minutes = -minutes
            seconds = -seconds
        return round(degrees + minutes + seconds, 6)
    except Exception:
        return None


def extract_metadata(img, file_path):
    info = {
        "filename": os.path.basename(file_path),
        "date_taken": None,
        "camera_make": None,
        "camera_model": None,
        "gps_latitude": None,
        "gps_longitude": None,
        "width": img.width,
        "height": img.height
    }

    # 1. EXIF standard tags
    exif = img.getexif()
    if exif:
        for tag_id, val in exif.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            if tag_name == "Make":
                info["camera_make"] = str(val).strip()
            elif tag_name == "Model":
                info["camera_model"] = str(val).strip()
            elif tag_name in ["DateTimeOriginal", "DateTime"]:
                info["date_taken"] = str(val).strip()

        # GPS IFD
        try:
            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
            if gps_ifd:
                lat = get_decimal_from_dms(gps_ifd.get(2), gps_ifd.get(1))
                lon = get_decimal_from_dms(gps_ifd.get(4), gps_ifd.get(3))
                info["gps_latitude"] = lat
                info["gps_longitude"] = lon
        except Exception:
            pass

    # 2. XMP metadata fallback (if stripped or embedded by Adobe/Lightroom)
    xmp_raw = img.info.get("xmp", b"")
    if isinstance(xmp_raw, bytes):
        xmp_str = xmp_raw.decode("utf-8", errors="ignore")
    else:
        xmp_str = str(xmp_raw)

    if xmp_str:
        if not info["date_taken"]:
            m = re.search(r'CreateDate="([^"]+)"', xmp_str) or re.search(r'<xmp:CreateDate>([^<]+)', xmp_str)
            if m:
                info["date_taken"] = m.group(1)
        if not info["camera_model"]:
            m = re.search(r'Model="([^"]+)"', xmp_str) or re.search(r'<tiff:Model>([^<]+)', xmp_str)
            if m:
                info["camera_model"] = m.group(1)
        if not info["gps_latitude"]:
            lat_m = re.search(r'GPSLatitude="([^"]+)"', xmp_str) or re.search(r'<exif:GPSLatitude>([^<]+)', xmp_str)
            lon_m = re.search(r'GPSLongitude="([^"]+)"', xmp_str) or re.search(r'<exif:GPSLongitude>([^<]+)', xmp_str)
            if lat_m and lon_m:
                info["gps_latitude"] = lat_m.group(1)
                info["gps_longitude"] = lon_m.group(1)

    return info


def process_directory(input_dir, output_dir=None, max_size=1024, quality=85):
    input_dir = os.path.abspath(input_dir)
    if output_dir is None:
        output_dir = os.path.join(input_dir, "_temp")
    os.makedirs(output_dir, exist_ok=True)

    extensions = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff")
    files = [f for f in sorted(os.listdir(input_dir)) if f.lower().endswith(extensions) and not f.startswith(".")]

    all_metadata = []

    print(f"Processing {len(files)} images from: {input_dir}")
    print(f"Thumbnails output directory: {output_dir}")

    for idx, filename in enumerate(files, 1):
        src_path = os.path.join(input_dir, filename)
        dst_path = os.path.join(output_dir, filename)

        try:
            with Image.open(src_path) as img:
                meta = extract_metadata(img, src_path)
                all_metadata.append(meta)

                # Create downscaled copy
                thumb = img.copy()
                thumb.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                # Convert RGBA to RGB for JPEG if needed
                if thumb.mode in ("RGBA", "P"):
                    thumb = thumb.convert("RGB")
                thumb.save(dst_path, "JPEG", quality=quality)
                print(f"[{idx}/{len(files)}] Resized & extracted: {filename}")
        except Exception as e:
            print(f"Error processing {filename}: {e}", file=sys.stderr)

    meta_json_path = os.path.join(output_dir, "metadata_extracted.json")
    with open(meta_json_path, "w", encoding="utf-8") as f:
        json.dump(all_metadata, f, indent=2, ensure_ascii=False)

    print(f"\nCompleted! Metadata saved to: {meta_json_path}")
    return all_metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create lightweight downscaled thumbnails and extract metadata for stock photos.")
    parser.add_argument("--input", "-i", required=True, help="Input directory containing original high-res photos")
    parser.add_argument("--output", "-o", default=None, help="Output directory for thumbnails (default: <input>/_temp)")
    parser.add_argument("--max-size", "-s", type=int, default=1024, help="Maximum width/height in pixels (default: 1024)")
    parser.add_argument("--quality", "-q", type=int, default=85, help="JPEG quality (default: 85)")

    args = parser.parse_args()
    process_directory(args.input, args.output, args.max_size, args.quality)
