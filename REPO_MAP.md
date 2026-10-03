# STOCKFORGE REPOSITORY MAP & ARCHITECTURE SPECIFICATION
> **Stateless Development Anchor for AI Engineering & Quick-Boot Navigation.**  
> *Everything needed to understand, extend, debug, and test the entire repository without recursively scanning directory trees.*

---

## 1. Executive Summary & Core Mission
- **Repository:** `angelush-stockforge` (`G:\repos\angelush-stockforge`)
- **Author / Artist:** Angelus H
- **Mission:** High-volume, publication-ready production, quality preflight, and multi-agency distribution pipeline for:
  1. **Fine Art Print-on-Demand (POD):** Art Heroes / Werk aan de Muur, Displate (Metal Posters), Fine Art America.
  2. **Microstock Photography & Illustration:** Adobe Stock (with **Posters.cz Hybrid Mode**), Vecteezy, Shutterstock, Alamy, Depositphotos.
  3. **Stock Footage / 4K Video:** Pond5, Adobe Stock Video, Shutterstock Video, Dreamstime.

---

## 2. Directory & Module Index

```text
G:\repos\angelush-stockforge\
├── REPO_MAP.md                     <-- YOU ARE HERE: Master architecture & dev spec
├── PROJECT_CONTEXT.md              <-- Compact agent anchor
├── dashboard/                      <-- Unified Streamlit management application
│   ├── app.py                      <-- Main UI, multi-platform editor, clipboard hub, batch runners
│   ├── db.py                       <-- SQLite engine (WAL mode), migrations, schema, export helpers
│   ├── llm_client.py               <-- Unified Gemini & Ollama caller, prompt templates, AI filters
│   ├── raw_loader.py               <-- Fast RAW/DNG thumbnail extraction & photographic RGB/Luma histograms
│   ├── credentials.py              <-- Agency profiles & Windows Credential Manager (keyring) secure storage
│   ├── ftp_uploader.py             <-- Direct multi-agency FTP/FTPS/SFTP upload engine
│   └── video_studio.py             <-- Stock Video Studio (keyframes, editorial audits, multi-agency video CSVs)
├── stock-workflow/                 <-- Stock photo batch tools & CSV generators
│   ├── generate_stock_csv.py       <-- Generates adobe_stock.csv, shutterstock.csv, vecteezy.csv
│   ├── process_vecteezy_batch.py   <-- Vecteezy automated ingestion & batch packaging
│   ├── apply_alamy_metadata.py     <-- Alamy IPTC/EXIF embedding tool
│   └── create_thumbnails.py        <-- Token-saving Lanczos thumbnail generator & telemetry extractor
├── stock-video-workflow/           <-- Stock footage analysis & CSV pipelines
│   ├── extract_video_keyframes.py  <-- High-precision video keyframe extractor
│   ├── audit_lednice_editorial.py  <-- Batch editorial reviewer & CSV writer
│   └── generate_ai_metadata.py     <-- Vision-based video captioning & tag generator
├── pod_workflow/                   <-- Fine Art Print-on-Demand modules
│   ├── ArtHeroes/                  <-- Art Heroes guides & apply_art_heroes_metadata.py (ExifTool engine)
│   ├── displate/                   <-- Displate tool (1.4:1 ratio, 300 DPI, safe zone, analog micrograin)
│   └── pod_metadata_generator.py   <-- Fine Art America JSON & CSV generator
└── stock-metadata/                 <-- Sensor dust, sharpness, and preflight analysis
    ├── dust_fingerprints.yaml      <-- Persistent camera sensor dust fingerprint database
    └── technical_quality_analyzer/ <-- Production & Paranoid QC suite (OpenCV, numpy, PIL)
        ├── analyzer.py             <-- Main QC runner
        ├── config.py               <-- Sensitivity thresholds
        └── detectors/              <-- Dust, sharpness, dead pixels, exposure analyzers
```

---

## 3. Database Architecture (`dashboard/db.py`)
- **Database Engine:** SQLite3 with WAL mode (`PRAGMA journal_mode = WAL;`, busy timeout 30s).
- **Default Database Path:** `G:\repos\angelush-stockforge\stockforge.db` (auto-created on first boot).
- **Core Table: `images`**
  ```sql
  CREATE TABLE IF NOT EXISTS images (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      file_path TEXT UNIQUE NOT NULL,
      file_name TEXT NOT NULL,
      directory TEXT NOT NULL,
      platform TEXT NOT NULL DEFAULT 'ArtHeroes',
      status TEXT NOT NULL DEFAULT 'NEW',             -- NEW, GENERATED, APPLIED, UPLOADED
      grade TEXT DEFAULT 'NONE',                      -- FINE_ART, STOCK, BOTH, NONE
      
      -- Art Heroes Fields
      title TEXT,                                     -- Emotional Mood + Subject + Room Suggestion
      description TEXT,                               -- Strictly 3 paragraphs
      keywords TEXT,                                  -- Comma-separated, strictly top 12 tags
      artist TEXT DEFAULT 'Angelus H',
      
      -- Displate Fields
      displate_title TEXT,                            -- Evocative metal poster title, < 60 chars
      displate_description TEXT,                      -- Punchy fine art copy, strictly 450-470 chars
      displate_tags TEXT,                             -- Up to 20 search tags
      
      -- Microstock & Adobe Stock Fields
      stock_title TEXT,                               -- Microstock title (or Adobe Hybrid title)
      stock_description TEXT,                         -- Factual stock caption (or Hybrid caption)
      stock_keywords TEXT,                            -- 25-35 stock tags (or 35-45 hybrid tags)
      stock_category TEXT,                            -- Category name (Travel, Architecture, etc.)
      
      -- Content Flags
      is_editorial INTEGER DEFAULT 0,                 -- 1 = Editorial, requires CITY, DATE dateline
      is_ai_generated INTEGER DEFAULT 0,              -- 1 = Generative AI, strictly NO camera keywords
      is_infrared INTEGER DEFAULT 0,                  -- 1 = 720nm IR, glowing white foliage, NOT snow
      is_surreal INTEGER DEFAULT 0,                   -- 1 = Dreamlike, surreal, conceptual style
      is_adobe_hybrid INTEGER DEFAULT 0,              -- 1 = Adobe Stock + Posters.cz Hybrid Mode
      custom_prompt TEXT,                             -- Per-image context / landmark hint
      
      -- Technical Quality & Agency Tracking
      qc_status TEXT DEFAULT 'UNCHECKED',             -- UNCHECKED, PASS, REVIEW, HIGH_RISK, ERROR
      qc_sharpness REAL,                              -- Laplacian sharpness variance score
      qc_dust_count INTEGER DEFAULT 0,                -- Detected dust candidates
      qc_warnings TEXT,                               -- Semicolon-separated QC warnings
      uploaded_to TEXT DEFAULT '',                    -- Comma-separated agencies already uploaded to
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```

---

## 4. Platform Specifications & Agency Requirements

### 🎨 Art Heroes / Werk aan de Muur
- **Title:** `[Emotional Mood] + [Core Subject] + [Explicit Room/Styling Suggestion]`.
- **Description:** Exactly 3 paragraphs:
  1. Atmospheric visual narrative, season, lighting.
  2. Specific room & styling recommendations (Scandinavian, Modern Rustic, Industrial, etc.).
  3. Material finishes (textured canvas, framed prints, sleek acrylic, metal) + attribution.
- **Keywords:** Strictly **12 high-relevance tags**.
- **Header Embedding:** Embedded via ExifTool into IPTC, XMP-dc, IFD0, with Camera Raw (`XMP-crs:all=`) and PhotoshopThumbnail stripped to keep header < 25 KB.

### 🏆 Displate (Metal Posters)
- **Title:** Evocative metal poster title, **strictly < 60 characters**.
- **Description:** Strictly **between 450 and 470 characters** (including spaces). High-contrast steel appeal.
- **Tags:** Up to **20 tags**.
- **Technical Preflight (`pod_workflow/displate/displate_tool.py`):**
  - **Aspect Ratio:** **1.4:1** (7:5) required. Native 3:2 can be auto-cropped by script.
  - **Resolution:** Short side **>= 2900 px** (Standard: 4060 × 2900 px). Max file size 30 MB.
  - **DPI:** Strictly **300 DPI**.
  - **Safe Zone:** Outer 200 px margin must not contain critical elements or text.
  - **Anti-Smoothing Grain:** AI upscaled images require 0.8–1.0% subtle optical micrograin to prevent bot rejection due to waxy smoothing. No artificial frames/borders.

### 📸 Microstock Standard (Vecteezy, Shutterstock, Alamy)
- **Vecteezy:** Strict **3 to 8 words title**. Banned subjective words (`beautiful, stunning, amazing, cool, best`). Max 30 tags. License: `pro`, `free`, or `editorial`.
- **Shutterstock:** Factual description, 7-50 keywords, two category strings, `editorial: yes/no`.
- **Alamy:** Factual caption + dateline format for editorial, 30-50 tags.

### 🖼️ Adobe Stock & Posters.cz HYBRID Approach (CRITICAL)
- **Background / Why Hybrid?**  
  Adobe Stock contributor assets are directly synced and licensed by European wall art print on demand webshops, primarily **https://www.posters.cz/** (Europosters network). On posters.cz, images are displayed in the customer storefront using the Adobe Stock Title, Description, and Keywords.
- **The Problem:** A dry, terse microstock title (e.g. `Retz calvary hill statues lower austria`) sells poorly on posters.cz as a poster product, and misses interior design search queries.
- **The Solution (Hybrid Formula):**
  1. **Stock Title (6–14 words, max 200 chars):**  
     `[Concrete Landmark / Subject + Geographic Location] - [Aesthetic Mood] [Interior Wall Art / Poster Decor]`  
     *Example:* `Historic Retz Calvary Hill Statues in Austria - Rustic Fine Art Wall Decor`  
     *Example:* `Keleti Railway Station Facade in Budapest - Architectural Wall Art Poster`
  2. **Stock Description (< 450 chars):**  
     Single cohesive paragraph identifying the real subject, location, and architecture, concluding with room and styling advice (e.g. `Ideal as an evocative wall art print or framed poster for contemporary living rooms, bedrooms, or modern office spaces.`).
  3. **Dual-Layer Keywords (35–45 tags):**
     - *Layer 1 (Microstock & Geography):* Specific city, region, country, landmark name, architecture terms, daylight, horizontal, no people.
     - *Layer 2 (Interior Design & Posters.cz):* `wall art, interior design, home decor, wall decor, poster, fine art print, canvas art, living room decor, bedroom wall art, modern interior, room styling, framed art, aesthetic decor, office wall art`.

---

## 5. AI Generation & LLM Engine (`dashboard/llm_client.py`)
- **Supported Engines:**
  1. **Google Gemini Flash (Cloud):** Fast, multimodal (~$0.002/image), requires `GEMINI_API_KEY`.
  2. **Local Ollama (100% Free / Private):** Two-stage pipeline:
     - Stage 1: Vision model (e.g. `llava:7b` or `moondream`) describes visual scene.
     - Stage 2: Copywriting model (e.g. `llama3.2:latest` or `qwen2.5`) generates structured JSON.
- **Prompt Router:** `get_prompt_for_target(target, description, user_context, is_editorial, is_ai_generated, is_infrared, is_surreal, is_adobe_hybrid)`
- **Auto-Detection (`is_hybrid_requested`):** Automatically detects keywords (`posters.cz`, `posters`, `hibrid`, `hybrid`, `lakberendez`, `belsőépít`, `interior design`, `wall decor`) in user or folder context.
- **AI-Generated Safeguards:** Automatically strips camera/lens words (`photography`, `camera`, `lens`, `dslr`, `photo`) and creator attributions when `is_ai_generated=1`.

---

## 6. Technical Quality Preflight (`stock-metadata/technical_quality_analyzer/`)
- **Analyzer:** `TechnicalQualityAnalyzer(QualityConfig(mode="production"|"paranoid"), db_path="dust_fingerprints.yaml")`
- **Detectors:**
  - `sharpness.py`: Laplacian variance with edge-density normalization.
  - `dust.py`: Sensor dust candidate detection; persistent vs single-image dust tracking using `dust_fingerprints.yaml`.
  - `dead_pixels.py`: Hot/stuck single-pixel sensor defects.
  - `exposure.py`: Shadow clipping (< 1%) and highlight blowout (< 1%) analysis.
- **Status Codes:** `PASS`, `REVIEW`, `HIGH_RISK`, `ERROR`.

---

## 7. Agency Ingestion & Secure Credential Hub (`dashboard/ftp_uploader.py`)
- **Supported Protocols:** SFTP (SSH Port 22), FTPS (TLS Port 21/990), Standard FTP (Port 21).
- **Environment:** `paramiko` and `keyring` installed in `dashboard\venv`.
- **High-Throughput Engine:** 256 KB transfer blocksize for fast delivery of high-bitrate 4K MP4/MOV footage and high-res photos.
- **SFTP Engine:** Powered by `paramiko.SSHClient` with `AutoAddPolicy` for seamless AWS SFTP handshake.
- **FTPS / FTP Engine:** Passive mode enabled (`set ftp:passive-mode true`), SSL certificate verification bypass (`ssl.CERT_NONE`, equivalent to `set ssl:verify-certificate no`).
- **Secret Management & Auto-Remembering:**
  - Dual persistent storage: Windows Credential Manager (`keyring`) + local `.env` fallback.
  - Automatic saving on text input change, connection test, or file upload (no manual "Save" click required).
  - Agency-wide shared state keys (`agency_shared_pass_{agency}`) so passwords remain loaded across image selections.
- **Target Profiles:**
  - **Adobe Stock:** `sftp.contributor.adobestock.com:22`, User: `208758992`, Dedicated SFTP password. Auto-generates `adobe_stock.csv` alongside files.
  - **Pond5:** `ftp://ftp.pond5.com:21`, User: `AngelusH`, Remote dir: `/` (photos & MP4 footage). Auto-generates `pond5.csv`.
  - **Vecteezy:** `content-ftp.eezy.com:22`, User: `miklosgreczi424081`, auto-includes `vecteezy.csv`.
  - **Dreamstime:** `upload.dreamstime.com:21`, User: `61235210`, Passive FTP, Remote dir: `video` (for video) / `/` (for photos). Auto-generates `dreamstime.csv`.
  - **Depositphotos:** `ftp.depositphotos.com:21`, User: `AngelusH`, Remote dir: `/`. Auto-generates `depositphotos.csv`.
  - **Alamy:** `upload.alamy.com:21`, User: `AngelusH`, Passive FTP. Ingests metadata directly from embedded JPEG IPTC/XMP.
  - **Shutterstock:** FTPS & Standard FTP profiles. Auto-generates `shutterstock.csv`.
- **Metadata Embedding & Delivery Engine (`dashboard/stock_metadata.py`):**
  - Direct ExifTool embedding for Stock & Alamy (`apply_stock_metadata_to_image`) with full 30-45 keywords, UTF-8 IPTC/XMP, and bloat stripping.
  - Automatic embedding before agency upload prevents stale headers.
  - Multi-agency automated CSV export engine (`generate_agency_csv`) generating platform-compliant CSV sidecars upon upload or batch export.
- **UI Feedback & Language Standards:**
  - Strict English language standard across all UI labels, toasts, status cards, and exception messages.
  - Multi-tiered feedback: `st.success`, `st.toast`, and persistent `st.session_state["last_up_{id}"]` cards.

---

## 8. Development, Verification & Test Commands

### Run Streamlit Management Dashboard
```powershell
streamlit run dashboard/app.py
```

### Run Stock Video Studio Standalone
```powershell
streamlit run dashboard/video_studio.py
```

### Execute Quality Analyzer Test Suite
```powershell
$env:PYTHONPATH="stock-metadata"; python -m unittest discover -s stock-metadata/technical_quality_analyzer/tests
```

### Run Local Unit Tests
```powershell
python -m unittest discover -s tests
```

### ExifTool Location
```text
C:\Users\miklo\AppData\Local\Programs\ExifTool\ExifTool.exe
```
