# StockForge Studio — Metadata & QC Control Panel

A unified visual workstation for fine art Print-on-Demand (POD) and stock photography creators. Integrates local & cloud LLMs (Ollama / Gemini Flash), an automated technical quality analyzer (sharpness, dust, exposure), remote FTP/FTPS delivery, and a one-click clipboard hub for fast web uploads.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r dashboard/requirements.txt
```

*(Ensure [ExifTool](https://exiftool.org/) is installed and accessible on your system PATH for metadata embedding).*

### 2. Launch the Workstation
```bash
cd dashboard
streamlit run app.py
```
Or from the project root:
```bash
streamlit run dashboard/app.py
```

---

## 🎯 Key Workflows & Features

### 1. 📁 Flexible Folder Scoping & Scanning
- Work on any directory on your system (e.g. `G:\upload_temp\Art-Heroes_temp`) with a quick-select list of recently used folders.
- Scope image list, batch generation, and exports strictly to the selected folder.
- Preserves existing sidecar `*_metadata.json` files automatically.

### 2. 🔬 Technical Quality Preflight (QC Engine)
- Integrated with `stock-metadata/technical_quality_analyzer`:
  - **Sharpness Evaluation:** Modified Laplacian variance with resolution-independent scoring.
  - **Sensor Dust & Blemish Detection:** Multi-scale spatial filtering with diagnostic mask overlay.
  - **Dead & Stuck Pixel Check:** Pinpoint sensor defects across RAW/JPEG files.
  - **Exposure & Dynamic Range:** Identifies severe underexposure and clipped highlights.
- **Batch QC Audit:** Run multi-image quality scans with a single click and review tabular results before committing to upload.
- Visual status indicators in catalog: `[🟢 PASS]`, `[🟡 REVIEW]`, `[🔴 HIGH_RISK]`.

### 3. 🧠 Hybrid LLM Metadata Engine (Ollama & Gemini)
- **Local Privacy:** Free, unlimited generation via local Ollama (`llama3.2` or any local vision/text model).
- **Cloud Speed:** Direct Google Gemini Flash integration with pre-compressed thumbnail previews for low latency and minimal cost (< $0.05 per 30 images).
- **Two-Tier Context System:**
  - *Folder Context:* Optional series-wide notes (e.g., location, technique, camera setup).
  - *Image-Specific Notes:* Per-image landmark, angle, or composition notes saved directly to the database.
  - *Clean Defaults:* Prompt fields start empty, giving you 100% control over what context is passed to the AI.

### 4. 🎨 Platform-Specific Formatting

#### A. Art Heroes (Werk aan de Muur)
- **Title Formula:** `[Emotional Mood] + [Subject] + [Room / Styling Suggestion]`.
- **Description:** Strictly 3 cohesive paragraphs (visual atmosphere, interior room styling, museum finishes + attribution).
- **Keywords:** Strictly **TOP 12** relevant search tags.
- **ExifTool Integration:** One-click batch embedding into EXIF, IPTC, and XMP headers while stripping bloat (`XMP-crs`, Photoshop previews) to keep files under web parser limits.

#### B. Displate (Metal Posters)
- **Title:** Evocative fine art metal poster title strictly under **60 characters**.
- **Description:** Strictly between **450 and 470 characters** (including spaces). High-impact copy optimized for metal finishes (matte/gloss) and modern wall decor.
- **Live Character Counter:** Instant visual feedback (`Target: 450-470 chars`) on length compliance.
- **Tags:** Up to 20 focused search tags.
- **CSV Export:** Ready for Displate catalog upload.

### 5. 📋 One-Click Clipboard Hub
- Zero-friction web browser uploading:
  - Copy individual fields (Title, Description, Tags) with a single click.
  - One-click **All-in-One** copy button (formatted with clear section headers).
  - Native browser clipboard integration (`navigator.clipboard.writeText`) with instant `✅ Copied!` visual confirmation.

### 6. 🚀 Remote FTP / FTPS Direct Uploader
- Integrated sidebar upload module:
  - Supports standard FTP and secure FTPS (FTP over TLS).
  - Connection tester and remote directory validator.
  - Selective batch uploads: push only images marked as `APPLIED` or entire folder with live progress tracking.

---

## 🗄️ Database Architecture
All session data, QC scores, custom prompts, and metadata revisions are maintained locally in `dashboard/stockforge.db` (SQLite):
- Schema includes: `qc_status`, `qc_sharpness`, `qc_dust_count`, `qc_warnings`, `custom_prompt`, `displate_title`, `displate_description`, `displate_tags`.
- Database files are automatically ignored by Git to prevent committing local file paths.
