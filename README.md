# Angelus H. StockForge Monorepo

A specialized, high-performance monorepo for automated **Stock Photography, Stock Video, and Print-on-Demand (POD)** production. Designed for fine art landscape photographers, stock contributors, and digital creators to streamline technical quality control, metadata generation, and multi-platform distribution.

---

## 📂 Repository Architecture

```text
angelush-stockforge/
├── dashboard/                  # StockForge Studio — Streamlit UI, local/cloud AI, QC, FTP & Clipboard Hub
├── pod_workflow/               # Print-on-Demand pipelines (Art Heroes, Displate, Fine Art America)
│   └── ArtHeroes/              # Art Heroes ExifTool embedding scripts and official guidelines
├── stock-metadata/             # Technical Quality Analyzer (OpenCV dust, sharpness, exposure, dead pixels)
├── stock-workflow/             # Microstock photo processing & metadata spreadsheet generators
├── stock-video-workflow/       # Stock video keyframe extraction, editorial audit & multi-agency CSVs
└── PROJECT_CONTEXT.md          # Global AI agent context and platform requirements
```

---

## 🌟 Primary Workflows & Modules

### 1. 🎛️ `dashboard/` — StockForge Studio
Visual workstation built on Streamlit for end-to-end processing:
- **RAW & DNG Format Support:** Blazing fast embedded preview generation for camera RAWs (`.dng`, `.orf`, `.cr2`, `.cr3`, `.nef`, `.arw`, `.pef`, `.raf`, `.rw2`) alongside `.jpg`, `.png`, `.tif`, and `.webp`.
- **Rapid Photo Triage & Culling:** Instant 1-click delete button (`🗑️`) next to every thumbnail in the gallery list. Automatically purges raw files, XMP sidecars, and JSON metadata from disk and SQLite catalog before editing.
- **Photographic RGB & Luminance Histogram:** Real-time dark-themed Lightroom/Capture One-style RGB and Luma curve display with automatic Shadow Clipping (%), Highlight Blowout (%), Mean Brightness, and Contrast metrics.
- **Multi-Agency Upload Tracker:** Manual and automatic submission tracking across 9 major agencies (`Adobe Stock`, `Vecteezy`, `Shutterstock`, `Alamy`, `Art Heroes`, `Displate`, `Pond5`, `Dreamstime`, `Fine Art America`) with visual card badges and dedicated sidebar filter.
- **Dual AI Engine:** Use local Ollama (`llama3.2`) for 100% private, free processing or Google Gemini Flash for cloud speed.
- **Technical Quality Analyzer & Visual Map:** Live image quality inspection (sharpness scoring, sky-aware sensor dust detection, dead pixel count, Unicode-safe visual defect overlay).
- **Two-Tier Context System & Medium Directives:** Series-level folder context, per-frame notes, and dedicated toggles for **Editorial**, **Generative AI**, **🔴 Infrared (720nm / Wood Effect)**, and **🌌 Surreal / Conceptual** styling.
- **Classification Grades:** One-click assignment of `🎨 Fine Art`, `📸 Stock`, `🎨📸 Dual Grade (Both)`, or `⚪ Unassigned`.
- **Platform Modules:**
  - **Art Heroes:** Mood + Subject + Room formula, 3-paragraph sales letters, strictly TOP 12 keywords, one-click ExifTool embedding.
  - **Displate:** Catchy titles (< 60 chars), strictly 450–470 character descriptions with live length counter, up to 20 search tags, CSV export.
  - **Microstock:** Short titles (3–8 words), factual descriptions with editorial city/date compliance, 20–35 comma-separated keywords, category selector.
- **Full-Screen Inspection & Native Viewer:** 2048px+ crisp preview with full-screen expansion and a dedicated `🖥️ Open Full Size` button launching the default Windows viewer (Photos, IrfanView) for 1:1 pixel inspection.
- **Secure Agency Upload (SFTP / FTPS / FTP):** Direct batch or single-image transmission with agency presets. Secrets and passwords stored safely in Windows Credential Manager (`keyring`).
- **One-Click Clipboard Hub:** Native browser clipboard buttons for instant web form pasting.

### 2. 🎨 `pod_workflow/` — Print-on-Demand Pipelines
- **Art Heroes / Werk aan de Muur:** Complete ExifTool batch injection scripts (`apply_art_heroes_metadata.py`) ensuring clean UTF-8 headers across EXIF, IPTC, and XMP while stripping raw camera bloat (`XMP-crs`).
- **Fine Art America (FAA) / Pixels.com:** Emotive 3-paragraph copy generation with strict < 500 character keyword bounds.
- **Displate:** Metal poster copy targeting modern interior and industrial decor collectors.

### 3. 🔬 `stock-metadata/` — Technical Quality Analyzer
Automated computer-vision quality gate for high-resolution photography:
- Detects dust candidates, sensor spots, and dead/hot pixels across uniform areas (e.g. skies).
- Modified Laplacian variance metric for resolution-independent focus analysis.
- Generates diagnostic mask images for rapid visual review before submission.

### 4. 📸 `stock-workflow/` — Photography Automation
- Multi-agency metadata generation (Alamy, Vecteezy, etc.).
- Batch thumbnail generation and Excel/CSV catalog creation.

### 5. 🎬 `stock-video-workflow/` — Stock Video Footage
- Automated video frame extraction (10%, 25%, 50%, 75%, 90% keyframes) via FFmpeg.
- Embedded GPS reading and automated file renaming (`<location>_<subject>_<shot>.<ext>`).
- Editorial vs. Commercial classification.
- CSV export for Adobe Stock, Shutterstock, Pond5, and Dreamstime.

---

## ⚙️ Prerequisites & Setup

### Environment Setup
- **Python 3.10+** (Python 3.11 / 3.12 / 3.14 tested)
- **External Tools:**
  - [ExifTool](https://exiftool.org/) (required for JPEG/TIFF metadata embedding)
  - [FFmpeg](https://ffmpeg.org/) (required for video workflows)
  - [Ollama](https://ollama.ai/) (optional, for local LLM inference)

### Installation
```bash
# Clone the repository
git clone https://github.com/your-username/angelush-stockforge.git
cd angelush-stockforge

# Install dashboard requirements
pip install -r dashboard/requirements.txt
```

### Quick Run
Launch the unified dashboard:
```bash
streamlit run dashboard/app.py
```

---

## 🛡️ Git & Safe Development
All heavy media files (`.jpg`, `.raw`, `.mp4`, etc.), temporary processing folders (`_temp_frames`, `results`), and local SQLite database files (`*.db`) are excluded via `.gitignore`. Your local working catalogs and credentials remain safe on your local workstation.
