# Art Heroes / Werk aan de Muur — Metadata & Upload Workflow Guide

This guide establishes the official technical specifications, metadata standards, and practical upload workflows for the **Art Heroes (Werk aan de Muur)** European Print-on-Demand (POD) marketplace.

---

## 1. Platform Overview & Official Guidelines

Art Heroes / Werk aan de Muur operates across the Netherlands, Germany, France, and other European markets. Based on official **Beeldmaker (Creator)** guidelines:

* **Automated Metadata Extraction:**  
  * *"Titels, omschrijving en tags worden direct uit jouw EXIF gehaald en alvast ingevuld!"*  
  *(The upload interface attempts to read the title, description, and keywords directly from embedded file metadata).*
* **Title Standards:**  
  * Must be descriptive, emotional, and interior-design oriented without being excessively long.
  * Formula: `[Emotional Mood] + [Core Subject] + [Explicit Room/Styling Suggestion]`.
  * Avoid robotic suffixes like `Wall Art`, `Canvas Print`, or raw file numbers at the end.
* **3-Paragraph Fine Art Sales Description:**  
  1. **Visual & Emotional Scene:** Describe the landscape, light, textures, season, and atmospheric mood.
  2. **Interior Design & Placement:** Explicit room recommendations (living room, bedroom, executive office, modern kitchen, healthcare clinic) and styling advice (Scandinavian, rustic farmhouse, minimalist).
  3. **Museum-Grade Quality & Guarantee:** Premium archival finishes (textured canvas, framed gallery prints, sleek acrylic, modern metal), archival pigment longevity, and artist attribution (`Original fine art photography by Angelus H.`).
* **Keywords / Tags:**  
  * **Strictly TOP 12 keywords.** The Art Heroes search algorithm prioritizes relevance; adding more than 12 tags dilutes ranking.
* **Image Specifications:**  
  * Format: High-quality JPEG (Quality 100) or TIFF (ZIP compressed).
  * Color Space: **Adobe RGB (1998)** (recommended for POD wide-gamut printers) or **sRGB**.
  * Resolution: At least 12 Megapixels.

---

## 2. Technical Metadata Field Mapping

Because web uploaders utilize heterogeneous parsers (PHP `exif_read_data`, IPTC IIM readers, browser JavaScript EXIF libraries), metadata must be synchronized across EXIF, IPTC, and XMP:

| Field | EXIF (IFD0 / ExifIFD) | IPTC (IIM) | XMP (Dublin Core) | Requirements |
| :--- | :--- | :--- | :--- | :--- |
| **Title** | `XPTitle` | `ObjectName` *(max 64 chars)* & `Headline` | `dc:title` *(x-default)* | Concise, interior-focused |
| **Description** | `ImageDescription`, `XPComment`, `UserComment` | `Caption-Abstract` | `dc:description` *(x-default)* | Complete 3-paragraph sales letter, clean UTF-8 |
| **Keywords** | `XPKeywords` *(semicolon-separated)* | `Keywords` *(array)* | `dc:subject` *(array)* | Strictly TOP 12 targeted tags |
| **Artist / Creator**| `Artist` | `By-line` | `dc:creator` | `Angelus H` |
| **Copyright** | `Copyright` | `CopyrightNotice` | `dc:rights` | `Angelus H` |

---

## 3. Header Optimization & Parser Stability

Web upload engines often struggle with raw camera exports. Follow these rules to ensure smooth processing:

1. **Purge Bloat (Camera Raw & Photoshop Thumbnails):**  
   Lightroom/Photoshop exports often bundle 30–60 KB of raw edit steps (`XMP-crs`) and an 18 KB embedded preview (`PhotoshopThumbnail`). These inflate the JPEG header beyond standard browser memory buffers. Always strip them (`-PhotoshopThumbnail= -XMP-crs:all=`).
2. **Strict UTF-8 Encoding:**  
   Always specify IPTC UTF-8 encoding explicitly:  
   `-charset iptc=UTF8 -IPTC:CodedCharacterSet=UTF8`
3. **Synchronize IPTCDigest:**  
   Update the Photoshop IPTCDigest hash (`-photoshop:IPTCDigest=new`) after modifying IPTC/XMP to prevent server-side synchronization errors.
4. **Web Parser Fallback Strategy:**  
   The web uploader's browser JavaScript parser can occasionally drop the description field due to multi-line formatting or language tab defaults (e.g., defaulting to Dutch rather than English).  
   **Best practice:** Always maintain sidecar `.json` files and an `art_heroes_catalog.csv` master spreadsheet for instant copy-pasting whenever the web frontend fails to auto-populate.

---

## 4. Standard ExifTool Command

```bash
exiftool -m -overwrite_original \
  -charset utf8 \
  -charset iptc=utf8 \
  -charset exif=utf8 \
  -IPTC:CodedCharacterSet=UTF8 \
  -IPTC:ObjectName="Short Title (max 64 chars)" \
  -IPTC:Headline="Full Emotional Title" \
  -IPTC:Caption-Abstract="Complete 3-paragraph fine art sales description" \
  -XMP-dc:Title="Full Emotional Title" \
  -XMP-dc:Description="Complete 3-paragraph fine art sales description" \
  -IFD0:ImageDescription="Complete 3-paragraph fine art sales description" \
  -IFD0:XPTitle="Full Emotional Title" \
  -IFD0:XPComment="Complete 3-paragraph fine art sales description" \
  -ExifIFD:UserComment="Complete 3-paragraph fine art sales description" \
  -Artist="Angelus H" \
  -By-line="Angelus H" \
  -CopyrightNotice="Angelus H" \
  -PhotoshopThumbnail= \
  -XMP-crs:all= \
  -photoshop:IPTCDigest=new \
  -IPTC:Keywords="tag 1" -IPTC:Keywords="tag 2" ... \
  -XMP-dc:Subject="tag 1" -XMP-dc:Subject="tag 2" ... \
  -IFD0:XPKeywords="tag 1;tag 2;tag 3" \
  "target_image.jpg"
```

---

## 5. Directory Structure & File Assets

```text
pod-workflow/
├── ArtHeroes/
│   ├── ART_HEROES_WORKFLOW_GUIDE.md    # This technical guide
│   ├── apply_art_heroes_metadata.py    # Batch metadata embedding script
│   └── art_heroes_prompt.txt           # AI prompt for Art Heroes metadata generation
└── README.md
```
