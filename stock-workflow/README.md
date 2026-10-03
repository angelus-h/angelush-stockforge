# AI Stock Photography Metadata & CSV Workflow

This directory contains the automated stock photography preparation, downscaling, and metadata generation pipeline for **Adobe Stock**, **Shutterstock**, and related microstock platforms.

---

## 🚀 Workflow Steps

### Step 1: Thumbnail Generation (Token & Bandwidth Optimization)
Directly uploading and analyzing high-resolution RAW or 24–50+ megapixel images with multimodal LLMs consumes excessive bandwidth and tokens.
- The `create_thumbnails.py` script creates a `_temp/` subfolder inside the target directory.
- It generates web-optimized downscaled copies (max. 1024px width/height, high-quality Lanczos resampling) for each image.
- In parallel, it extracts embedded **EXIF**, **XMP**, and **GPS** coordinate telemetry into `metadata_extracted.json`.

### Step 2: AI Image Analysis and Classification (Commercial vs. Editorial)
The multimodal AI engine (or human curator) reviews the `_temp` preview images and classifies them according to strict microstock legal standards:
- **Commercial:**
  - No recognizable human faces or persons (unless covered by a signed Model Release).
  - No visible protected trademarks, logos, or brand marks.
  - Pure architecture, landscape, nature, botanical, or abstract imagery.
  - Title/Description: Clear, objective, factual description in English.
- **Editorial:**
  - Visible tourists, pedestrians, protected brand names, vehicle license plates, or copyrighted modern architecture/art.
  - **Mandatory Dateline Format:** `CITY, COUNTRY - MONTH DAY, YEAR: Factual description of event/scene.`  
    *Example:* `Szekesfehervar, Hungary - August 20, 2023: Tourists visit the fairytale Bory Castle surrounded by lush landscaped gardens.`

### Step 3: Keywords and Category Assignment
- **Keyword Count:** 25–45 highly relevant, searchable English terms per image.
- **Relevance Ordering:** Most specific primary keywords first (e.g. `bory castle`, `szekesfehervar`, `hungary`), followed by broader thematic terms (`architecture`, `travel`, `scenic`).
- **Agency Categories:**
  - Adobe Stock: Numeric ID (`2`: Buildings and Architecture, `21`: Travel, `11`: Nature, etc.).
  - Shutterstock: Official category names (`buildings/landmarks, travel`).

### Step 4: Generating Platform-Compliant CSVs
The `generate_stock_csv.py` script generates:
1. `adobe_stock.csv`: For batch upload to the Adobe Stock Contributor portal.
2. `shutterstock.csv`: For batch upload to the Shutterstock Contributor portal.
3. `<filename>_adobe.csv` and `<filename>_shutterstock.csv`: For specialized individual asset managers / metadata submitters (e.g., StockSubmitter, Xpiks).

---

## 📂 File Structure

```text
stock-workflow/
├── README.md                  # Workflow documentation
├── create_thumbnails.py       # Thumbnail downscaler and EXIF/GPS telemetry extractor
├── generate_stock_csv.py      # Adobe Stock and Shutterstock CSV exporter
├── process_vecteezy_batch.py  # Vecteezy automated batch pipeline
├── apply_alamy_metadata.py    # Alamy metadata embedding tool
└── test_data/
    └── bory_castle_example.json   # Reference sample dataset
```

---

## 🛠️ Usage Guide

### 1. Downscale Images and Extract Telemetry
Run the thumbnail extractor on your target image directory:
```bash
python create_thumbnails.py --input "G:\path\to\your\images" --max-size 1024
```
*This generates a `_temp/` folder with downscaled images and `metadata_extracted.json`.*

### 2. AI Multimodal Analysis
The AI reads the downscaled images from `_temp/` and generates structured JSON metadata according to agency specifications.

### 3. Generate CSV Files
Once the JSON dataset is ready, export the CSV files:
```bash
python generate_stock_csv.py --json "G:\path\to\your\images\image_data.json" --output "G:\path\to\your\images"
```

---

## 📋 Agency Platform Standards Summary

| Specification | Adobe Stock | Shutterstock |
| :--- | :--- | :--- |
| **Batch CSV Filename** | `adobe_stock.csv` | `shutterstock.csv` |
| **Header Columns** | `Filename,Title,Keywords,Category,Releases` | `Filename,Description,Keywords,Categories,Illustration,Mature content,Editorial` |
| **Editorial Flag** | Embedded in title or marked in contributor portal | `Editorial` column: `yes` / `no` |
| **Editorial Dateline** | Factual description or `City, Country - Date: ...` | `City, Country - Month Day, Year: ...` |
| **Keyword Count** | Max 49 (first 10 carry highest search weight) | Min. 7, Max. 50 |
| **Category Field** | Numeric category code (e.g. `2`, `21`) | Comma-separated category names (max 2) |
