# Stock & POD Automation Monorepo

Welcome to the central repository for automated Stock Photography, Stock Video, and Print-on-Demand (POD) workflows. This repository contains various specialized tools designed to leverage AI (like Google's Gemini) and automated scripts to process raw media, generate commercial metadata, and prepare files for upload to microstock agencies and POD platforms.

## 📂 Repository Structure

The repository is organized into discrete workflow sub-projects:

### 1. `stock-video-workflow/`
The most advanced workflow for **Stock Video Footage**. 
- Extracts representative keyframes (10%, 25%, 50%, 75%, 90%) from MP4/MOV files.
- Reads embedded GPS metadata.
- Uses AI to classify content as Editorial vs. Commercial (e.g., detecting recognizable faces or brands).
- **Auto-renames raw video files** directly on disk to clean, descriptive names (`<location>_<subject>_<shot>.<ext>`).
- Generates platform-specific metadata CSVs for **Adobe Stock, Shutterstock, Pond5, and Dreamstime**.
- *[Read the detailed documentation inside the folder]*

### 2. `stock-workflow/`
Workflow dedicated to **Stock Photography**.
- Includes scripts for thumbnail generation (`create_thumbnails.py`).
- Generates required CSV and XLS metadata sheets (using provided templates) for major photography agencies.

### 3. `pod-workflow/`
Workflow tailored for **Print-on-Demand (POD)** platforms like Fine Art America (FAA).
- Contains highly specialized AI prompts to generate artistic, emotive, and SEO-friendly titles and descriptions.
- `gemini_metadata_generator.py` processes raw image datasets into rich JSON and CSV metadata formatted for POD.
- Includes a comprehensive sales strategy guide (`POD_SALES_STRATEGY_GUIDE.md`).

### 4. `stock-metadata/`
A smaller, core utility module for basic image analysis.
- `analyze_images.py`: A lightweight script for analyzing local image datasets before metadata generation.

## ⚙️ Quick Start

**Prerequisites:**
- Python 3.8+
- `ffmpeg` (Required for video processing)
- `google-generativeai`, `Pillow`, `opencv-python` (See individual `requirements.txt` files)

**Environment Setup:**
Most AI scripts require a Google Gemini API key. Export it in your shell:
```bash
export GEMINI_API_KEY="your_api_key_here"
```

## 🛡️ Git & Ignored Files
This repository uses a global `.gitignore` to prevent huge media files (`.mp4`, `.mov`, `.jpg`) and temporary processing directories (`_temp_frames`, `results`) from being uploaded to GitHub. You can safely run the scripts inside these folders; generated media and raw outputs will stay local to your machine.

---
*Maintained for automated, high-volume stock portfolio generation.*
