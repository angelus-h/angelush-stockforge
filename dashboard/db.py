"""
SQLite database layer for Angelush StockForge Dashboard.
Manages media items, platform targets, metadata records, and lifecycle statuses.
"""

import sqlite3
import json
import csv
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "stockforge.db"


_INITIALIZED_DBS = set()

@contextmanager
def get_connection(db_path=None):
    """Yield a SQLite connection with WAL mode, generous busy timeout, and row factory."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except Exception:
        pass
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path=None, force=False):
    """Initialize database tables and indexes (cached per process lifecycle to prevent write-lock contention)."""
    resolved_path = str(Path(db_path).resolve()) if db_path else str(DEFAULT_DB_PATH.resolve())
    if not force and resolved_path in _INITIALIZED_DBS:
        return

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                directory TEXT NOT NULL,
                platform TEXT NOT NULL DEFAULT 'ArtHeroes',
                status TEXT NOT NULL DEFAULT 'NEW',
                title TEXT,
                description TEXT,
                keywords TEXT,
                displate_title TEXT,
                displate_description TEXT,
                displate_tags TEXT,
                artist TEXT DEFAULT 'Angelus H',
                grade TEXT DEFAULT 'NONE',
                qc_status TEXT DEFAULT 'UNCHECKED',
                qc_sharpness REAL,
                qc_dust_count INTEGER DEFAULT 0,
                qc_warnings TEXT,
                custom_prompt TEXT,
                is_editorial INTEGER DEFAULT 0,
                is_ai_generated INTEGER DEFAULT 0,
                is_infrared INTEGER DEFAULT 0,
                is_surreal INTEGER DEFAULT 0,
                stock_title TEXT,
                stock_description TEXT,
                stock_keywords TEXT,
                stock_category TEXT,
                uploaded_to TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Ensure migration columns exist for existing databases
        for col in [
            "displate_title TEXT", "displate_description TEXT", "displate_tags TEXT",
            "grade TEXT DEFAULT 'NONE'",
            "qc_status TEXT DEFAULT 'UNCHECKED'", "qc_sharpness REAL",
            "qc_dust_count INTEGER DEFAULT 0", "qc_warnings TEXT",
            "custom_prompt TEXT",
            "is_editorial INTEGER DEFAULT 0",
            "is_ai_generated INTEGER DEFAULT 0",
            "is_infrared INTEGER DEFAULT 0",
            "is_surreal INTEGER DEFAULT 0",
            "stock_title TEXT", "stock_description TEXT", "stock_keywords TEXT", "stock_category TEXT",
            "uploaded_to TEXT DEFAULT ''"
        ]:
            try:
                cursor.execute(f"ALTER TABLE images ADD COLUMN {col};")
            except sqlite3.OperationalError:
                pass  # column already exists
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_platform ON images(platform);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_status ON images(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_file_name ON images(file_name);")
        conn.commit()
    _INITIALIZED_DBS.add(resolved_path)


SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff",
    ".dng", ".orf", ".odf", ".cr2", ".cr3", ".nef", ".arw", ".pef", ".raf", ".rw2"
}


def scan_and_sync_folder(folder_path, platform="ArtHeroes", db_path=None):
    """
    Scan a directory for image files (JPG, PNG, TIFF, DNG, ORF, RAW),
    automatically importing existing sidecar *_metadata.json files if present.
    """
    init_db(db_path)
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    image_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS]

    imported_count = 0
    updated_count = 0

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        for img in image_files:
            file_path = str(img.resolve())
            file_name = img.name
            directory = str(folder.resolve())

            # Check if sidecar JSON exists
            json_file = folder / f"{img.stem}_metadata.json"
            title = None
            description = None
            keywords_str = None
            disp_title = None
            disp_desc = None
            disp_tags_str = None
            initial_status = "NEW"

            if json_file.exists():
                try:
                    with open(json_file, "r", encoding="utf-8") as jf:
                        meta = json.load(jf)
                        title = meta.get("title")
                        description = meta.get("description")
                        kws = meta.get("keywords", [])
                        if isinstance(kws, list):
                            keywords_str = ", ".join(kws)
                        else:
                            keywords_str = str(kws) if kws else None

                        disp_data = meta.get("displate") if isinstance(meta.get("displate"), dict) else {}
                        disp_title = meta.get("displate_title") or disp_data.get("title")
                        disp_desc = meta.get("displate_description") or disp_data.get("description")
                        disp_tags_raw = meta.get("displate_tags") or disp_data.get("tags")
                        if isinstance(disp_tags_raw, list):
                            disp_tags_str = ", ".join(disp_tags_raw)
                        elif disp_tags_raw:
                            disp_tags_str = str(disp_tags_raw)

                        grade = meta.get("grade", "NONE")
                        if title or disp_title:
                            initial_status = "GENERATED"
                except Exception as e:
                    print(f"Warning reading {json_file.name}: {e}")
                    grade = "NONE"
            else:
                grade = "NONE"

            # Check if record already exists
            cursor.execute("SELECT id, status FROM images WHERE file_path = ?", (file_path,))
            row = cursor.fetchone()

            if row is None:
                cursor.execute("""
                    INSERT INTO images (
                        file_path, file_name, directory, platform, status,
                        title, description, keywords,
                        displate_title, displate_description, displate_tags,
                        grade, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_path, file_name, directory, platform, initial_status,
                    title, description, keywords_str,
                    disp_title, disp_desc, disp_tags_str,
                    grade, datetime.now()
                ))
                imported_count += 1
            else:
                # Update existing if new sidecar metadata is available
                if title or disp_title:
                    cursor.execute("""
                        UPDATE images 
                        SET title = COALESCE(title, ?),
                            description = COALESCE(description, ?),
                            keywords = COALESCE(keywords, ?),
                            displate_title = COALESCE(displate_title, ?),
                            displate_description = COALESCE(displate_description, ?),
                            displate_tags = COALESCE(displate_tags, ?),
                            updated_at = ?
                        WHERE id = ?
                    """, (title, description, keywords_str, disp_title, disp_desc, disp_tags_str, datetime.now(), row["id"]))
                    updated_count += 1

        conn.commit()

    return {"scanned": len(image_files), "imported": imported_count, "updated": updated_count}


def get_images(platform=None, status=None, search_query=None, folder_path=None, qc_status=None, grade=None, uploaded_filter=None, db_path=None, **kwargs):
    """Retrieve filtered images."""
    init_db(db_path)
    uploaded_filter = uploaded_filter or kwargs.get("uploaded_filter")
    query = "SELECT * FROM images WHERE 1=1"
    params = []

    if folder_path:
        norm_folder = str(Path(folder_path).resolve())
        query += " AND (file_path LIKE ? OR file_path LIKE ? OR file_path LIKE ?)"
        params.extend([f"{norm_folder}\\%", f"{norm_folder}/%", f"{norm_folder}%"])

    if platform and platform != "ALL":
        if platform == "Displate":
            query += " AND (platform = 'Displate' OR (displate_title IS NOT NULL AND displate_title != ''))"
        elif platform == "ArtHeroes":
            query += " AND (platform = 'ArtHeroes' OR (title IS NOT NULL AND title != ''))"
        else:
            query += " AND platform = ?"
            params.append(platform)

    if status and status != "ALL":
        query += " AND status = ?"
        params.append(status)

    if qc_status and qc_status != "ALL":
        query += " AND qc_status = ?"
        params.append(qc_status)

    if grade and grade != "ALL":
        if grade in ("NONE", "UNASSIGNED"):
            query += " AND (grade IS NULL OR grade = '' OR grade = 'NONE')"
        elif grade == "FINE_ART":
            query += " AND grade IN ('FINE_ART', 'BOTH')"
        elif grade == "STOCK":
            query += " AND grade IN ('STOCK', 'BOTH')"
        elif grade == "BOTH":
            query += " AND grade = 'BOTH'"
        else:
            query += " AND grade = ?"
            params.append(grade)

    if uploaded_filter and uploaded_filter != "ALL":
        if uploaded_filter == "NOT_UPLOADED":
            query += " AND (uploaded_to IS NULL OR uploaded_to = '')"
        elif uploaded_filter == "ANY_UPLOADED":
            query += " AND (uploaded_to IS NOT NULL AND uploaded_to != '')"
        else:
            query += " AND uploaded_to LIKE ?"
            params.append(f"%{uploaded_filter}%")

    if search_query:
        query += " AND (file_name LIKE ? OR title LIKE ? OR keywords LIKE ? OR displate_title LIKE ? OR displate_tags LIKE ? OR stock_title LIKE ? OR stock_keywords LIKE ?)"
        like_str = f"%{search_query}%"
        params.extend([like_str, like_str, like_str, like_str, like_str, like_str, like_str])

    query += " ORDER BY file_name ASC"

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_known_folders(db_path=None):
    """Return distinct parent directory paths of all registered images."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT file_path FROM images")
        rows = cursor.fetchall()
        folders = sorted(list({str(Path(r[0]).parent) for r in rows if r and r[0]}))
        return folders


def get_image_by_id(image_id, db_path=None):
    """Get single image record by ID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_image(image_id, title=None, description=None, keywords=None, 
                 displate_title=None, displate_description=None, displate_tags=None,
                 status=None, platform=None, qc_status=None, qc_sharpness=None,
                 qc_dust_count=None, qc_warnings=None, custom_prompt=None, grade=None,
                 is_editorial=None, is_ai_generated=None, is_infrared=None, is_surreal=None,
                 stock_title=None, stock_description=None,
                 stock_keywords=None, stock_category=None, uploaded_to=None, db_path=None, **kwargs):
    """Update fields of an image record."""
    fields = []
    params = []

    if title is not None:
        fields.append("title = ?")
        params.append(title)
    if description is not None:
        fields.append("description = ?")
        params.append(description)
    if keywords is not None:
        fields.append("keywords = ?")
        params.append(keywords)
    if displate_title is not None:
        fields.append("displate_title = ?")
        params.append(displate_title)
    if displate_description is not None:
        fields.append("displate_description = ?")
        params.append(displate_description)
    if displate_tags is not None:
        fields.append("displate_tags = ?")
        params.append(displate_tags)
    if is_editorial is not None:
        fields.append("is_editorial = ?")
        params.append(1 if is_editorial else 0)
    if is_ai_generated is not None:
        fields.append("is_ai_generated = ?")
        params.append(1 if is_ai_generated else 0)
    if is_infrared is not None:
        fields.append("is_infrared = ?")
        params.append(1 if is_infrared else 0)
    if is_surreal is not None:
        fields.append("is_surreal = ?")
        params.append(1 if is_surreal else 0)
    if stock_title is not None:
        fields.append("stock_title = ?")
        params.append(stock_title)
    if stock_description is not None:
        fields.append("stock_description = ?")
        params.append(stock_description)
    if stock_keywords is not None:
        fields.append("stock_keywords = ?")
        params.append(stock_keywords)
    if stock_category is not None:
        fields.append("stock_category = ?")
        params.append(stock_category)
    if uploaded_to is not None:
        fields.append("uploaded_to = ?")
        params.append(uploaded_to)
    if status is not None:
        fields.append("status = ?")
        params.append(status)
    if platform is not None:
        fields.append("platform = ?")
        params.append(platform)
    if grade is not None:
        fields.append("grade = ?")
        params.append(grade)
    if qc_status is not None:
        fields.append("qc_status = ?")
        params.append(qc_status)
    if qc_sharpness is not None:
        fields.append("qc_sharpness = ?")
        params.append(qc_sharpness)
    if qc_dust_count is not None:
        fields.append("qc_dust_count = ?")
        params.append(qc_dust_count)
    if qc_warnings is not None:
        fields.append("qc_warnings = ?")
        params.append(qc_warnings)
    if custom_prompt is not None:
        fields.append("custom_prompt = ?")
        params.append(custom_prompt)

    # Extra kwargs safety for hot-reloads
    for k, v in kwargs.items():
        if k in ("is_ai_generated", "is_infrared", "is_surreal", "is_editorial") and v is not None and f"{k} = ?" not in fields:
            fields.append(f"{k} = ?")
            params.append(1 if v else 0)
        elif k in ("stock_title", "stock_description", "stock_keywords", "stock_category") and v is not None and f"{k} = ?" not in fields:
            fields.append(f"{k} = ?")
            params.append(v)

    if not fields:
        return

    fields.append("updated_at = ?")
    params.append(datetime.now())
    params.append(image_id)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE images SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()


def delete_image(image_id, delete_from_disk=True, db_path=None):
    """
    Delete image record from database and optionally remove the file and sidecar JSON from disk.
    """
    img = get_image_by_id(image_id, db_path=db_path)
    if not img:
        return False, "Image not found in database."

    file_path = Path(img["file_path"])
    disk_deleted = False

    if delete_from_disk:
        try:
            if file_path.exists():
                file_path.unlink()
                disk_deleted = True
            # Also delete sidecar JSON if present
            sidecar_json = file_path.parent / f"{file_path.stem}_metadata.json"
            if sidecar_json.exists():
                sidecar_json.unlink()
            # Also delete XMP sidecars if present (common for RAW/DNG culling)
            for xmp_cand in [
                file_path.with_suffix(".xmp"),
                file_path.with_suffix(".XMP"),
                file_path.parent / f"{file_path.name}.xmp",
                file_path.parent / f"{file_path.name}.XMP"
            ]:
                if xmp_cand.exists():
                    xmp_cand.unlink()
            # Also delete any diagnostic map
            diag_file = Path(__file__).resolve().parent / f"_temp_diag_{image_id}.jpg"
            if diag_file.exists():
                diag_file.unlink()
        except Exception as e:
            return False, f"Failed to delete file from disk: {e}"

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM images WHERE id = ?", (image_id,))
        conn.commit()

    msg = f"Permanently deleted {img['file_name']}" + (" from disk and database." if disk_deleted else " from database.")
    return True, msg


def export_catalog_csv(output_csv_path, platform="ArtHeroes", folder_path=None, db_path=None):
    """Export current images matching platform to a master CSV catalog."""
    images = get_images(platform="ALL", folder_path=folder_path, db_path=db_path)
    out_path = Path(output_csv_path)

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if platform == "Displate":
            writer.writerow(["Filename", "Title", "Description", "Tags", "Grade", "Status"])
            for img in images:
                writer.writerow([
                    img["file_name"],
                    img["displate_title"] or "",
                    img["displate_description"] or "",
                    img["displate_tags"] or "",
                    img.get("grade") or "NONE",
                    img["status"] or ""
                ])
        else:
            writer.writerow(["Filename", "Title", "Description", "Keywords", "Grade", "Status"])
            for img in images:
                writer.writerow([
                    img["file_name"],
                    img["title"] or "",
                    img["description"] or "",
                    img["keywords"] or "",
                    img.get("grade") or "NONE",
                    img["status"] or ""
                ])

    return str(out_path.resolve())
