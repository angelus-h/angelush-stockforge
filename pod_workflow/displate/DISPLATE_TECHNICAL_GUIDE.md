# Displate Technical & Quality Guidelines

This guide summarizes the strict technical specifications, automated bot screening rules, manual curator review criteria, and typical rejection triggers for publishing fine art metal posters on the Displate marketplace.

---

## 1. Displate Two-Phase Review System

1. **Phase 1: Automated Preflight Validation (Bot / Validation Algorithm)**
   - Executes within minutes to a few hours post-upload.
   - Strictly algorithmic; non-compliant submissions are immediately rejected with `"Deactivated / technical requirements not being met"`.
   - **Immediate Rejection Triggers:**
     - Incorrect aspect ratio (deviating from 1.4:1 / 1:1.4 or native camera 3:2 tolerance).
     - Shortest side under 2900 px.
     - Missing or sub-300 DPI resolution tags in file headers (e.g., standard AI 72 or 96 DPI).
     - Text, logos, borders, or critical signatures within 200 px of the perimeter (Safe Zone violation).
     - Heavy AI upscaling artifacts or low-resolution pixelation.
     - Prohibited words detected via image OCR.

2. **Phase 2: Manual Review ("Under review")**
   - Assets passing Phase 1 enter the human curator queue (typically 24–72 hours).
   - Human art directors and legal editors inspect:
     - 100% zoom print resolution (micro-contrast, edge sharpness, authentic texture).
     - AI anatomical deformities (warped hands, fused eyes, melted architectural lines).
     - Intellectual property, trademarked logos, recognizable copyrighted characters.
     - Tastefulness and NSFW/prohibited themes.

---

## 2. Hard Technical Specifications

| Parameter | Specification | Practical Notes |
| :--- | :--- | :--- |
| **Aspect Ratio** | **Strictly 1.4 : 1** (or 1 : 1.4) | Portrait strongly recommended (XL size is only produced in Portrait). |
| **Minimum Resolution** | **Shortest side: min. 2900 px** | Standard production target: **4060 × 2900 px** (or larger, e.g. 5684 × 4060 px). |
| **DPI** | **Strictly 300 DPI** | Must be explicitly embedded in EXIF/JFIF header. |
| **Safe Zone** | **Min. 200 px from edges** | Sheet metal edges are mechanically folded! Zero text or logos near borders. |
| **File Format** | **JPG, PNG, WEBP, AVIF** | For JPG: 95–100% quality, 4:4:4 chroma subsampling. |
| **File Size Limit** | **Max. 30 MB** | System rejects files over 30 MB immediately. |
| **Color Space** | **sRGB or AdobeRGB (1998)** | Always embed an ICC profile. |
| **Borders & Watermarks** | **Strictly Prohibited** | Never add artificial frames, white/black borders, or edge signatures. |

---

## 3. Real-World Findings: Why Real Photography Passes and AI Art Fails

### The Aspect Ratio Reality (3:2 vs. 1.4:1):
While Displate documentation specifies **1.4:1** (7:5), native camera **3:2 (1.5:1)** photos (e.g. macro spider on orchid, historic castle vistas) pass review seamlessly with negligible outer bleed.
Rejections stem not from minor camera aspect differences, but from **BORDERS**, **SAFE ZONE INFRINGEMENTS**, and **WAXY UPSCALING SMOOTHING**!

| Attribute | Authentic Photography - APPROVED ✅ | Rejected AI Generations ❌ |
| :--- | :--- | :--- |
| **Borders** | **Zero borders.** Full bleed edge-to-edge organic background. | **Artificial border / framing.** Displate's #1 cause of rejection (the metal plate is already the frame). |
| **Text & Signatures** | No text. | Text touching the 200 px outer perimeter (Safe Zone breach) or typos. |
| **Optical Micro-Detail** | **Natural optical texture:** spider bristles, leaf veins, stonework grain, authentic sensor noise. | Artificial upscaler smoothing ("waxy/plastic" skin, gelatinous look at 100% zoom). |
| **EXIF Header** | Embedded camera shutter, aperture, 300 DPI. | AI generator default 72–96 DPI, missing photographic headers. |

### Pitfalls in AI Art (Midjourney / DALL-E) and Remedies:
1. **Unwanted Generated Borders:** AI models often illustrate poster borders or white card margins. Crop them out completely before uploading!
2. **Upscayl "Digital Art" Plastic Effect:** Upscalers over-smooth organic surfaces. Always inject 0.8–1.2% subtle film grain to pass automated print inspection.
3. **Missing 300 DPI:** Use `displate_tool.py` to write 300 DPI directly into the EXIF header.
4. **Text Near Perimeter:** Place text overlays only after cropping, anchored at least 300 px inward from any edge.

---

## 4. Displate Asset Preparation Best Practices

1. **Generation:** Render directly in Displate ratio when possible (Midjourney: `--ar 5:7` or `--ar 10:14`).
2. **Upscaling:** Use appropriate models (UltraSharp for intricate details, Remacri for painterly styles).
3. **Automated Normalization via `displate_tool.py`:**
   - Auto-crop to exact 1.4:1 (e.g. 4060 × 2900 px).
   - Inject 300 DPI header.
   - Embed sRGB profile.
   - Inject subtle micro-grain (0.8–1.2%) to break synthetic waxy smoothness and present authentic print substrate texture.
4. **Text Placement:** Position any typography on a separate layer after upscaling and cropping, keeping a 300 px perimeter buffer.

---

## 5. Upscayl Model Selection Matrix

| Model | Ideal Use Case | Strengths | Displate Rejection Risk |
| :--- | :--- | :--- | :--- |
| **⭐ UltraSharp (4x-UltraSharp)** | **Intricate AI scenes, fantasy, textured illustrations, engravings** | **Top all-rounder.** Retains micro-contrast, hair, metallic glints, and fine feathers without waxy blurring. | **Very Low.** Passes automated review smoothly. |
| **⭐ Remacri** | **Oil paintings, watercolors, classical art, masonry, wood grain** | Preserves brushstroke depth and surface topography; renders natural analog finish. | **Very Low.** Effectively masks synthetic AI origins. |
| **General Photo (Real-ESRGAN)** | **Camera photography (landscapes, architecture, macros)** | Preserves genuine optical noise and lens sharpness without cartoonish edges. | **Minimal.** Ideal for real camera captures. |
| **Digital Art** | **Flat vectors, simple cartoons, pop art, stickers ONLY** | Produces crisp outlines and flat gradients. | **⚠️ Extremely High Risk for detailed art.** Creates plastic/waxy textures that trigger manual review rejection. |
