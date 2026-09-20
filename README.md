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
- **Dual AI Engine:** Use local Ollama (`llama3.2`) for 100% private, free processing or Google Gemini Flash for cloud speed.
- **Technical Quality Analyzer:** Live image quality inspection (sharpness scoring, sensor dust detection, dead pixel count, visual defect overlay).
- **Two-Tier Context System:** Series-level folder context and per-frame landmark notes with clean prompt defaults (no forced pre-filled text).
- **Platform Modules:**
  - **Art Heroes:** Mood + Subject + Room formula, 3-paragraph sales letters, strictly TOP 12 keywords, one-click ExifTool embedding.
  - **Displate:** Catchy titles (< 60 chars), strictly 450–470 character descriptions with live length counter, up to 20 search tags, CSV export.
- **One-Click Clipboard Hub:** Native browser clipboard buttons for instant web form pasting.
- **Remote FTP / FTPS Uploader:** Direct batch transmission to remote agency storage with progress tracking.

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
