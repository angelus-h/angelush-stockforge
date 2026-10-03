#!/usr/bin/env python3
"""
Art Heroes / Werk aan de Muur Metadata Applicator
Batch embeds fine art POD metadata (Title, 3-Paragraph Description, TOP 12 Keywords, Artist)
into JPEG images for Art Heroes / Werk aan de Muur marketplace compliance.
"""

import os
import sys
import json
import time
import shutil
import argparse
import tempfile
import subprocess
from pathlib import Path


def find_exiftool():
    """Locate ExifTool executable."""
    found = shutil.which("exiftool")
    if found:
        return found
    fallback = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\ExifTool\ExifTool.exe"))
    if fallback.exists():
        return str(fallback)
    raise FileNotFoundError("ExifTool executable not found in PATH or standard install directory.")


def apply_metadata_to_image(exiftool_path, image_path, meta):
    """Embed metadata across EXIF, IPTC, and XMP with bloat removal and UTF-8 encoding."""
    title = meta["title"]
    description = meta["description"]
    keywords = meta["keywords"][:12]

    cmd = [
        "-m",
        "-overwrite_original_in_place",
        "-charset", "utf8",
        "-charset", "iptc=utf8",
        "-charset", "exif=utf8",
        "-IPTC:CodedCharacterSet=UTF8",
        "-IFD0:XPComment=",
        "-IFD0:XPTitle=",
        "-IFD0:XPKeywords=",
        f"-IPTC:ObjectName={title[:64]}",
        f"-IPTC:Headline={title}",
        f"-IPTC:Caption-Abstract={description}",
        f"-XMP-dc:Title={title}",
        f"-XMP-dc:Description={description}",
        f"-IFD0:ImageDescription={description}",
        f"-ExifIFD:UserComment={description}",
        "-Artist=Angelus H",
        "-By-line=Angelus H",
        "-CopyrightNotice=Angelus H",
        "-PhotoshopThumbnail=",
        "-XMP-crs:all=",
        "-photoshop:IPTCDigest=new",
        "-IPTC:Keywords=",
        "-XMP-dc:Subject=",
    ]

    for kw in keywords:
        cmd.append(f"-IPTC:Keywords={kw}")
        cmd.append(f"-XMP-dc:Subject={kw}")

    cmd.append(str(image_path))

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as argfile:
        for a in cmd:
            argfile.write(f"{a}\n")
        argfile_path = argfile.name

    try:
        for _ in range(3):
            res = subprocess.run([exiftool_path, "-@", argfile_path], capture_output=True, text=True, encoding="utf-8", errors="replace")
            if res.returncode == 0 and "Error" not in res.stderr:
                return
            time.sleep(0.3)
        raise RuntimeError(f"ExifTool error on {Path(image_path).name}: {res.stderr or res.stdout}")
    finally:
        try:
            os.remove(argfile_path)
        except OSError:
            pass


def process_directory(directory_path):
    """Process all JPEGs with matching JSON metadata files in the directory."""
    dir_path = Path(directory_path)
    exiftool = find_exiftool()

    images = sorted(
        [f for f in dir_path.glob("*.jpg")] +
        [f for f in dir_path.glob("*.jpeg")] +
        [f for f in dir_path.glob("*.png")]
    )
    if not images:
        print(f"No JPEG or PNG images found in {directory_path}")
        return

    print(f"Found {len(images)} images in {dir_path.resolve()}. Applying Art Heroes metadata...")

    updated = 0
    for img in images:
        json_path = dir_path / f"{img.stem}_metadata.json"
        if not json_path.exists():
            print(f"Skipping {img.name} (no {json_path.name} found)")
            continue

        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        try:
            apply_metadata_to_image(exiftool, img, meta)
            print(f"✓ Embedded metadata in {img.name}")
            updated += 1
        except Exception as e:
            print(f"✗ Failed {img.name}: {e}")

    print(f"\nCompleted: {updated}/{len(images)} images successfully updated.")


def main():
    parser = argparse.ArgumentParser(description="Embed Art Heroes fine art POD metadata into images.")
    parser.add_argument("directory", help="Path to directory containing images and *_metadata.json files.")
    args = parser.parse_args()

    process_directory(args.directory)


if __name__ == "__main__":
    main()
