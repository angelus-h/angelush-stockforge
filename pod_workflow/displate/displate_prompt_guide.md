# DALL-E 3 & Midjourney Prompting Guide for Displate Metal Posters

This guide provides prompt architectures and composition templates to ensure AI-generated artworks natively satisfy Displate manufacturing and quality criteria.

---

## 1. DALL-E 3 Constraints & Solutions

* **Aspect Ratio:** DALL-E 3 generates in standard fixed canvas dimensions:
  * Portrait: `1024 × 1792 px` (~9:16)
  * Landscape: `1792 × 1024 px` (~16:9)
  * Square: `1024 × 1024 px` (1:1)
  *(The Displate **1.4:1** ratio is automatically achieved post-generation using `displate_tool.py prepare`).*
* **Bleed Margins:** The physical steel plate manufacturing process folds outer edges over metal chassis rims. Prompts must strictly demand **central composition and generous breathing room along all outer borders**.
* **Zero Borders Rule:** DALL-E frequently illustrates decorative border trims or white margins. These must be explicitly prohibited in prompt instructions.

---

## 2. DALL-E 3 Master System Prompt (Prefix Prompt)

Prepend this block to prompt instructions or register it as a Custom Instruction:

```text
Create a high-resolution, full-bleed artwork optimized for metal poster printing (Displate standard). 

STRICT COMPOSITION & TECHNICAL CONSTRAINTS:
1. FULL BLEED ONLY: Edge-to-edge artwork. Absolutely NO borders, NO frames, NO white margins, NO passe-partout, and NO vignettes around the edges.
2. SAFE MARGIN / COMPOSITION: Keep all primary subjects, focal points, and action strictly centered in the middle 80% of the canvas. Ensure generous background breathing room along all 4 outer edges so that outer margins can be trimmed without cutting into the subject.
3. NO TYPOGRAPHY / NO TEXT: Do not include any text, titles, slogans, quotes, captions, watermarks, or artist signatures unless explicitly requested.
4. TEXTURE & DETAIL: Focus on rich, crisp micro-details, sharp tactile textures, high dynamic contrast, and deep clean shadows that look stunning on metallic steel surfaces. Avoid blurry, washed-out, or overly plastic/waxy surfaces.
5. ORIENTATION: Vertical portrait orientation (tall format).

SUBJECT DESCRIPTION:
[YOUR CORE SUBJECT AND ARTISTIC AESTHETIC HERE]
```

---

## 3. Typography Directives (If Text Overlays Are Desired)

When graphic quotes or typographic elements are required:

```text
TYPOGRAPHY CONSTRAINTS:
- The text must be strictly centered, perfectly legible, and positioned well inside the safe zone (at least 15% away from any edge).
- Exact text spelling: "[EXACT QUOTED TEXT]"
- No text touching or floating near the canvas boundaries.
```

---

## 4. Top-Performing Displate Aesthetic Modifiers in DALL-E / Midjourney

1. **Dark Metallic / Golden Line Art:**
   `"intricate gold foil line art on deep obsidian black background, fine metallic engraving style, high contrast, luminous details"`
2. **Cyberpunk & Neon Synthwave:**
   `"vibrant neon lighting, deep volumetric shadows, ultra high contrast, reflections on metallic surfaces, dark moody aesthetic"`
3. **Fantasy & Mythological Illustration:**
   `"masterpiece dark fantasy digital painting, crisp detailed brushwork, luminous bioluminescent glow against dark enchanted forest"`
4. **Retro Travel & Vintage Engraving:**
   `"classic woodcut or vintage linocut printmaking style, rich hatched shadows, clean solid color fills, full bleed illustration"`
