# PROJECT CONTEXT & AGENT ANCHOR
> **Fast-boot context file for AI CLI agents (OpenCode / Claude Code).**  
> *Read this file first before searching or reading other directories.*

---

## 1. Project Overview & Mission
**Repository:** `angelush-stockforge` (`G:\repos\angelush-stockforge`)  
**Creator / Artist:** Angelus H  
**Purpose:** High-volume, high-quality automated workflow system for Stock Photography, Stock Video, and Print-on-Demand (POD) art sales.

---

## 2. Directory Architecture & Key Modules

| Module / Path | Purpose & Key Artifacts |
| :--- | :--- |
| `pod-workflow/` | **Print-on-Demand (POD) Pipelines**<br>• `ArtHeroes/`: Art Heroes / Werk aan de Muur guides, prompt, and `apply_art_heroes_metadata.py`<br>• `prompts/`: FAA master prompts (`FAA-prompt-v2-master.txt`)<br>• `pod_metadata_generator.py`: Generates FAA JSON/CSV datasets |
| `stock-workflow/` | **Microstock Photography**<br>• `create_thumbnails.py`, `generate_stock_csv.py`, `apply_alamy_metadata.py`, `process_vecteezy_batch.py` |
| `stock-video-workflow/` | **Stock Video Processing**<br>• Keyframe extraction, editorial classification, auto-renaming, CSV generators for Pond5, Adobe Stock, Shutterstock, Dreamstime |
| `stock-metadata/` | **Quality Analysis**<br>• `technical_quality_analyzer/`: Sensor dust, dead pixels, exposure, and sharpness detection |
| `dashboard/` | **Unified Streamlit Management UI & SQLite Engine**<br>• `app.py`: Streamlit control panel with directory scoping & integrated Technical QC<br>• `db.py`: SQLite catalog & status tracker (`stockforge.db`)<br>• `llm_client.py`: Direct, low-cost Gemini / Ollama caller (Art Heroes & Displate targets)<br>• `ftp_uploader.py`: Direct batch FTP/FTPS agency uploader |

---

## 3. Platform Metadata Standards & Hard Constraints

### A. Art Heroes / Werk aan de Muur (European POD)
- **Title:** `[Emotional Mood] + [Core Subject] + [Explicit Room/Styling Suggestion]` (No generic "Wall Art" suffixes).
- **Description:** Strictly 3 paragraphs (1. Atmospheric visual story; 2. Interior design & room styling; 3. Museum-grade materials & "Original fine art photography by Angelus H." attribution).
- **Keywords:** **Strictly TOP 12 keywords** (relevance priority).
- **Header Sanitization:** Strip Camera Raw (`XMP-crs:all=`) and Photoshop thumbnail (`PhotoshopThumbnail=`) to keep JPEG headers under 25 KB. UTF-8 encoded across EXIF, IPTC, and XMP.

### B. Displate (Metal Posters)
- **Title:** Catchy, evocative fine art metal poster title, **strictly under 60 characters**.
- **Description:** Strictly **around 450–470 characters** (including spaces). High-impact fine art copy highlighting luminous contrast on steel metal finish (matte/gloss) and modern wall decor appeal. Concludes with "Original fine art photography by Angelus H."
- **Tags:** **Up to 20 search tags** (1-2 words each, high-volume search terms).
- **Export:** Displate CSV export format.

### C. Fine Art America (FAA) / Pixels.com
- **Title:** SEO-optimized, interior-design friendly, subject + style.
- **Description:** 3-paragraph sales letter.
- **Keywords:** String length **must remain under 500 characters** total.

### C. Alamy & Microstock Agencies
- **Caption:** Concise, factual description (who, what, where, when). Editorial formatting when applicable.
- **Keywords:** 30–50 comma-separated tags, distinct essential vs secondary tags.

---

## 4. Operational Best Practices for AI Agents

1. **Zero-Crawl Policy:** Do NOT run broad recursive `glob` or `grep` scans across the whole workspace upon initialization. All necessary context is anchored here.
2. **Local Script Execution:** Never stream or process multi-file JSON datasets through LLM chat context. Generate or invoke a local Python script and return only exit status and error summaries.
3. **Paths:**
   - Workspace root: `G:\repos\angelush-stockforge`
   - Active staging: `G:\upload_temp\Art-Heroes_temp` (or designated external directories)
   - ExifTool: `C:\Users\miklo\AppData\Local\Programs\ExifTool\ExifTool.exe`
