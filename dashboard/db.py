"""
SQLite database layer for Angelush StockForge Dashboard.
Manages media items, platform targets, metadata records, and lifecycle statuses.
"""

import sqlite3
import json
import csv
from pathlib import Path
from datetime import datetime

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "stockforge.db"


def get_connection(db_path=None):
    """Return a SQLite connection with row factory enabled."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    """Initialize database tables and indexes."""
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Ensure migration columns exist for existing databases
        for col in [
            "displate_title TEXT", "displate_description TEXT", "displate_tags TEXT",
            "qc_status TEXT DEFAULT 'UNCHECKED'", "qc_sharpness REAL",
            "qc_dust_count INTEGER DEFAULT 0", "qc_warnings TEXT",
            "custom_prompt TEXT"
        ]:
            try:
                cursor.execute(f"ALTER TABLE images ADD COLUMN {col};")
            except sqlite3.OperationalError:
                pass  # column already exists
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_platform ON images(platform);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_status ON images(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_file_name ON images(file_name);")
        conn.commit()


def scan_and_sync_folder(folder_path, platform="ArtHeroes", db_path=None):
    """
    Scan a directory for JPEG images, automatically importing existing
    sidecar *_metadata.json files if present.
    """
    init_db(db_path)
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    image_extensions = {".jpg", ".jpeg"}
    image_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in image_extensions]

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
                            keywords_str = str(kws)
                        initial_status = "GENERATED"
                except Exception as e:
                    print(f"Warning reading {json_file.name}: {e}")

            # Check if record already exists
            cursor.execute("SELECT id, status FROM images WHERE file_path = ?", (file_path,))
            row = cursor.fetchone()

            if row is None:
                cursor.execute("""
                    INSERT INTO images (file_path, file_name, directory, platform, status, title, description, keywords, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (file_path, file_name, directory, platform, initial_status, title, description, keywords_str, datetime.now()))
                imported_count += 1
            else:
                # Update existing if new sidecar metadata is available and record has no title
                if title:
                    cursor.execute("""
                        UPDATE images 
                        SET title = COALESCE(title, ?),
                            description = COALESCE(description, ?),
                            keywords = COALESCE(keywords, ?),
                            platform = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (title, description, keywords_str, platform, datetime.now(), row["id"]))
                    updated_count += 1

        conn.commit()

    return {"scanned": len(image_files), "imported": imported_count, "updated": updated_count}


def get_images(platform=None, status=None, search_query=None, folder_path=None, qc_status=None, db_path=None):
    """Retrieve filtered images."""
    init_db(db_path)
    query = "SELECT * FROM images WHERE 1=1"
    params = []

    if folder_path:
        norm_folder = str(Path(folder_path).resolve())
        query += " AND (file_path LIKE ? OR file_path LIKE ? OR file_path LIKE ?)"
        params.extend([f"{norm_folder}\\%", f"{norm_folder}/%", f"{norm_folder}%"])

    if platform and platform != "ALL":
        query += " AND platform = ?"
        params.append(platform)

    if status and status != "ALL":
        query += " AND status = ?"
        params.append(status)

    if qc_status and qc_status != "ALL":
        query += " AND qc_status = ?"
        params.append(qc_status)

    if search_query:
        query += " AND (file_name LIKE ? OR title LIKE ? OR keywords LIKE ?)"
        like_str = f"%{search_query}%"
        params.extend([like_str, like_str, like_str])

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
                 qc_dust_count=None, qc_warnings=None, custom_prompt=None, db_path=None):
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
    if status is not None:
        fields.append("status = ?")
        params.append(status)
    if platform is not None:
        fields.append("platform = ?")
        params.append(platform)
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

    if not fields:
        return

    fields.append("updated_at = ?")
    params.append(datetime.now())
    params.append(image_id)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE images SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()


def export_catalog_csv(output_csv_path, platform="ArtHeroes", db_path=None):
    """Export current images matching platform to a master CSV catalog."""
    images = get_images(platform="ALL", db_path=db_path)
    out_path = Path(output_csv_path)

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if platform == "Displate":
            writer.writerow(["Filename", "Title", "Description", "Tags", "Status"])
            for img in images:
                writer.writerow([
                    img["file_name"],
                    img["displate_title"] or "",
                    img["displate_description"] or "",
                    img["displate_tags"] or "",
                    img["status"] or ""
                ])
        else:
            writer.writerow(["Filename", "Title", "Description", "Keywords", "Status"])
            for img in images:
                writer.writerow([
                    img["file_name"],
                    img["title"] or "",
                    img["description"] or "",
                    img["keywords"] or "",
                    img["status"] or ""
                ])

    return str(out_path.resolve())
