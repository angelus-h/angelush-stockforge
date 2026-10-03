# Depositphotos Contributor & Metadata Submission Guide

Comprehensive technical, legal, and metadata guidelines for submitting stock photography and stock video footage to **Depositphotos**.

---

## 1. Overview & Contributor Workflow

Depositphotos operates as a high-volume global microstock agency accepting commercial and editorial stock photos, vectors, illustrations, and stock video clips.

### Ingestion Lifecycle:
1. **Upload:** Files can be uploaded via the web **File Uploader** or via **FTP** (`ftp.depositphotos.com`).
2. **Unfinished Files:** Uploaded media initially lands in **Seller's Menu -> Unfinished Files**.
3. **Metadata Ingestion:**
   - **Photos:** Depositphotos automatically parses embedded **IPTC / XMP** metadata (`Title / Object Name`, `Description / Caption`, `Keywords`).
   - **Videos:** Metadata can be attached directly in the web UI, imported via microstock batch CSV, or managed in the contributor portal.
4. **Review & Approval:** Files are inspected for technical compliance, legal releases, and metadata accuracy before publishing online.

---

## 2. Technical File Requirements

### 📸 Photography Requirements
- **Format:** JPEG / JPG or PNG in standard **sRGB** / RGB color space.
- **Resolution:** Minimum **3.8 Megapixels** (at least `2400 × 1600` pixels).
- **File Size:** Maximum **50 MB** per image.
- **Scaling:** Do **NOT** artificially upscale, stretch, or distort images to satisfy resolution limits. Genuine camera native resolution is required.
- **AI Policy:** **Strictly NO AI-generated images.** Depositphotos does not accept AI-generated content from contributors due to intellectual property policies. Only genuine camera captures and original vector artwork are permitted.

### 🎬 Stock Video Requirements
- **Container Formats:** `.MOV`, `.MP4`, `.AVI`, `.WMV`, `.MPEG`.
- **Codecs:** H.264 / AVC, Apple ProRes, Photo JPEG, Motion JPEG.
- **Duration:** Strictly between **3 seconds and 60 seconds**.
- **Frame Rates (FPS):** Standard broadcast rates: `23.976`, `24`, `25`, `29.97`, `30`, `50`, `59.94`, `60 FPS`.
- **Resolution:** Minimum `320 × 240 px` (standard submissions should be **1080p Full HD (1920×1080)** or **4K UHD (3840×2160)**).
- **File Size Limit:** Up to **4096 MB (4 GB)** per video file.
- **Audio:** Natural ambient environmental sound and background voices are permitted if integral to the scene. Background copyrighted music or unowned audio tracks are strictly prohibited.

---

## 3. Metadata Standards & Editorial Formatting

### 📰 Editorial Content Guidelines
Depositphotos accepts editorial documentation of newsworthy events, cultural landmarks, travel destinations, and everyday public life.

#### Required Dateline Formula:
```text
CITY, COUNTRY – MONTH DAY, YEAR: [Factual sentence describing the subject, action, and context.]
```

#### Core Rules:
1. **The 3 Ws:** Must explicitly answer **Who**, **Where**, and **What**.
2. **No All-Caps:** Use title/sentence casing. Do not capitalize the entire dateline in ALL CAPS.
3. **Official Example:**
   `Berlin, Germany – September 1, 2025: Attendees interact with exhibitors during IFA Berlin, one of the world's leading consumer electronics trade shows.`
4. **Local Lednice Example:**
   `Lednice, Czech Republic – September 29, 2024: Tourists stroll through the formal gardens and courtyard pathways in front of the historic Lednice Castle.`

#### Model Release Requirements:
- **General Scene / Crowd Coverage:** Photos and videos displaying crowds, pedestrians in wide angles, and participants in public heritage spaces do **not** require model releases under the Editorial license.
- **Isolated Portraits:** A close-up or isolated shot focusing primarily on an identifiable individual requires a signed Model Release even if captured in a public venue.

---

### 🛍️ Commercial Content Guidelines
- **Title / Description:** Concise, factual description in English (3–10 words for titles, 1–2 descriptive sentences).
- **Subject Restrictions:** No visible brand logos, trademarks, modern registered buildings, or vehicle license plates.
- **Keywords:** Strictly **25–45 relevant lowercase English keywords**, separated by commas.
  - Prioritize specific literal terms first (e.g. `lednice castle, czech republic, chateau, neo-gothic, formal garden`).
  - Follow with thematic, seasonal, lighting, and environmental tags (`autumn, travel, tourism, architecture, exterior, sunny`).

---

## 4. FTP Upload Connection Details

Depositphotos provides dedicated FTP access for batch uploads:

| Parameter | Configuration Value |
| :--- | :--- |
| **Protocol** | Standard FTP |
| **Server / Host** | `ftp.depositphotos.com` |
| **Port** | `21` |
| **Username** | Your Depositphotos Contributor Username / Login |
| **Password** | Your Depositphotos Account Password |
| **Remote Directory** | `/` (root) |
| **Passive Mode** | Supported (recommended) |

---

## 5. StockForge Integration

- **FTP Uploader Hub:** Accessible directly inside `dashboard/app.py` under the **🚀 Agency FTP / SFTP Uploader Hub** expander. Select the `Depositphotos` preset to test connection and dispatch batches directly.
- **Credential Storage:** Passwords can be stored securely in the Windows Credential Manager (`DEPOSITPHOTOS_PASSWORD`) via `credentials.py`.
- **Metadata Alignment:** The AI-generated metadata from `stock-video-workflow` and `stock-workflow` directly conforms to Depositphotos standards:
  - Titles match Adobe/Shutterstock rules.
  - Editorial descriptions match the required `City, Country – Month Day, Year: Description` syntax.
  - Embedded IPTC/XMP in JPEGs automatically auto-fills all fields upon upload.
