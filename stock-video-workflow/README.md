# AngelusH's StockForge

A fully automated, AI-driven pipeline for extracting, analyzing, and generating commercial & editorial stock video metadata. 
StockForge processes raw video footage (e.g., MP4, MOV), extracts representative keyframes and embedded GPS/EXIF data, and leverages Google's **Gemini Flash** AI model orchestrated seamlessly via **OpenCode** to automatically generate highly optimized, platform-compliant metadata (Titles, Descriptions, Categories, and Keywords).

It exports ready-to-upload CSV files for the major stock agencies:
- **Adobe Stock**
- **Shutterstock**
- **Pond5**
- **Dreamstime**

## 🤖 AI Orchestration with OpenCode & Gemini Flash

StockForge is designed to be orchestrated directly through the **OpenCode** CLI agent:
- **OpenCode as the Pipeline Orchestrator:** Manages end-to-end execution, directory discovery across local and external SSD storage, fault tolerance, iterative prompt refinements, and batch processing quality control.
- **Google Gemini Flash (`gemini-flash-latest`):** Acts as the multimodal vision engine. It analyzes 5-frame contact sheets ("filmstrips") in conjunction with technical EXIF/GPS telemetry to deduce shot composition, lighting, camera motion, and editorial relevance through tailored prompt templates (`prompts/`).

## 📂 Repository Structure

```text
.
├── extract_video_keyframes.py  # Step 1: Extracts 5 keyframes & GPS data into a filmstrip
├── generate_ai_metadata.py     # Step 2: Analyzes filmstrips with AI & generates CSVs
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git ignore rules
├── prompts/                    # AI Prompt guidelines & rulesets for the AI model
│   ├── system_prompt_stock_video.md
│   ├── adobe-stock-prompt.txt
│   ├── shutterstock-prompt.txt
│   ├── dreamstime-prompt.txt
│   └── pond5-prompt.txt
├── templates/                  # Blank agency templates (e.g., XLS, CSV layouts)
└── legacy/                     # Old or specific hardcoded scripts (for reference)
```

## 🚀 Features

1. **Intelligent Keyframe Extraction:** Automatically extracts frames at 10%, 25%, 50%, 75%, and 90% of the video duration. Generates a composite "filmstrip" image.
2. **GPS & Date Parsing:** Reads ISO 6709 GPS coordinates embedded in MP4 headers and matches them to known geographical clusters (e.g., Budapest, Prague) for accurate location tagging.
3. **Editorial vs. Commercial Detection:** The AI automatically decides whether footage needs an Editorial license format (e.g., recognizable people, brands, transit like BKK/MAV) and formats descriptions as `City, Country - Month Day, Year: Description` (strictly NO ALL-CAPS, following official press guidelines).
4. **Official 5 Ws Compliance (Dreamstime & Shutterstock):** Editorial descriptions answer Who, What, Where, When, and Why (and How) with clean title-cased datelines.
5. **Time-lapse Detection:** Automatically detects time-lapses based on camera and subject movement.
6. **Caching & Rate Limiting:** Progress is saved automatically to `ai_metadata_cache.json`. If the script stops, it will resume exactly where it left off without burning extra AI API quotas.

## 🛠 Prerequisites

- **Python 3.8+**
- **FFmpeg & FFprobe**: Must be installed and accessible in your system's `PATH`.
  ```bash
  sudo apt install ffmpeg  # Linux (Debian/Ubuntu)
  brew install ffmpeg      # macOS
  ```
- **Gemini API Key**: You need a free or paid Google Gemini API key.

## 📦 Installation

1. Clone this repository.
2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Export your Gemini API Key as an environment variable:
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```

## ⚙️ Usage

The workflow is split into two straightforward steps.

### Step 1: Extract Keyframes and GPS Metadata
Run the extractor script and point it to the directory containing your raw videos.
```bash
python3 extract_video_keyframes.py -i /path/to/your/videos
```
*What this does:*
- Scans the directory for `.mp4`, `.mov`, `.mkv` files.
- Creates a `_temp_frames` folder inside the target directory.
- Generates a composite `*_filmstrip.jpg` for each video.
- Saves `video_metadata_summary.json` containing durations, FPS, and GPS location hints.

### Step 2: Generate AI Metadata & CSVs (with Auto-Renaming)
Run the AI generation script pointing to the *same* video directory.
```bash
python3 generate_ai_metadata.py -i /path/to/your/videos
```
*What this does:*
- Creates a `_metadata` folder inside the target directory.
- Reads the filmstrips and the GPS metadata.
- Calls the Gemini AI API to analyze the visuals.
- Caches results progressively into `ai_metadata_cache.json`.
- **Automatically renames** the raw video files on disk into descriptive, sanitized names.
- Outputs four strictly formatted CSV files ready for upload:
  - `adobe_stock_video.csv`
  - `shutterstock_video.csv`
  - `pond5_video.csv`
  - `dreamstime_video.csv`

## 📝 Platform Formatting Details

- **Adobe Stock:** Title (15-70 chars, plain text without punctuation) + 25-45 Keywords + Specific Numeric Category (e.g., 2=Buildings, 3=People, 21=Travel).
- **Shutterstock:** Strict formatting for Editorial (`City, Country - Month Day, Year: ...` without ALL-CAPS) + Max 2 Categories + 25-45 Keywords.
- **Pond5:** Strict Title length (40-80 characters, usually `[Subject] [Action] [Environment] [Shot type]`) + Keywords.
- **Dreamstime:** Video Name + Editorial 5 Ws Description (`City, Country - Month Day, Year: [Who] [What] [Where] [Why]`) + 3 separate Numeric Categories + Editorial Flags. (No ALL-CAPS; never uses category ID 2). 

## 🔄 Automatic File Renaming
The script automatically renames your original raw video files directly on disk to match stock agency best practices.
- **Naming Pattern:** `<city_or_location>_<theme_or_subject>_<shot_type>.<ext>` (e.g. `budapest_szechenyi_bridge_traffic_wide.mp4`).
- **Sanitization:** Converts to lowercase ASCII, replaces invalid characters, and preserves the original file extension (`.mp4`, `.mov`, etc.).
- **Collision Safe:** Checks if the target filename already exists before renaming to prevent accidental overwrites.
- **Consistency:** The generated CSV files (`adobe_stock_video.csv`, `shutterstock_video.csv`, etc.) will reference these exact new filenames, making the batch upload completely seamless.

---
**Disclaimer:** *Always review the AI-generated CSVs before uploading to ensure 100% compliance with agency guidelines. While the prompts are heavily optimized, AI can occasionally hallucinate specific landmarks.*
