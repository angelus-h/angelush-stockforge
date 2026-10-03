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
| `pod_workflow/` | **Print-on-Demand (POD) Pipelines**<br>• `ArtHeroes/`: Art Heroes / Werk aan de Muur guides, prompt, and `apply_art_heroes_metadata.py`<br>• `prompts/`: FAA master prompts (`FAA-prompt-v2-master.txt`)<br>• `pod_metadata_generator.py`: Generates FAA JSON/CSV datasets |
| `stock-workflow/` | **Microstock Photography**<br>• `create_thumbnails.py`, `generate_stock_csv.py`, `apply_alamy_metadata.py`, `process_vecteezy_batch.py` |
| `stock-video-workflow/` | **Stock Video Processing**<br>• Keyframe extraction, editorial classification, auto-renaming, CSV generators for Pond5, Adobe Stock, Shutterstock, Dreamstime |
| `stock-metadata/` | **Quality Analysis**<br>• `technical_quality_analyzer/`: Sensor dust, dead pixels, exposure, and sharpness detection |
| `dashboard/` | **Unified Streamlit Management UI & SQLite Engine**<br>• `app.py`: Streamlit control panel with directory scoping, histogram & integrated Technical QC<br>• `db.py`: SQLite catalog, dual grade & multi-agency upload tracker (`stockforge.db`)<br>• `raw_loader.py`: High-performance RAW/DNG preview extractor & photographic histogram engine<br>• `credentials.py`: Windows Credential Manager (`keyring`) secure secret storage<br>• `llm_client.py`: Direct, low-cost Gemini / Ollama caller (Art Heroes, Displate & Microstock targets)<br>• `ftp_uploader.py`: Direct batch SFTP/FTPS/FTP agency uploader |

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
- **Technical Image Specs & Real-World Approval Criteria:**
  - **Aspect Ratio:** Official standard: **1.4:1** (or 7:5). In practice, native camera **3:2 (1.5:1)** is accepted automatically with minor outer-edge crop.
  - **Resolution:** Shortest side **min. 2900 px** (Standard: **4060 × 2900 px** or larger, e.g. 6090 × 4350 px).
  - **DPI:** Strictly **300 DPI** embedded in header.
  - **Critical Rejection Triggers:** 
    - **Borders / Frames STRICTLY PROHIBITED:** The metal plate itself serves as the frame; artificial borders lead to immediate rejection.
    - **Safe Zone (<200 px):** No text, logos, or critical details touching the outer edge.
    - **AI Waxy Smoothing vs. Authentic Micro-Detail:** Genuine photography passes review easily due to natural optical micro-detail and sensor grain. For AI art, add subtle analog film grain (0.8-1%) to counteract AI upscaler smoothing.
  - **Color Profile & Size:** Embedded **sRGB** or **AdobeRGB**, max file size **30 MB** (JPG/PNG).
- **Tooling:** `pod_workflow/displate/displate_tool.py` (verification, Safe Zone check, 1.4:1 auto-crop & 300 DPI injection, integrated into `dashboard/app.py`).
- **Documentation:** `pod_workflow/displate/DISPLATE_TECHNICAL_GUIDE.md` & `pod_workflow/displate/displate_prompt_guide.md`.
- **Export:** Displate CSV export format.

### C. Fine Art America (FAA) / Pixels.com
- **Title:** SEO-optimized, interior-design friendly, subject + style.
- **Description:** 3-paragraph sales letter.
- **Keywords:** String length **must remain under 500 characters** total.

### D. Alamy & Microstock Agencies
- **Caption:** Concise, factual description (who, what, where, when). Editorial formatting when applicable.
- **Keywords:** 30–50 comma-separated tags, distinct essential vs secondary tags.

### E. Depositphotos
- **FTP Ingestion:** `ftp.depositphotos.com:21` (credentials stored under `DEPOSITPHOTOS_PASSWORD`).
- **Image Specs:** Min 3.8 MP (2400 × 1600), RGB, max 50 MB. Strictly NO AI-generated submissions. Auto-imports embedded IPTC/XMP.
- **Video Specs:** MOV/MP4 (H.264/ProRes), duration strictly 3–60 seconds, broadcast FPS (24/25/30/50/60), max 4096 MB.
- **Editorial Syntax:** `CITY, COUNTRY – MONTH DAY, YEAR: [Factual sentence answering Who, Where, What]`.
- **Documentation:** `DEPOSITPHOTOS_CONTRIBUTOR_GUIDE.md`.

---

## 4. Operational Best Practices for AI Agents

1. **Zero-Crawl Policy:** Do NOT run broad recursive `glob` or `grep` scans across the whole workspace upon initialization. All necessary context is anchored here.
2. **Local Script Execution:** Never stream or process multi-file JSON datasets through LLM chat context. Generate or invoke a local Python script and return only exit status and error summaries.
3. **Paths:**
   - Workspace root: `G:\repos\angelush-stockforge`
   - Active staging: `G:\upload_temp\Art-Heroes_temp` (or designated external directories)
   - ExifTool: `C:\Users\miklo\AppData\Local\Programs\ExifTool\ExifTool.exe`
