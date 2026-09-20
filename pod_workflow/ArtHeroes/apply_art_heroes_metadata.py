#!/usr/bin/env python3
"""
Art Heroes / Werk aan de Muur Metadata Applicator
Batch embeds fine art POD metadata (Title, 3-Paragraph Description, TOP 12 Keywords, Artist)
into JPEG images for Art Heroes / Werk aan de Muur marketplace compliance.
"""

import os
import sys
import json
import shutil
import argparse
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
    keywords_semicolon = ";".join(keywords)

    cmd = [
        exiftool_path,
        "-m",
        "-overwrite_original",
        "-charset", "utf8",
        "-charset", "iptc=utf8",
        "-charset", "exif=utf8",
        "-IPTC:CodedCharacterSet=UTF8",
        f"-IPTC:ObjectName={title[:64]}",
        f"-IPTC:Headline={title}",
        f"-IPTC:Caption-Abstract={description}",
        f"-XMP-dc:Title={title}",
        f"-XMP-dc:Description={description}",
        f"-IFD0:ImageDescription={description}",
        f"-IFD0:XPTitle={title}",
        f"-IFD0:XPComment={description}",
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

    cmd.append(f"-IFD0:XPKeywords={keywords_semicolon}")
    cmd.append(str(image_path))

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ExifTool error on {image_path.name}: {res.stderr}")


def process_directory(directory_path):
    """Process all JPEGs with matching JSON metadata files in the directory."""
    dir_path = Path(directory_path)
    exiftool = find_exiftool()

    images = sorted([f for f in dir_path.glob("*.jpg")] + [f for f in dir_path.glob("*.jpeg")])
    if not images:
        print(f"No JPEG images found in {directory_path}")
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
