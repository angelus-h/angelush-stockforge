# Fine Art America (FAA) & Print-on-Demand (POD) Metadata Workflow

This pipeline generates search-optimized titles, persuasive 3-paragraph sales storytelling descriptions, and tag sets specifically engineered for **Fine Art America (FAA)** and **Pixels.com** fine art marketplaces.

---

## 🎯 Workflow Objectives and Rules (Based on `FAA-prompt.txt`)

### 1. Thumbnail Creation (Token & Bandwidth Efficiency)
Rather than passing heavy 24–50+ megapixel master files directly into multimodal vision models, the system creates a lightweight `_temp/` directory containing downscaled preview copies (max. 1024px width/height).

### 2. Geolocation and Context Telemetry
Using embedded GPS coordinates, EXIF capture data, and regional cluster matching, the workflow automatically resolves geographic and cultural landmarks (e.g., **Hardegg Castle / Burg Hardegg, Thayatal National Park, Lower Austria / Čížov Iron Curtain Memorial**).

### 3. SEO Title Formulation (`optimized_title`)
- **Prohibited:** Raw filenames, sequence numbers (`#1`, `v2`), camera model names, or overly abstract artistic titles.
- **Required:** Highly searchable, interior-design friendly, evocative fine art titles clearly communicating subject and aesthetic mood.  
  *Examples:* `Medieval Hardegg Castle Rising Above Green Forest - Austrian Fortress Wall Art` or `Infrared Fairytale Hardegg Town and Castle - Dreamy Austrian Landscape Fine Art Print`.

### 4. Three-Paragraph Sales Description (`sales_description`)
- **Paragraph 1 (Atmosphere & Visual Storytelling):** Describes the visual composition, lighting quality (e.g. ethereal infrared luminescence, golden sunlight), and emotional resonance (tranquil, grounding, serene).
- **Paragraph 2 (Interior Styling & Room Placement):** Specific room suggestions (Living Room, Master Bedroom, Calming Executive Office, Hotel Suite, Healthcare/Hospital Waiting Room - healing art), highlighting complementary decor palettes and interior aesthetics.
- **Paragraph 3 (Museum-Grade Quality & Assurance):** Available substrate finishes (stretched textured canvas, custom framed prints, sleek modern acrylic, luminous metal prints), 30-day money-back guarantee, concluding with signature attribution to landscape photographer Angelus H.

### 5. Tag Optimization (`comma_separated_tags`)
- **Strict Limit:** Total tag string length **must remain strictly under 500 characters** (including commas).
- Strategic taxonomy: High-volume core terms (`wall art`, `landscape print`), technique (`infrared photography`, `fine art print`), literal subjects (`castle`, `forest`, `river`), color tones (`emerald green`, `silver white`), mood (`calming art`, `healing art`, `serene`), room contexts (`living room decor`, `office wall art`), and accurate geography (`hardegg`, `austria`, `thayatal`).

---

## 📂 File Structure

```text
pod_workflow/
├── README.md                     # Workflow documentation
├── POD_SALES_STRATEGY_GUIDE.md   # Market positioning & sales strategy
├── pod_metadata_generator.py     # Automated FAA JSON and CSV generator
├── gemini_metadata_generator.py  # Direct Gemini multimodal generator
├── prompts/                      # Specialized POD system prompts
│   ├── FAA-prompt.txt
│   └── FAA-prompt-v2-master.txt
├── ArtHeroes/                    # Art Heroes / Werk aan de Muur tools
│   ├── apply_art_heroes_metadata.py
│   └── ART_HEROES_WORKFLOW_GUIDE.md
└── displate/                     # Displate metal poster tools & guides
    ├── displate_tool.py
    ├── DISPLATE_TECHNICAL_GUIDE.md
    └── displate_prompt_guide.md
```

---

## 🛠️ Usage Guide

### 1. Generate Previews and Extract Telemetry
```bash
python ../stock-workflow/create_thumbnails.py --input "G:\path\to\images" --max-size 1024
```

### 2. Generate FAA Metadata and Export CSV
```bash
python pod_metadata_generator.py --json "G:\path\to\images\metadata_extracted.json" --output "G:\path\to\images"
```
