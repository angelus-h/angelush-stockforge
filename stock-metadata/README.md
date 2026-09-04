# Technical Quality Analyzer (TQA)

A completely local, production-quality Python script designed for **Pre-Submission Technical Quality Preflight** of stock photographs.

## Core Philosophy: The "Paranoid" Screener
This tool is deliberately **paranoid**. Its primary objective is to minimize **false negatives** (missing a real technical defect). It is not designed to automatically reject images, but rather to flag anything suspicious for a human photographer to review before submitting to strict stock photography platforms. 

If the script flags an issue, you can quickly review it (using the `--diagnostic` flag) and fix the image in your editor (e.g., Lightroom, Capture One) while your metadata pipeline continues processing in parallel.

## Features & Detectors

1. **Sensor Dust Detection (Cross-Image Fingerprinting)**
   - Uses black-hat morphology to find soft-edged, dark, circular structures.
   - **Persistence Database:** Maintains a local YAML database (`dust_fingerprints.yaml`) to track normalized coordinates of suspected dust. If a spot appears in the same location across multiple images, its risk level is escalated.
2. **Sharpness & Focus**
   - Calculates global Laplacian variance to detect overall softness.
   - Divides the image into a 3x3 grid to detect *local anomalies* (e.g., one corner being significantly softer due to lens decentering or motion).
3. **Exposure & Clipping**
   - Analyzes the histogram for severe shadow and highlight clipping.
4. **Dead / Hot Pixels**
   - Looks for isolated pixels that are unnaturally bright (e.g., `>250` intensity) *and* exhibit extreme contrast against their immediate surrounding neighbors, preventing false positives on natural high-frequency textures like foliage or flowers.

## Pipeline Context
This tool fits into a modern AI-assisted photography workflow:
1. Export images from RAW editor.
2. **Run TQA (this script)** -> Outputs human-readable warnings and a machine-readable JSON.
3. *Concurrently*: Send images to a Vision LLM (like Gemini) to generate metadata/keywords.
4. Review the TQA report. If `HIGH_RISK` or `REVIEW` is flagged, inspect and retouch the image.
5. Final stock platform submission.

## Installation

Requires Python 3.9+.

```bash
# Clone/Navigate to the directory
cd /home/mgreczi/Documents/stock/stock-metadata

# Install dependencies (OpenCV, NumPy, Pillow, PyYAML)
pip install -r requirements.txt
```

## Usage

**1. Analyze a single image (Concise Human Report)**
Outputs a clean report highlighting ONLY the issues that need attention.
```bash
python -m technical_quality_analyzer "IMGP1431.JPG"
```

**2. Generate a Diagnostic Image**
Creates a copy of the image (e.g., `IMGP1431_diagnostic.jpg`) with bounding boxes drawn around detected defects. *The original image is never modified.*
```bash
python -m technical_quality_analyzer "IMGP1431.JPG" --diagnostic
```

**3. Batch Processing & JSON Output for Pipelines**
Processes a whole directory and dumps the structured results into a JSON file for downstream orchestration scripts.
```bash
python -m technical_quality_analyzer ./photos --batch --json report.json
```

**4. Resetting the Dust Database**
If the dust database learns too many false positives (e.g., from running on UI screenshots), simply delete the YAML file:
```bash
rm dust_fingerprints.yaml
```

## Configuration & Tuning
All thresholds are accessible in `technical_quality_analyzer/config.py`.

If you shoot highly textured scenes (like flowering fields, gravel, rough walls) and get false positives, you can tune:
- `dead_pixel_threshold`: Increase (e.g., to 250) to ignore natural bright specular highlights.
- `dust_sensitivity` / `dust_persistence_tolerance`: Adjust to define how aggressively the system tracks returning dust spots.
- `sharpness_global_threshold`: Adjust based on your camera's resolution and typical lens sharpness.

## Project Architecture
```text
technical_quality_analyzer/
├── __main__.py          # CLI entry point
├── analyzer.py          # Orchestrator
├── cli.py               # Argument parser & concise stdout formatting
├── config.py            # Centralized threshold settings
├── models.py            # Dataclasses and Enums
├── detectors/           # Modular detection logic
│   ├── base.py
│   ├── dust.py
│   ├── exposure.py
│   ├── sharpness.py
│   └── dead_pixels.py
├── fingerprint/
│   └── dust_database.py # YAML-based persistent dust tracking
└── reporting/
    └── diagnostic.py    # OpenCV visualization
```
