"""
Stock Metadata Engine
- Embeds standardized Microstock & Alamy IPTC / XMP / EXIF headers into JPEG images via ExifTool.
- Generates platform-compliant CSV catalogs for Adobe Stock, Pond5, Vecteezy, Dreamstime, Depositphotos, and Shutterstock.
"""

import os
import csv
import time
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


def find_exiftool() -> str:
    """Locate ExifTool executable in PATH or standard installation directories."""
    found = shutil.which("exiftool")
    if found:
        return found
    fallback = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\ExifTool\ExifTool.exe"))
    if fallback.exists():
        return str(fallback)
    custom_fallbacks = [
        Path(r"C:\Program Files\ExifTool\exiftool.exe"),
        Path(r"C:\Program Files (x86)\ExifTool\exiftool.exe"),
        Path(r"C:\tools\exiftool.exe"),
    ]
    for p in custom_fallbacks:
        if p.exists():
            return str(p)
    raise FileNotFoundError("ExifTool executable not found in PATH or standard install directory.")


def parse_keywords_list(keywords_input: Any, max_count: int = 50) -> List[str]:
    """Parse string or list of keywords into clean unique list."""
    if not keywords_input:
        return []
    if isinstance(keywords_input, str):
        raw_items = [t.strip() for t in keywords_input.replace(";", ",").split(",") if t.strip()]
    elif isinstance(keywords_input, (list, tuple, set)):
        raw_items = [str(t).strip() for t in keywords_input if str(t).strip()]
    else:
        raw_items = []

    # Preserve order while removing duplicates
    seen = set()
    unique_items = []
    for k in raw_items:
        k_lower = k.lower()
        if k_lower not in seen:
            seen.add(k_lower)
            unique_items.append(k)

    return unique_items[:max_count]


def apply_stock_metadata_to_image(
    image_path: Path,
    title: str,
    description: str = "",
    keywords: Any = None,
    artist: str = "Angelus H",
    copyright_notice: str = "Angelus H",
    exiftool_path: Optional[str] = None
) -> None:
    """
    Embed comprehensive Stock & Alamy metadata (IPTC / XMP / EXIF) into image file.
    Does NOT truncate keywords to 12 (embeds up to 50 tags).
    Uses -overwrite_original_in_place and UTF-8 argfile to prevent Windows file locking
    and malformed encoding errors.
    """
    img_path = Path(image_path)
    if not img_path.exists():
        raise FileNotFoundError(f"Image not found on disk: {img_path}")

    exe = exiftool_path or find_exiftool()

    clean_title = (title or "").strip()
    clean_desc = (description or clean_title).strip()
    tag_list = parse_keywords_list(keywords, max_count=50)

    # Clean legacy malformed XP tags and embed clean IPTC / XMP / EXIF
    args = [
        "-m",
        "-overwrite_original_in_place",
        "-charset", "utf8",
        "-charset", "iptc=utf8",
        "-charset", "exif=utf8",
        "-IPTC:CodedCharacterSet=UTF8",
        "-IFD0:XPComment=",
        "-IFD0:XPTitle=",
        "-IFD0:XPKeywords=",
        f"-IPTC:ObjectName={clean_title[:64]}",
        f"-IPTC:Headline={clean_title}",
        f"-IPTC:Caption-Abstract={clean_desc}",
        f"-XMP-dc:Title={clean_title}",
        f"-XMP-dc:Description={clean_desc}",
        f"-IFD0:ImageDescription={clean_desc}",
        f"-ExifIFD:UserComment={clean_desc}",
        f"-Artist={artist}",
        f"-By-line={artist}",
        f"-CopyrightNotice={copyright_notice}",
        "-PhotoshopThumbnail=",
        "-XMP-crs:all=",
        "-photoshop:IPTCDigest=new",
        "-IPTC:Keywords=",
        "-XMP-dc:Subject=",
    ]

    for kw in tag_list:
        args.append(f"-IPTC:Keywords={kw}")
        args.append(f"-XMP-dc:Subject={kw}")

    args.append(str(img_path))

    # Write args to UTF-8 temp argfile to bypass Windows cmd line encoding corruptions
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as argfile:
        for a in args:
            argfile.write(f"{a}\n")
        argfile_path = argfile.name

    max_retries = 3
    last_err = None
    try:
        for attempt in range(max_retries):
            res = subprocess.run([exe, "-@", argfile_path], capture_output=True, text=True, encoding="utf-8", errors="replace")
            # If warning or error occurred, check return code and output
            if res.returncode == 0 and "Error" not in res.stderr:
                return
            last_err = res.stderr or res.stdout
            time.sleep(0.3)
        raise RuntimeError(f"ExifTool error on {img_path.name}: {last_err}")
    finally:
        try:
            os.remove(argfile_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Multi-Agency CSV Catalog Generation
# ---------------------------------------------------------------------------

AGENCY_CSV_FILENAMES = {
    "Adobe Stock": "adobe_stock.csv",
    "Vecteezy": "vecteezy.csv",
    "Pond5": "pond5.csv",
    "Dreamstime": "dreamstime.csv",
    "Depositphotos": "depositphotos.csv",
    "Shutterstock": "shutterstock.csv",
}


def get_image_stock_fields(img: Dict[str, Any], agency_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Helper to extract agency-specific stock metadata.
    Adobe Stock receives Posters.cz Hybrid metadata when hybrid mode is enabled and hybrid metadata exists.
    ALL OTHER AGENCIES (Alamy, Vecteezy, Shutterstock, Depositphotos, Dreamstime, Pond5)
    strictly receive pure, factual Microstock metadata without interior design / wall decor terms.
    """
    is_adobe = agency_name in ("Adobe Stock", "AdobeStock", "Adobe") if agency_name else False
    is_hybrid = bool(img.get("is_adobe_hybrid", 0))

    if is_adobe and is_hybrid and (img.get("adobe_title") or img.get("adobe_keywords") or img.get("adobe_description")):
        title = (img.get("adobe_title") or img.get("stock_title") or img.get("title") or "").strip()
        desc = (img.get("adobe_description") or img.get("stock_description") or img.get("description") or title).strip()
        kws = (img.get("adobe_keywords") or img.get("stock_keywords") or img.get("keywords") or "").strip()
        cat = (img.get("adobe_category") or img.get("stock_category") or "2").strip()
    else:
        title = (img.get("stock_title") or img.get("title") or "").strip()
        desc = (img.get("stock_description") or img.get("description") or title).strip()
        kws = (img.get("stock_keywords") or img.get("keywords") or "").strip()
        cat = (img.get("stock_category") or "2").strip()

    is_editorial = bool(img.get("is_editorial", False))

    return {
        "filename": Path(img["file_path"]).name if "file_path" in img else img.get("file_name", ""),
        "title": title,
        "description": desc,
        "keywords": kws,
        "category": cat,
        "editorial": is_editorial,
    }


def generate_agency_csv(
    images: List[Dict[str, Any]],
    agency_name: str,
    output_dir: Path
) -> Path:
    """
    Generate agency-compliant CSV for the specified images in output_dir.
    Returns the Path to the created CSV file.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_filename = AGENCY_CSV_FILENAMES.get(agency_name, f"{agency_name.lower().replace(' ', '_')}.csv")
    csv_path = out_dir / csv_filename

    rows_data = [get_image_stock_fields(img, agency_name=agency_name) for img in images]

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        if agency_name in ("Adobe Stock", "AdobeStock", "Adobe"):
            # Adobe Stock standard specification
            writer.writerow(["Filename", "Title", "Keywords", "Category", "Releases"])
            for r in rows_data:
                writer.writerow([r["filename"], r["title"], r["keywords"], r["category"] or "2", ""])

        elif agency_name == "Vecteezy":
            # Vecteezy standard specification
            writer.writerow(["Filename", "Title", "Description", "Keywords", "License"])
            for r in rows_data:
                writer.writerow([r["filename"], r["title"], r["description"], r["keywords"], "Commercial"])

        elif agency_name == "Pond5":
            # Pond5 standard specification
            writer.writerow(["originalfilename", "title", "description", "keywords", "editorial"])
            for r in rows_data:
                writer.writerow([
                    r["filename"],
                    r["title"],
                    r["description"],
                    r["keywords"],
                    "yes" if r["editorial"] else "no"
                ])

        elif agency_name == "Dreamstime":
            # Dreamstime photo specification
            writer.writerow(["Filename", "Image Name", "Description", "Category 1", "Category 2", "Category 3", "keywords", "Editorial"])
            for r in rows_data:
                writer.writerow([
                    r["filename"],
                    r["title"],
                    r["description"],
                    r["category"] or "70",
                    "59",
                    "72",
                    r["keywords"],
                    "1" if r["editorial"] else "0"
                ])

        elif agency_name == "Depositphotos":
            # Depositphotos standard batch CSV specification
            writer.writerow(["Filename", "Title", "Description", "Keywords", "Categories", "Model Releases", "Property Releases", "Editorial"])
            for r in rows_data:
                writer.writerow([
                    r["filename"],
                    r["title"],
                    r["description"],
                    r["keywords"],
                    r["category"] or "Travel",
                    "",
                    "",
                    "yes" if r["editorial"] else "no"
                ])

        elif agency_name == "Shutterstock":
            # Shutterstock specification
            writer.writerow(["Filename", "Description", "Keywords", "Categories", "Editorial", "Mature content", "illustration"])
            for r in rows_data:
                writer.writerow([
                    r["filename"],
                    r["description"] or r["title"],
                    r["keywords"],
                    r["category"] or "Buildings/Landmarks, Travel",
                    "yes" if r["editorial"] else "no",
                    "no",
                    "no"
                ])

        else:
            # Generic fallback CSV
            writer.writerow(["Filename", "Title", "Description", "Keywords"])
            for r in rows_data:
                writer.writerow([r["filename"], r["title"], r["description"], r["keywords"]])

    return csv_path
