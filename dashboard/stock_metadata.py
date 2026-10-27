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


def _escape_cstr(val: str) -> str:
    """Escape backslashes and newlines for ExifTool #[CSTR] argfile directive."""
    return (
        val.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


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

    clean_title = (title or "").strip().replace("\r", " ").replace("\n", " ")
    clean_desc = (description or clean_title).strip()
    esc_desc = _escape_cstr(clean_desc)
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
        f"#[CSTR]-IPTC:Caption-Abstract={esc_desc}",
        f"-XMP-dc:Title={clean_title}",
        f"#[CSTR]-XMP-dc:Description={esc_desc}",
        f"#[CSTR]-IFD0:ImageDescription={esc_desc}",
        f"#[CSTR]-ExifIFD:UserComment={esc_desc}",
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
        kw_clean = str(kw).strip().replace("\r", " ").replace("\n", " ")
        if kw_clean:
            args.append(f"-IPTC:Keywords={kw_clean}")
            args.append(f"-XMP-dc:Subject={kw_clean}")

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
            res = subprocess.run(
                [exe, "-charset", "filename=utf8", "-@", argfile_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
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

# The 26 official Shutterstock contributor categories
SHUTTERSTOCK_CATEGORIES: List[str] = [
    "Abstract",
    "Animals/Wildlife",
    "Arts",
    "Backgrounds/Textures",
    "Beauty/Fashion",
    "Buildings/Landmarks",
    "Business/Finance",
    "Celebrities",
    "Education",
    "Food and drink",
    "Healthcare/Medical",
    "Holidays",
    "Industrial",
    "Interiors",
    "Miscellaneous",
    "Nature",
    "Objects",
    "Parks/Outdoor",
    "People",
    "Religion",
    "Science",
    "Signs/Symbols",
    "Sports/Recreation",
    "Technology",
    "Transportation",
    "Vintage",
]

_SHUTTERSTOCK_CANONICAL_LOOKUP = {c.lower(): c for c in SHUTTERSTOCK_CATEGORIES}

_SHUTTERSTOCK_ALIASES = {
    # Direct aliases & common variations
    "animals": "Animals/Wildlife",
    "wildlife": "Animals/Wildlife",
    "animal": "Animals/Wildlife",
    "fauna": "Animals/Wildlife",
    "pets": "Animals/Wildlife",
    "art": "Arts",
    "artwork": "Arts",
    "paintings": "Arts",
    "sculpture": "Arts",
    "backgrounds": "Backgrounds/Textures",
    "textures": "Backgrounds/Textures",
    "background": "Backgrounds/Textures",
    "texture": "Backgrounds/Textures",
    "patterns": "Backgrounds/Textures",
    "pattern": "Backgrounds/Textures",
    "beauty": "Beauty/Fashion",
    "fashion": "Beauty/Fashion",
    "buildings": "Buildings/Landmarks",
    "landmarks": "Buildings/Landmarks",
    "building": "Buildings/Landmarks",
    "landmark": "Buildings/Landmarks",
    "architecture": "Buildings/Landmarks",
    "buildings and architecture": "Buildings/Landmarks",
    "buildings & architecture": "Buildings/Landmarks",
    "buildings/architecture": "Buildings/Landmarks",
    "monuments": "Buildings/Landmarks",
    "monument": "Buildings/Landmarks",
    "castle": "Buildings/Landmarks",
    "castles": "Buildings/Landmarks",
    "business": "Business/Finance",
    "finance": "Business/Finance",
    "corporate": "Business/Finance",
    "celebrity": "Celebrities",
    "education": "Education",
    "learning": "Education",
    "school": "Education",
    "food & drink": "Food and drink",
    "food": "Food and drink",
    "drink": "Food and drink",
    "drinks": "Food and drink",
    "beverage": "Food and drink",
    "beverages": "Food and drink",
    "healthcare": "Healthcare/Medical",
    "medical": "Healthcare/Medical",
    "health": "Healthcare/Medical",
    "medicine": "Healthcare/Medical",
    "holiday": "Holidays",
    "industry": "Industrial",
    "manufacturing": "Industrial",
    "interior": "Interiors",
    "indoor": "Interiors",
    "indoors": "Interiors",
    "misc": "Miscellaneous",
    "general": "Miscellaneous",
    "landscapes": "Nature",
    "landscape": "Nature",
    "the environment": "Nature",
    "environment": "Nature",
    "plants and flowers": "Nature",
    "plants": "Nature",
    "flowers": "Nature",
    "flora": "Nature",
    "scenery": "Nature",
    "object": "Objects",
    "still life": "Objects",
    "item": "Objects",
    "items": "Objects",
    "parks": "Parks/Outdoor",
    "outdoor": "Parks/Outdoor",
    "outdoors": "Parks/Outdoor",
    "park": "Parks/Outdoor",
    "garden": "Parks/Outdoor",
    "gardens": "Parks/Outdoor",
    "countryside": "Parks/Outdoor",
    "rural": "Parks/Outdoor",
    "hobbies and leisure": "Parks/Outdoor",
    "person": "People",
    "human": "People",
    "lifestyle": "People",
    "culture and religion": "Religion",
    "religious": "Religion",
    "culture": "Religion",
    "church": "Religion",
    "spirituality": "Religion",
    "scientific": "Science",
    "research": "Science",
    "signs": "Signs/Symbols",
    "symbols": "Signs/Symbols",
    "sign": "Signs/Symbols",
    "symbol": "Signs/Symbols",
    "sports": "Sports/Recreation",
    "sport": "Sports/Recreation",
    "recreation": "Sports/Recreation",
    "fitness": "Sports/Recreation",
    "tech": "Technology",
    "digital": "Technology",
    "computers": "Technology",
    "computer": "Technology",
    "transport": "Transportation",
    "vehicles": "Transportation",
    "vehicle": "Transportation",
    "cars": "Transportation",
    "car": "Transportation",
    "trains": "Transportation",
    "retro": "Vintage",
    "antique": "Vintage",
    "historical": "Vintage",
    "historic": "Vintage",
    "nostalgic": "Vintage",
    "heritage": "Vintage",
    # Adobe category numeric IDs
    "1": "Animals/Wildlife",
    "2": "Buildings/Landmarks",
    "3": "Business/Finance",
    "4": "Food and drink",
    "5": "Nature",
    "6": "Abstract",
    "7": "Food and drink",
    "8": "Backgrounds/Textures",
    "9": "Sports/Recreation",
    "10": "Industrial",
    "11": "Nature",
    "12": "People",
    "13": "People",
    "14": "Nature",
    "15": "Religion",
    "16": "Science",
    "17": "People",
    "18": "Sports/Recreation",
    "19": "Technology",
    "20": "Transportation",
    "21": "Buildings/Landmarks",
}

_SHUTTERSTOCK_DEFAULT_PAIRS = {
    "Buildings/Landmarks": "Parks/Outdoor",
    "Nature": "Parks/Outdoor",
    "Parks/Outdoor": "Nature",
    "Religion": "Buildings/Landmarks",
    "Transportation": "Technology",
    "Technology": "Industrial",
    "People": "Parks/Outdoor",
    "Animals/Wildlife": "Nature",
    "Abstract": "Backgrounds/Textures",
    "Backgrounds/Textures": "Abstract",
    "Interiors": "Buildings/Landmarks",
    "Vintage": "Buildings/Landmarks",
    "Arts": "Vintage",
    "Food and drink": "Objects",
    "Objects": "Miscellaneous",
    "Industrial": "Technology",
    "Business/Finance": "Technology",
    "Healthcare/Medical": "Science",
    "Science": "Technology",
    "Education": "People",
    "Celebrities": "People",
    "Beauty/Fashion": "People",
    "Holidays": "Religion",
    "Signs/Symbols": "Objects",
    "Sports/Recreation": "Parks/Outdoor",
    "Miscellaneous": "Objects",
}

_CONTEXT_CATEGORY_TRIGGERS: List[Tuple[str, List[str]]] = [
    ("Buildings/Landmarks", ["church", "tower", "castle", "fortress", "palace", "cathedral", "chapel", "building", "landmark", "monument", "architecture", "facade", "ruins", "bridge", "spire", "steeple"]),
    ("Religion", ["church", "cathedral", "chapel", "monastery", "cross", "crucifix", "jesus", "shrine", "temple", "altar", "christian", "catholic", "religion", "religious", "spiritual", "saint", "faith", "basilica"]),
    ("Nature", ["nature", "tree", "trees", "grass", "field", "meadow", "sky", "cloud", "clouds", "landscape", "hill", "hills", "mountain", "lake", "river", "sea", "flower", "poppy", "poppies", "forest", "sunlight", "rapeseed", "canola", "pastoral"]),
    ("Parks/Outdoor", ["park", "outdoor", "outdoors", "garden", "rural", "countryside", "scenic", "path", "trail", "walkway"]),
    ("Transportation", ["train", "railway", "rail", "tram", "station", "tracks", "car", "vehicle", "bus", "road", "street", "highway", "traffic", "subway", "metro", "locomotive"]),
    ("Vintage", ["vintage", "historic", "historical", "medieval", "antique", "retro", "heritage", "ancient", "baroque", "gothic", "renaissance"]),
    ("Interiors", ["interior", "interiors", "indoor", "room", "hall", "ceiling", "furniture", "inside", "corridor"]),
    ("People", ["people", "person", "man", "woman", "tourist", "tourists", "crowd", "children", "pedestrian", "model"]),
    ("Animals/Wildlife", ["animal", "wildlife", "bird", "fauna", "deer", "horse", "dog", "cat"]),
    ("Food and drink", ["food", "drink", "wine", "coffee", "fruit", "vegetable", "dining", "meal"]),
    ("Technology", ["technology", "computer", "digital", "screen", "electronic", "device", "modern"]),
    ("Industrial", ["industrial", "factory", "manufacture", "crane", "power line", "industry"]),
    ("Business/Finance", ["business", "finance", "money", "office", "bank", "corporate"]),
    ("Sports/Recreation", ["sport", "sports", "fitness", "workout", "bike", "bicycle", "cycling", "recreation"]),
    ("Arts", ["art", "artwork", "painting", "sculpture", "statue", "statues"]),
    ("Backgrounds/Textures", ["texture", "background", "pattern", "surface"]),
    ("Abstract", ["abstract", "surreal", "minimalist"]),
    ("Objects", ["object", "objects", "still life", "tool"]),
    ("Signs/Symbols", ["sign", "symbol", "emblem", "logo"]),
    ("Healthcare/Medical", ["medical", "health", "hospital", "doctor", "medicine"]),
    ("Education", ["education", "school", "university", "book", "student"]),
    ("Holidays", ["holiday", "christmas", "easter", "halloween", "celebration"]),
    ("Beauty/Fashion", ["beauty", "fashion", "dress", "style"]),
    ("Celebrities", ["celebrity", "famous"]),
]


def map_to_shutterstock_categories(
    category_input: Any = None,
    title: str = "",
    description: str = "",
    keywords: Any = None
) -> str:
    """
    Map and validate any platform category, keywords, and description into EXACTLY TWO
    official Shutterstock categories selected from the strict 26-category list.
    Always returns: 'Category1, Category2' (e.g. 'Buildings/Landmarks, Nature').
    """
    valid_cats: List[str] = []

    # 1. Parse existing category inputs
    raw_parts: List[str] = []
    if category_input:
        if isinstance(category_input, (list, tuple, set)):
            raw_parts.extend([str(c).strip() for c in category_input if str(c).strip()])
        elif isinstance(category_input, str):
            for part in category_input.replace(";", ",").split(","):
                part_clean = part.strip()
                if part_clean:
                    raw_parts.append(part_clean)

    for p in raw_parts:
        p_lower = p.lower()
        canonical = _SHUTTERSTOCK_CANONICAL_LOOKUP.get(p_lower) or _SHUTTERSTOCK_ALIASES.get(p_lower)
        if canonical and canonical not in valid_cats:
            valid_cats.append(canonical)
        if len(valid_cats) >= 2:
            break

    # 2. Build context text for keyword triggers
    if isinstance(keywords, (list, tuple, set)):
        kws_str = " ".join(str(k) for k in keywords)
    else:
        kws_str = str(keywords or "")
    combined_text = f"{title} {description} {kws_str}".lower()

    # 3. If we need more categories, inspect context triggers
    if len(valid_cats) < 2:
        for cat_candidate, triggers in _CONTEXT_CATEGORY_TRIGGERS:
            if cat_candidate not in valid_cats:
                if any(t in combined_text for t in triggers):
                    valid_cats.append(cat_candidate)
                    if len(valid_cats) >= 2:
                        break

    # 4. If still only 1 category, pick companion default pair
    if len(valid_cats) == 1:
        c1 = valid_cats[0]
        fallback = _SHUTTERSTOCK_DEFAULT_PAIRS.get(c1, "Parks/Outdoor" if c1 != "Parks/Outdoor" else "Nature")
        if fallback not in valid_cats:
            valid_cats.append(fallback)

    # 5. If no categories detected at all, default cleanly
    if not valid_cats:
        valid_cats = ["Buildings/Landmarks", "Nature"]
    elif len(valid_cats) == 1:
        valid_cats.append("Nature" if valid_cats[0] != "Nature" else "Parks/Outdoor")

    return f"{valid_cats[0]}, {valid_cats[1]}"


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

    sh_cat = (img.get("shutterstock_categories") or "").strip()
    is_editorial = bool(img.get("is_editorial", False))

    return {
        "filename": Path(img["file_path"]).name if "file_path" in img else img.get("file_name", ""),
        "title": title,
        "description": desc,
        "keywords": kws,
        "category": cat,
        "shutterstock_categories": sh_cat,
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

    # Pond5 PHP parser fails when UTF-8 BOM is present; Vecteezy web parser also strictly requires UTF-8 without BOM
    csv_encoding = "utf-8" if agency_name in ("Pond5", "Vecteezy") else "utf-8-sig"
    with open(csv_path, "w", newline="", encoding=csv_encoding) as f:
        writer = csv.writer(f)

        if agency_name in ("Adobe Stock", "AdobeStock", "Adobe"):
            # Adobe Stock standard specification
            writer.writerow(["Filename", "Title", "Keywords", "Category", "Releases"])
            for r in rows_data:
                writer.writerow([r["filename"], r["title"], r["keywords"], r["category"] or "2", ""])

        elif agency_name == "Vecteezy":
            # Vecteezy standard specification: strictly 4 columns, UTF-8 without BOM
            writer.writerow(["Filename", "Title", "Description", "Keywords"])
            for r in rows_data:
                writer.writerow([r["filename"], r["title"], r["description"], r["keywords"]])

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
            # Shutterstock specification: exactly 2 categories from the official 26 category list
            writer.writerow(["Filename", "Description", "Keywords", "Categories", "Editorial", "Mature content", "illustration"])
            for r in rows_data:
                sh_cats = map_to_shutterstock_categories(
                    r.get("shutterstock_categories") or r.get("category"),
                    title=r.get("title", ""),
                    description=r.get("description", ""),
                    keywords=r.get("keywords", "")
                )
                writer.writerow([
                    r["filename"],
                    r["description"] or r["title"],
                    r["keywords"],
                    sh_cats,
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
