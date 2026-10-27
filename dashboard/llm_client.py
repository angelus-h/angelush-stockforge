"""
Unified AI Client for StockForge.
Supports:
1. Local Ollama (100% Free, Private, $0.00 cost using installed local models like llava, llama3.2, qwen)
2. Direct Google Gemini REST API (~$0.002/image cloud backup)

Supports generating for Art Heroes only, Displate only, or Both platforms simultaneously.
"""

import os
import io
import re
import json
import base64
import requests
from pathlib import Path
from PIL import Image

OLLAMA_API_URL = "http://localhost:11434/api/generate"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"

ART_HEROES_PROMPT_TEMPLATE = """You are an expert Fine Art Print-on-Demand (POD) copywriter specializing in European interior design sales for Art Heroes / Werk aan de Muur.
Visual Scene Description: {description}

Generate fine art metadata strictly adhering to:
1. 'title': [Emotional Mood] + [Core Subject] + [Explicit Room/Styling Suggestion]
2. 'description': Strictly 3 cohesive paragraphs separated by double newlines:
   - Para 1: Atmospheric visual storytelling, lighting, mood, season.
   - Para 2: Specific interior room recommendations (Living Room, Bedroom, Kitchen, etc.) and matching styles (Scandinavian, Modern Rustic, Contemporary).
   - Para 3: Available finishes (textured canvas, framed prints, sleek acrylic, metal). {attribution_instruction}
3. 'keywords': Array of strictly 12 high-relevance search tags.

Output exclusively valid JSON:
{{
  "title": "...",
  "description": "Paragraph 1\\n\\nParagraph 2\\n\\nParagraph 3",
  "keywords": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10", "tag11", "tag12"]
}}"""

DISPLATE_PROMPT_TEMPLATE = """You are an expert Print-on-Demand copywriter specializing in metal posters for Displate.
Visual Scene Description: {description}

Generate fine art metadata strictly adhering to:
1. 'title': Catchy, evocative, fine art metal poster title strictly under 60 characters.
2. 'description': Strictly between 450 and 470 characters in total length (including spaces). High-impact fine art copywriting highlighting luminous contrast on steel metal finish (matte/gloss) and modern wall decor appeal. {attribution_instruction}
3. 'tags': Array of up to 20 highly searchable tags (1-2 words each, e.g. fine art, metal print, wall decor, landscape, architecture, modern art).

Output exclusively valid JSON:
{{
  "title": "...",
  "description": "Engaging description strictly 450-470 characters long.",
  "tags": ["fine art", "metal print", "wall decor", "landscape", "modern art"]
}}"""

REDBUBBLE_2026_SEO_PROMPT_TEMPLATE = """You are an elite Print-on-Demand (POD) SEO & Metadata Specialist specifically optimizing for Redbubble and Google Search indexing in 2026.
Analyze the provided artwork image and generate metadata formatted strictly as a valid JSON object.
Visual Scene Description: {description}

STRICT REDBUBBLE SEO & CONTENT RULES:

1. TRADEMARK & BRAND SAFETY (CRITICAL):
   - ABSOLUTELY ZERO trademarked brand names, company logos, or copyrighted terms (e.g., NEVER use "LinkedIn", "Red Hat", "Photoshop", "Windows", "Disney", etc.).
   - If the artwork contains satire, tech humor, or parody, replace all brand references with generic or parody equivalents (e.g., use "professional networking site" instead of "LinkedIn", "open source linux" instead of "Red Hat").

2. TITLE (40-50 characters max):
   - Formula: [Specific Descriptor] + [Subject/Niche] + [Art Style/Vibe] + [Product Hint]
   - Front-load the most important 30 characters with high-intent keywords for mobile buyers.
   - Write natural English. NO keyword stuffing, NO generic titles ("Cool Art", "Funny Poster").

3. TAGS (EXACTLY 15 MULTI-WORD PHRASES):
   - Provide EXACTLY 15 multi-word tag phrases separated by commas in a single string.
   - Apply the 60/40 Split Rule:
     * 9 tags (60%): Specific long-tail search phrases (2-5 words each) describing the exact subject, satire joke, or specific scene (e.g., "sysadmin caffeine coding skull", "infrared calvary landscape print").
     * 6 tags (40%): Broader room decor, aesthetic, and gift phrases (2-4 words each) capturing the vibe or buyer intent (e.g., "minimalist zen bedroom decor", "gift for software engineer").
   - STRICT TAG RESTRICTIONS:
     * EVERY tag MUST be a multi-word phrase (2 to 5 words). NO SINGLE-WORD TAGS (e.g., BAN "art", "photo", "funny", "poster").
     * BANNED SPAM WORDS: Do NOT use "best selling", "trending", "top selling", "cheap", "viral", "discount", "gift".
     * Order: Place the top 10 most critical search terms FIRST (Google indexes only the first 10 tags).

4. DESCRIPTION (60-120 words):
   - Write 2-3 engaging, prose paragraphs in clear English.
   - Paragraph 1: Visual depiction, color palette, mood, and artistic technique.
   - Paragraph 2: Ideal interior design placement (e.g., modern living room, home office, gaming room) OR target personality/gift audience (e.g., sysadmins, Linux lovers, fine art collectors).
   - DO NOT copy the title verbatim. DO NOT list tags as comma-separated lists.

5. PRIMARY PRODUCT DETECTION:
   - Determine the most natural primary display product:
     * Set "Wall Art" for fine art photography, landscapes, oil/watercolor styles, and complex digital paintings.
     * Set "Sticker" or "T-Shirt" for tech humor, code jokes, vector logos, slogans, or pop-art illustrations.

OUTPUT FORMAT (STRICT JSON ONLY):
{{
  "title": "Front-loaded Specific Descriptor Subject Style Poster",
  "tags": "multi word tag 1, multi word tag 2, multi word tag 3, multi word tag 4, multi word tag 5, multi word tag 6, multi word tag 7, multi word tag 8, multi word tag 9, multi word tag 10, multi word tag 11, multi word tag 12, multi word tag 13, multi word tag 14, multi word tag 15",
  "description": "Engaging prose description of visual style, mood, interior context, and gift suitability.",
  "primary_product": "Wall Art"
}}"""

REDBUBBLE_WALLART_PROMPT_TEMPLATE = REDBUBBLE_2026_SEO_PROMPT_TEMPLATE + "\n\nFOCUS CONSTRAINT: Bias primary_product detection to 'Wall Art'."
REDBUBBLE_MERCH_PROMPT_TEMPLATE = REDBUBBLE_2026_SEO_PROMPT_TEMPLATE + "\n\nFOCUS CONSTRAINT: Bias primary_product detection to 'Sticker' or 'T-Shirt'."

def is_hybrid_requested(user_context="", flag_value=False):
    """Detect whether Adobe Stock / Posters.cz Hybrid metadata is requested via flag or context text."""
    if flag_value:
        return True
    if not user_context or not isinstance(user_context, str):
        return False
    ctx_low = user_context.lower()
    hybrid_triggers = [
        "hybrid", "hibrid", "posters.cz", "posters", "europosters",
        "lakberendez", "belsőépít", "interior design", "wall decor",
        "wall art hybrid", "adobe hybrid", "poster print"
    ]
    return any(trig in ctx_low for trig in hybrid_triggers)


ADOBE_HYBRID_STOCK_PROMPT_TEMPLATE = """You are an elite stock photography & multi-agency metadata specialist.
The photographer sells images across two distinct channels:
1. ADOBE STOCK (automatically synced to European art print marketplace https://www.posters.cz/):
   Requires a HYBRID metadata set combining factual landmark/subject accuracy WITH refined interior design / wall decor copywriting.
2. GENERAL MICROSTOCK AGENCIES (Alamy, Vecteezy, Shutterstock, Depositphotos, Dreamstime, Pond5):
   Requires PURE, FACTUAL, DRY microstock metadata with NO interior design / wall decor keywords or marketing fluff.

Visual Scene Description: {description}
Editorial Mode: {editorial_instruction}

Generate TWO distinct metadata sets:

PART 1: 'adobe' (For Adobe Stock & Posters.cz Wall Art):
1. 'title': Sophisticated hybrid title strictly 6 to 14 words (under 150 chars).
   MANDATORY HYBRID FORMULA: [Specific Landmark / Subject + Concrete Location] - [Aesthetic Mood] [Interior Wall Art / Poster / Wall Decor]
   Examples:
   - 'Historic Retz Calvary Hill Statues in Austria - Rustic Fine Art Wall Decor'
   - 'Keleti Railway Station Facade in Budapest - Architectural Wall Art Poster'
   - 'Luminous Alpine Forest at Sunrise - Serene Nature Print for Modern Living Room'
   - 'Fairytale Bory Castle with Blue Sky - Elegant Architectural Poster Wall Art'
2. 'description': Refined hybrid caption under 450 characters (1 single cohesive paragraph). Identifies subject and location, concluding with interior styling advice for posters.cz customers (e.g. 'Ideal as an evocative wall art print or framed poster for contemporary living rooms, bedrooms, or modern office spaces.'). {editorial_desc_rule}
3. 'keywords': Array of strictly 35 to 45 lowercase tags. MANDATORY DUAL-LAYER KEYWORDS: fusing microstock location tags (first 15-20 tags: city, country, landmark, lighting) AND Interior Design, Wall Art & Posters.cz Search Terms (15-20 tags: 'wall art', 'interior design', 'home decor', 'wall decor', 'poster', 'fine art print', 'canvas art', 'living room decor', 'bedroom wall art', 'modern interior', 'room styling', 'framed art').
4. 'category': Best matching category name (e.g. 'Buildings and Architecture', 'Travel', 'Landscapes', 'Nature').

PART 2: 'stock' (For ALL other Microstock Agencies: Alamy, Vecteezy, Shutterstock, Depositphotos, Dreamstime, Pond5):
1. 'title': Pure factual microstock title strictly 3 to 8 words (sentence case, max 200 chars).
   MANDATORY: Must include specific subject/landmark AND concrete geographic location (city/town, country). E.g. 'Calvary hill statues in Retz Austria'.
   NEVER include wall decor words ('wall art', 'poster', 'decor').
2. 'description': Strictly factual, clear microstock description under 500 characters. Factual details of subject, architecture, location. NO wall decor or room styling recommendations! {editorial_desc_rule}
3. 'keywords': Array of strictly 25 to 35 lowercase search tags. Pure microstock tags (concrete location, subject, lighting, orientation). NO wall art, interior design, or poster keywords!
4. 'category': Best matching category name (e.g. 'Buildings and Architecture', 'Travel', 'Landscapes', 'Nature').

Output EXCLUSIVELY valid JSON:
{{
  "adobe": {{
    "title": "...",
    "description": "...",
    "keywords": ["tag1", "tag2", "tag3", "tag4", "tag5", "..."],
    "category": "Travel"
  }},
  "stock": {{
    "title": "...",
    "description": "...",
    "keywords": ["tag1", "tag2", "tag3", "tag4", "tag5", "..."],
    "category": "Travel"
  }}
}}"""

STOCK_PROMPT_TEMPLATE = """You are an expert Microstock Photography metadata optimizer specifically trained for major agencies (Adobe Stock, Vecteezy, Alamy, Shutterstock).
Visual Scene Description: {description}
Editorial Mode: {editorial_instruction}

Generate compliant stock metadata adhering strictly to:
1. 'stock_title': Strictly between 3 and 8 words (maximum 200 characters). Sentence capitalization, no subjective filler words ('beautiful', 'stunning', 'amazing').
   - MANDATORY SUBJECT & LOCATION: The title MUST explicitly feature both the specific landmark / depicted subject AND the geographic location (city/town, country), e.g. 'Calvary hill statues in Retz Austria' or 'Keleti railway station facade Budapest Hungary'. NEVER generate vague generic titles like 'Statues on a hill' or 'Landscape with blue sky'.
2. 'stock_description': Clear, factual description (under 500 characters). Explicitly identify the specific landmark, architectural elements, historical/cultural context, and exact city/region/country. {editorial_desc_rule}
3. 'stock_keywords': Array of strictly 25 to 35 lowercase search tags.
   - MANDATORY SUBJECT & GEOGRAPHIC TAGS: The first keywords MUST explicitly include the concrete city/town, region, and country (e.g. 'retz', 'austria', 'lower austria', 'niederosterreich', 'europe') AND the specific subject, landmark name, and cultural/religious terminology (e.g. 'calvary', 'kalvarienberg', 'stations of the cross', 'crucifixion', 'saint veronica', 'jesus christ', 'statues', 'catholic').
   - Additional visual tags: 'no people' if no person is present, orientation ('horizontal' or 'vertical'), time/lighting ('daylight', 'sunny', 'blue sky').
   - Letters and spaces only (use spaces instead of hyphens, e.g. 'close up', 'stations of the cross').
   - No subjective buzzwords, no slang, no brand trademarks.
4. 'stock_category': Best matching category name (e.g. 'Buildings and Architecture', 'Travel', 'Landscapes', 'The Environment', 'Transport', 'Technology', 'People', 'Nature').

Output exclusively valid JSON:
{{
  "stock": {{
    "title": "...",
    "description": "...",
    "keywords": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10", "tag11", "tag12", "tag13", "tag14", "tag15", "tag16", "tag17", "tag18", "tag19", "tag20", "tag21", "tag22", "tag23", "tag24", "tag25"],
    "category": "Travel"
  }}
}}"""

ALL_PLATFORMS_PROMPT_TEMPLATE = """You are an elite multi-agency copywriter specializing in Fine Art Print-on-Demand (Art Heroes & Displate) AND Microstock Photography (Adobe Stock, Vecteezy, Alamy).
Visual Scene Description: {description}
Editorial Mode: {editorial_instruction}

Produce high-converting metadata adhering strictly to all three platform specifications:

1. ART HEROES RULES:
- 'title': [Emotional Mood] + [Core Subject] + [Explicit Room/Styling Suggestion]
- 'description': Strictly 3 cohesive paragraphs separated by double newlines:
  * Para 1: Atmospheric visual storytelling, lighting, mood, season.
  * Para 2: Specific interior room recommendations and matching decor styles.
  * Para 3: Available finishes (canvas, acrylic, framed). {attribution_instruction}
- 'keywords': Array of strictly 12 high-relevance search tags.

2. DISPLATE RULES:
- 'displate_title': Punchy, evocative metal poster title strictly under 60 characters.
- 'displate_description': Strictly between 450 and 470 characters in total length (including spaces). Highlight steel finish contrast and modern wall decor appeal. {attribution_instruction}
- 'displate_tags': Array of up to 20 highly searchable tags (1-2 words each).

3. MICROSTOCK (STOCK) RULES:
- 'stock_title': Strictly between 3 and 8 words (sentence case). MANDATORY: Must include the specific landmark/subject name AND geographic location (city/town, country). E.g. 'Calvary hill statues in Retz Austria'.
- 'stock_description': Factual caption under 500 characters. Explicitly identify the specific landmark, architectural elements, historical/cultural context, and exact city/region/country. {editorial_desc_rule}
- 'stock_keywords': Array of 25 to 35 lowercase search tags. First keywords must include the concrete city/town, region, country, specific subject, landmark name, and cultural/religious terminology (e.g. 'retz', 'austria', 'lower austria', 'calvary', 'kalvarienberg', 'stations of the cross', 'jesus christ', 'statues', 'no people', 'horizontal', 'blue sky'). No hyphens, no buzzwords.
- 'stock_category': Agency category name (e.g. 'Buildings and Architecture', 'Travel', 'Landscapes', 'Nature').

Output EXCLUSIVELY valid JSON matching this exact structure:
{{
  "artheroes": {{
    "title": "...",
    "description": "Paragraph 1\\n\\nParagraph 2\\n\\nParagraph 3",
    "keywords": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10", "tag11", "tag12"]
  }},
  "displate": {{
    "title": "...",
    "description": "Engaging description strictly 450-470 characters long.",
    "tags": ["fine art", "metal print", "wall decor", "landscape", "modern art"]
  }},
  "stock": {{
    "title": "...",
    "description": "...",
    "keywords": ["tag1", "tag2", "tag3", "tag4", "tag5", "..."],
    "category": "Travel"
  }}
}}"""

ALL_PLATFORMS_HYBRID_PROMPT_TEMPLATE = """You are an elite multi-agency copywriter specializing in Fine Art Print-on-Demand (Art Heroes & Displate), Adobe Stock (synced to Posters.cz), AND General Microstock (Alamy, Vecteezy, Shutterstock, Depositphotos, Dreamstime, Pond5).
Visual Scene Description: {description}
Editorial Mode: {editorial_instruction}

Produce high-converting metadata adhering strictly to all platform specifications:

1. ART HEROES RULES:
- 'title': [Emotional Mood] + [Core Subject] + [Explicit Room/Styling Suggestion]
- 'description': Strictly 3 cohesive paragraphs separated by double newlines:
  * Para 1: Atmospheric visual storytelling, lighting, mood, season.
  * Para 2: Specific interior room recommendations and matching decor styles.
  * Para 3: Available finishes (canvas, acrylic, framed). {attribution_instruction}
- 'keywords': Array of strictly 12 high-relevance search tags.

2. DISPLATE RULES:
- 'displate_title': Punchy, evocative metal poster title strictly under 60 characters.
- 'displate_description': Strictly between 450 and 470 characters in total length (including spaces). Highlight steel finish contrast and modern wall decor appeal. {attribution_instruction}
- 'displate_tags': Array of up to 20 highly searchable tags (1-2 words each).

3. ADOBE STOCK & POSTERS.CZ HYBRID RULES ('adobe'):
- These assets are synced directly to https://www.posters.cz/ as wall art posters.
- 'title': Sophisticated hybrid title strictly 6 to 14 words (under 150 chars). MANDATORY FORMULA: [Specific Subject / Landmark + Concrete Location] - [Aesthetic Mood] [Interior Wall Art / Poster / Wall Decor]. E.g. 'Historic Retz Calvary Hill Statues in Austria - Rustic Fine Art Wall Decor'.
- 'description': Single cohesive paragraph under 450 characters combining factual subject/location description with an interior styling recommendation for posters.cz customers (e.g. 'Evocative fine art wall decor suitable for living rooms, bedrooms, or modern offices.'). {editorial_desc_rule}
- 'keywords': Array of strictly 35 to 45 lowercase tags fusing microstock location tags (city, country, landmark, lighting) AND interior design/poster search tags ('wall art', 'interior design', 'home decor', 'wall decor', 'poster', 'fine art print', 'living room decor', 'modern interior', 'room styling', 'framed print', 'aesthetic decor').
- 'category': Agency category name (e.g. 'Buildings and Architecture', 'Travel', 'Landscapes', 'Nature', 'Lifestyle', 'Graphic Resources').

4. GENERAL MICROSTOCK RULES ('stock') - For Alamy, Vecteezy, Shutterstock, Depositphotos, Dreamstime, Pond5:
- 'title': Pure factual microstock title strictly 3 to 8 words (sentence case, max 200 chars). Specific Subject + Location only. NO wall decor terms!
- 'description': Factual caption under 500 characters. Factual scene details only. NO wall decor marketing or room styling! {editorial_desc_rule}
- 'keywords': Array of strictly 25 to 35 lowercase search tags. Pure microstock tags (concrete location, subject, lighting, orientation). NO wall art, interior design, or poster keywords!
- 'category': Agency category name (e.g. 'Buildings and Architecture', 'Travel', 'Landscapes', 'Nature').

Output EXCLUSIVELY valid JSON matching this exact structure:
{{
  "artheroes": {{
    "title": "...",
    "description": "Paragraph 1\\n\\nParagraph 2\\n\\nParagraph 3",
    "keywords": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10", "tag11", "tag12"]
  }},
  "displate": {{
    "title": "...",
    "description": "Engaging description strictly 450-470 characters long.",
    "tags": ["fine art", "metal print", "wall decor", "landscape", "modern art"]
  }},
  "adobe": {{
    "title": "...",
    "description": "...",
    "keywords": ["tag1", "tag2", "tag3", "tag4", "tag5", "..."],
    "category": "Travel"
  }},
  "stock": {{
    "title": "...",
    "description": "...",
    "keywords": ["tag1", "tag2", "tag3", "tag4", "tag5", "..."],
    "category": "Travel"
  }}
}}"""

COMBINED_PROMPT_TEMPLATE = """You are an elite Print-on-Demand (POD) fine art copywriter specializing in Art Heroes (European interior design) and Displate (metal posters).
Visual Scene Description: {description}

Produce high-converting fine art metadata adhering strictly to the respective guidelines for both platforms.

1. ART HEROES RULES:
- 'title': [Emotional Mood] + [Core Subject] + [Explicit Room/Styling Suggestion]
- 'description': Strictly 3 cohesive paragraphs separated by double newlines:
  * Para 1: Atmospheric visual storytelling, lighting, mood, season.
  * Para 2: Specific interior room recommendations and matching decor styles.
  * Para 3: Available finishes (canvas, acrylic, framed). {attribution_instruction}
- 'keywords': Array of strictly 12 high-relevance search tags.

2. DISPLATE RULES:
- 'displate_title': Punchy, evocative metal poster title strictly under 60 characters.
- 'displate_description': Strictly between 450 and 470 characters in total length (including spaces). Highlight steel finish contrast and modern wall decor appeal. {attribution_instruction}
- 'displate_tags': Array of up to 20 highly searchable tags (1-2 words each).

Output EXCLUSIVELY valid JSON matching this exact structure:
{{
  "artheroes": {{
    "title": "...",
    "description": "Paragraph 1\\n\\nParagraph 2\\n\\nParagraph 3",
    "keywords": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10", "tag11", "tag12"]
  }},
  "displate": {{
    "title": "...",
    "description": "Engaging description strictly 450-470 characters long.",
    "tags": ["fine art", "metal print", "wall decor", "landscape", "modern art"]
  }}
}}"""


def encode_thumbnail_base64(image_path, max_dim=512):
    """Resize image to max_dim and return base64 string, handling JPG, PNG, and RAW/DNG/ORF formats."""
    try:
        from dashboard import raw_loader
        return raw_loader.encode_thumbnail_base64(image_path, max_dim=max_dim)
    except Exception:
        pass
    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = bg
        else:
            img = img.convert("RGB")
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode("utf-8")


def get_local_vision_description(image_path, vision_model="llava:7b", user_context="", timeout=90):
    """Use local vision model (llava:7b or moondream) to describe image."""
    b64 = encode_thumbnail_base64(image_path, max_dim=512)
    vision_prompt = "Describe this fine art landscape photograph in detail: subject, colors, lighting, location, and atmosphere."
    if user_context and user_context.strip():
        vision_prompt += f" Note the photographer's context: {user_context.strip()}. Do not mistake infrared foliage for winter snow."

    payload = {
        "model": vision_model,
        "prompt": vision_prompt,
        "images": [b64],
        "stream": False
    }
    resp = requests.post(OLLAMA_API_URL, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Ollama Vision error ({resp.status_code}): {resp.text}")
    return resp.json().get("response", "").strip()


def strip_ai_photo_attributions(text):
    """Strip any photographer or creator attribution taglines for AI generated images."""
    if not text:
        return text
    patterns = [
        r"(?:Original\s+)?fine\s+art\s+photography\s+by\s+[^.]*\.?",
        r"Original\s+photography\s+by\s+[^.]*\.?",
        r"(?:Digital\s+)?artwork\s+created\s+by\s+[^.]*\.?",
        r"(?:Digital\s+)?artwork\s+by\s+[^.]*\.?",
        r"Created\s+by\s+Angelus\s+H\.?",
        r"Photography\s+by\s+[^.]*\.?",
    ]
    for p in patterns:
        text = re.sub(p, "", text, flags=re.IGNORECASE)
    return text.strip()


def filter_ai_keywords(kws):
    """Filter out photography and camera keywords for AI generated images."""
    if not isinstance(kws, list):
        return kws
    banned = {"photography", "photograph", "camera", "dslr", "lens", "shutter"}
    cleaned = []
    for k in kws:
        k_lower = k.lower()
        if any(b in k_lower.split() for b in banned) or "fine art photography" in k_lower:
            continue
        cleaned.append(k)
    return cleaned


TRADEMARK_REPLACEMENTS = {
    r"\blinkedin\b": "professional networking site",
    r"\bred\s+hat\b": "open source linux",
    r"\bphotoshop\b": "photo editing software",
    r"\bwindows\b": "operating system",
    r"\bdisney\b": "fairy tale animation",
    r"\bapple\b": "tech brand",
    r"\bmicrosoft\b": "tech enterprise",
    r"\binstagram\b": "photo sharing platform",
    r"\btwitter\b": "social network",
    r"\btiktok\b": "short video platform",
    r"\bfacebook\b": "social network",
}


def sanitize_redbubble_trademarks(text: str) -> str:
    """Replace trademarked brand names and logos with generic equivalents for Redbubble safety."""
    if not text:
        return text
    result = text
    for pattern, replacement in TRADEMARK_REPLACEMENTS.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def normalize_redbubble_title(title: str) -> str:
    """
    Sanitize and format direct Redbubble title to 40-50 characters max.
    Formula: [Specific Descriptor] + [Subject/Niche] + [Art Style/Vibe] + [Product Hint].
    Front-loads the most important high-intent keywords for mobile buyers and removes trademarks.
    """
    if not title:
        return "Serene Alpine Nature Landscape Fine Art Print"
    t = sanitize_redbubble_trademarks(title)
    t = t.strip().strip('"\'')
    t = re.sub(r"\s{2,}", " ", t).strip(" -–—|:,.")
    # If excessively long (> 55 chars), trim cleanly to nearest word boundary under 50 chars
    if len(t) > 55:
        trimmed = t[:50].rsplit(" ", 1)[0].rstrip(",;:- ")
        if len(trimmed) >= 20:
            t = trimmed
    return t


def normalize_redbubble_description(desc: str, max_words: int = 140, max_chars: int = None, is_ai: bool = False) -> str:
    """
    Sanitize and ensure length adheres to 2026 guidelines (60-120 words across 2-3 engaging prose paragraphs).
    Paragraph 1: Visual depiction, color palette, mood, and artistic technique.
    Paragraph 2: Ideal interior design placement or target personality/gift audience.
    """
    if not desc:
        return ""
    d = sanitize_redbubble_trademarks(desc)
    d = d.strip().strip('"\'')
    if is_ai:
        d = strip_ai_photo_attributions(d)
    d = re.sub(r"[ \t]{2,}", " ", d).strip()

    # If legacy caller specifically enforces character limit (e.g. max_chars=245)
    if max_chars is not None:
        if len(d) <= max_chars:
            return d
        trimmed = d[:max_chars].rsplit(" ", 1)[0].rstrip(",;:- ")
        if not trimmed.endswith((".", "!", "?")):
            trimmed += "."
        return trimmed

    # Word-based target (60-120 words, max 140 buffer)
    words = d.split()
    if len(words) <= max_words:
        return d
    trimmed_words = " ".join(words[:max_words]).rstrip(",;:- ")
    if not trimmed_words.endswith((".", "!", "?")):
        trimmed_words += "."
    return trimmed_words


def clean_redbubble_title(ah_title: str) -> str:
    """
    Produce an evocative, descriptive fine art title strictly between 4 and 8 words,
    focusing on emotional visual mood and atmosphere. Specific landmark/location
    is intentionally highlighted in the Description and Supporting Tags for optimal CTR & SEO.
    """
    if not ah_title:
        return "Serene Landscape Reflection in Lake"
    t = ah_title.strip()
    
    # Strip room and interior styling suffixes
    patterns = [
        r"\s*[-–—|:]\s*(?:for\s+)?(?:luxury\s+|wellness\s+|spa\s+|living\s+room|bedroom|office|modern|scandinavian|interior|wall\s+art|wall\s+decor|decor|home\s+decor|rustic|contemporary).*",
        r"\s+(?:for|in)\s+(?:the\s+)?(?:modern\s+|rustic\s+|contemporary\s+|scandinavian\s+|luxury\s+|wellness\s+)?(?:living\s+room|bedroom|kitchen|office|dining\s+room|spa|interior(?:\s+decor)?).*",
    ]
    for pat in patterns:
        t = re.sub(pat, "", t, flags=re.IGNORECASE).strip()
    
    # Remove dry/obscure geographic location names from Title to keep it universally compelling
    t = re.sub(r"\b(?:Lednice\s+Minaret|Lednice\s+Castle|Lednice|Retz|South\s+Moravia|Czech\s+Republic|Moravia|Lower\s+Austria|Austria)\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s{2,}", " ", t).strip(" -–—|:,.")
    
    # If stripping left a very short title, restore visual descriptive essence
    if not t or len(t.split()) < 2:
        t = "Serene Autumn Lake Water Mirror Reflection"
    
    words = t.split()
    # Ensure 4 to 8 words
    if len(words) < 4:
        if len(words) == 3:
            t = f"Serene {t}"
        elif len(words) == 2:
            t = f"Serene Reflection of {t}"
        elif len(words) == 1:
            t = f"Serene {t} Water Reflection"
        words = t.split()
        
    if len(words) > 8:
        t = " ".join(words[:8]).rstrip(",;:- ")
        
    # Strip dangling trailing prepositions / incomplete suffixes
    t = re.sub(r"\s+(?:for|in|at|of|and|with|the|on|to)(?:\s+(?:refined|modern|spacious|elegant|historic|luxury))?\s*$", "", t, flags=re.IGNORECASE).strip(" -–—|:,.")
        
    return t


def clean_redbubble_description(ah_description: str, max_chars: int = 245) -> str:
    """
    Craft the story and meaning behind the artwork (<250 chars) for Redbubble.
    Explicitly features the authentic location and landmark, balanced with emotional resonance and interior harmony.
    """
    if not ah_description:
        return "A graceful historic tower rises in peaceful stillness, mirrored across tranquil waters. Brings timeless harmony and serene beauty to your living room decor."
        
    paragraphs = [p.strip() for p in ah_description.split("\n\n") if p.strip()]
    p1 = paragraphs[0] if paragraphs else ah_description.strip()
    p2 = paragraphs[1] if len(paragraphs) > 1 else ""
    
    # Strip institutional and technical boilerplate, preserving genuine landmark & location
    p1 = re.sub(r"\b(?:UNESCO-protected|UNESCO World Heritage|UNESCO heritage|Cultural Landscape)\b,?", "", p1, flags=re.IGNORECASE)
    p1 = re.sub(r"(?:Original\s+)?fine\s+art\s+photography\s+by\s+[^.]*\.?", "", p1, flags=re.IGNORECASE).strip()
    p1 = re.sub(r"Available\s+in\s+various\s+sizes\s+and\s+finishes[^.]*\.?", "", p1, flags=re.IGNORECASE).strip()
    p1 = re.sub(r"\s+(?:in|at|across|of)\s*[\.,;]", ".", p1)
    p1 = re.sub(r"\s{2,}", " ", p1).strip()
    
    # First poetic sentence from p1 describing scene and location
    s1_match = re.search(r"^([^.!?]+[.!?])", p1)
    s1 = s1_match.group(1).strip() if s1_match else p1
    
    # Extract interior & emotional feeling from p2
    s2 = ""
    if p2:
        match_brings = re.search(r"((?:This\s+[^.]*|It\s+[^.]*)?(?:brings|harmonizes|infuses|creates|fosters|inspires)[^.!?]+[.!?])", p2, flags=re.IGNORECASE)
        if match_brings:
            s2 = match_brings.group(1).strip()
            s2 = re.sub(r"^This\s+[^.]*?\s+(?=brings|pairs|harmonizes|infuses|creates|fosters|inspires)", "", s2, flags=re.IGNORECASE)
            s2 = s2[0].upper() + s2[1:] if s2 else ""
            
    if not s2 and len(s1) < 80:
        s2 = "Brings peaceful balance, timeless harmony, and refined beauty to your wall decor."
        
    combined = f"{s1} {s2}".strip()
    if len(combined) <= max_chars:
        return combined
        
    # If too long, use standard refined interior tail
    short_tail = "Brings serene harmony and timeless elegance to living room decor."
    if len(f"{s1} {short_tail}") <= max_chars:
        return f"{s1} {short_tail}"
        
    trimmed_s1 = s1[:(max_chars - len(short_tail) - 2)].rsplit(" ", 1)[0].rstrip(",;:- ") + "."
    if len(f"{trimmed_s1} {short_tail}") <= max_chars:
        return f"{trimmed_s1} {short_tail}"
        
    return combined[:max_chars].rsplit(" ", 1)[0].rstrip(",;:- ") + "."


def filter_redbubble_tags(tags_list: list, require_multiword: bool = False) -> list:
    """
    Filter and sanitize tags according to Redbubble 2026 guidelines.
    Returns up to 15 tags where the first tag serves as the primary 'Main Tag'.
    - Sanitizes trademarks and brand names.
    - Strips banned spam tags ('best selling', 'trending', 'top selling', 'cheap', 'viral', 'discount', 'gift').
    - If require_multiword=True, ensures 2 to 5 words per tag, rejecting single-word tags (banning 'art', 'photo', 'funny', 'poster', etc.).
    """
    forbidden_exact = {
        "art", "artwork", "image", "photo", "photography", "poster", "print", "prints",
        "funny", "t-shirt", "tshirt", "shirt", "sticker", "stickers", "case", "mug", "hoodie",
        "trending", "best selling", "top selling", "bestseller", "popular", "hot sale", "cheap",
        "viral", "discount", "free shipping", "gift", "gifts", "gift idea", "unesco heritage", "unesco world heritage"
    }
    banned_spam_substrings = (
        "best selling", "trending", "top selling", "cheap", "viral", "discount"
    )
    if isinstance(tags_list, str):
        tags_list = [t.strip() for t in tags_list.split(",") if t.strip()]
    elif not isinstance(tags_list, (list, tuple, set)):
        tags_list = []

    clean = []
    seen = set()
    for raw in tags_list:
        raw_sanitized = sanitize_redbubble_trademarks(str(raw))
        tag = raw_sanitized.strip().lower()
        tag = re.sub(r"[^\w\s-]", "", tag).strip()
        if not tag or len(tag) > 60 or tag in seen:
            continue
        if tag in forbidden_exact:
            continue
        if any(spam in tag for spam in banned_spam_substrings):
            continue
        # Strict multi-word check (2 to 5 words)
        word_count = len(tag.split())
        if require_multiword and (word_count < 2 or word_count > 5):
            continue
        clean.append(tag)
        seen.add(tag)
        if len(clean) >= 15:
            break
            
    return clean


def split_redbubble_tags(tags: any, trailing_comma: bool = True) -> tuple:
    """
    Split tags into (main_tag, supporting_tags_str) with automatic trailing commas
    for instant chip creation in Redbubble uploader.
    """
    if isinstance(tags, str):
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    elif isinstance(tags, (list, tuple)):
        tag_list = list(tags)
    else:
        tag_list = []
        
    if not tag_list:
        return "", ""
    main_tag = tag_list[0]
    supporting_tags = ", ".join(tag_list[1:])
    
    if trailing_comma:
        if main_tag and not main_tag.endswith(","):
            main_tag = f"{main_tag},"
        if supporting_tags and not supporting_tags.endswith(","):
            supporting_tags = f"{supporting_tags},"
            
    return main_tag, supporting_tags


def adapt_art_heroes_to_redbubble(title: str, description: str, keywords: any, profile: str = "wall_art") -> dict:
    """
    Transforms Art Heroes metadata into Redbubble metadata deterministically.
    Strictly adheres to: 4-8 words title, <=245 chars story description, 1 Main Tag + supporting tags.
    """
    clean_t = clean_redbubble_title(title or "")
    clean_d = clean_redbubble_description(description or "", max_chars=245)
    
    raw_kw = keywords
    if isinstance(raw_kw, str):
        raw_kw = [k.strip() for k in raw_kw.split(",") if k.strip()]
    elif not isinstance(raw_kw, (list, tuple)):
        raw_kw = []
        
    clean_tags = filter_redbubble_tags(raw_kw)
    return {
        "title": clean_t,
        "description": clean_d,
        "tags": clean_tags,
        "profile": profile
    }


def parse_response_json(raw_text, target="Both", is_ai_generated=False):
    """Parse JSON and normalize based on target platform, sanitizing attributions for AI content."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    data = json.loads(text)

    if target == "ArtHeroes":
        kws = data.get("keywords", [])
        if isinstance(kws, str):
            kws = [k.strip() for k in kws.split(",") if k.strip()]
        desc = data.get("description", "")
        if is_ai_generated:
            desc = strip_ai_photo_attributions(desc)
            kws = filter_ai_keywords(kws)
        return {
            "artheroes": {
                "title": data.get("title"),
                "description": desc,
                "keywords": kws
            }
        }

    if target == "Displate":
        tags = data.get("tags") or data.get("displate_tags") or data.get("keywords", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        desc = data.get("description") or data.get("displate_description") or ""
        if is_ai_generated:
            desc = strip_ai_photo_attributions(desc)
            tags = filter_ai_keywords(tags)
        return {
            "displate": {
                "title": data.get("title") or data.get("displate_title"),
                "description": desc,
                "tags": tags
            }
        }

    if target in ("Redbubble", "Redbubble_WallArt", "Redbubble_Merch", "Redbubble (Wall Art)", "Redbubble (Merch)", "Merch"):
        rb_data = data.get("redbubble") if isinstance(data.get("redbubble"), dict) else data
        
        # Tags extraction: support comma-separated string, list of strings, or legacy main_tag+supporting_tags
        tags = []
        main_t = rb_data.get("main_tag")
        supp_t = rb_data.get("supporting_tags")
        if main_t or supp_t:
            if main_t and isinstance(main_t, str) and main_t.strip():
                tags.append(main_t.strip())
            if isinstance(supp_t, list):
                tags.extend([str(k).strip() for k in supp_t if str(k).strip()])
            elif isinstance(supp_t, str):
                tags.extend([k.strip() for k in supp_t.split(",") if k.strip()])
                
        if not tags:
            raw_tags = rb_data.get("tags") or rb_data.get("redbubble_tags") or rb_data.get("keywords", [])
            if isinstance(raw_tags, str):
                tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
            elif isinstance(raw_tags, list):
                tags = [str(t).strip() for t in raw_tags if str(t).strip()]
                
        clean_tags = filter_redbubble_tags(tags, require_multiword=False)
        # If there are plenty of multi-word tags (>= 6), enforce 2-5 words strictly per 2026 rule
        multiword_tags = [t for t in clean_tags if 2 <= len(t.split()) <= 5]
        if len(multiword_tags) >= 6:
            clean_tags = multiword_tags[:15]
        else:
            clean_tags = clean_tags[:15]
        
        desc = rb_data.get("description") or rb_data.get("redbubble_description") or ""
        clean_desc = normalize_redbubble_description(desc, is_ai=is_ai_generated)
        
        raw_title = rb_data.get("title") or rb_data.get("redbubble_title") or ""
        clean_t = normalize_redbubble_title(raw_title)
        
        # Primary product detection
        primary_prod = rb_data.get("primary_product") or rb_data.get("profile") or ""
        if primary_prod:
            prod_lower = str(primary_prod).lower()
            if any(k in prod_lower for k in ("wall", "art", "canvas", "poster", "print")):
                profile = "wall_art"
                normalized_product = "Wall Art"
            elif any(k in prod_lower for k in ("sticker", "t-shirt", "shirt", "apparel", "merch")):
                profile = "merch"
                normalized_product = "Sticker" if "sticker" in prod_lower else "T-Shirt"
            else:
                profile = "merch" if "merch" in target.lower() else "wall_art"
                normalized_product = "Wall Art" if profile == "wall_art" else "T-Shirt"
        else:
            profile = "merch" if "merch" in target.lower() else "wall_art"
            normalized_product = "Wall Art" if profile == "wall_art" else "T-Shirt"

        return {
            "redbubble": {
                "title": clean_t,
                "description": clean_desc,
                "tags": clean_tags,
                "profile": profile,
                "primary_product": normalized_product
            }
        }

    if target in ("Stock", "Microstock"):
        result = {}
        # Parse Adobe Stock Hybrid if present
        if "adobe" in data and isinstance(data.get("adobe"), dict):
            adb = data["adobe"]
            adb_kws = adb.get("keywords", [])
            if isinstance(adb_kws, str):
                adb_kws = [k.strip() for k in adb_kws.split(",") if k.strip()]
            adb_desc = adb.get("description") or adb.get("stock_description") or ""
            if is_ai_generated:
                adb_desc = strip_ai_photo_attributions(adb_desc)
                adb_kws = filter_ai_keywords(adb_kws)
            result["adobe"] = {
                "title": adb.get("title") or adb.get("adobe_title"),
                "description": adb_desc,
                "keywords": adb_kws,
                "category": adb.get("category") or "Travel"
            }

        # Parse General Microstock
        stock_data = data.get("stock") if isinstance(data.get("stock"), dict) else data
        kws = stock_data.get("keywords", [])
        if isinstance(kws, str):
            kws = [k.strip() for k in kws.split(",") if k.strip()]
        desc = stock_data.get("description") or stock_data.get("stock_description") or ""
        if is_ai_generated:
            desc = strip_ai_photo_attributions(desc)
            kws = filter_ai_keywords(kws)
        stk_cat = stock_data.get("category") or stock_data.get("stock_category", "Travel")
        raw_sh = stock_data.get("shutterstock_categories")
        from dashboard.stock_metadata import map_to_shutterstock_categories
        sh_cats = map_to_shutterstock_categories(
            raw_sh or stk_cat,
            title=stock_data.get("title") or stock_data.get("stock_title") or "",
            description=desc,
            keywords=kws
        )
        result["stock"] = {
            "title": stock_data.get("title") or stock_data.get("stock_title"),
            "description": desc,
            "keywords": kws,
            "category": stk_cat,
            "shutterstock_categories": sh_cats
        }
        return result

    if target in ("All", "ALL"):
        ah = data.get("artheroes", {})
        disp = data.get("displate", {})
        stk = data.get("stock", {})
        adb = data.get("adobe", {})

        if isinstance(ah.get("keywords"), str):
            ah["keywords"] = [k.strip() for k in ah["keywords"].split(",") if k.strip()]
        if isinstance(disp.get("tags"), str):
            disp["tags"] = [k.strip() for k in disp["tags"].split(",") if k.strip()]
        if isinstance(stk.get("keywords"), str):
            stk["keywords"] = [k.strip() for k in stk["keywords"].split(",") if k.strip()]
        if isinstance(adb.get("keywords"), str):
            adb["keywords"] = [k.strip() for k in adb["keywords"].split(",") if k.strip()]

        if is_ai_generated:
            if "description" in ah:
                ah["description"] = strip_ai_photo_attributions(ah["description"])
            if "description" in disp:
                disp["description"] = strip_ai_photo_attributions(disp["description"])
            if "description" in stk:
                stk["description"] = strip_ai_photo_attributions(stk["description"])
            if "description" in adb:
                adb["description"] = strip_ai_photo_attributions(adb["description"])
            if "keywords" in ah:
                ah["keywords"] = filter_ai_keywords(ah["keywords"])
            if "tags" in disp:
                disp["tags"] = filter_ai_keywords(disp["tags"])
            if "keywords" in stk:
                stk["keywords"] = filter_ai_keywords(stk["keywords"])
            if "keywords" in adb:
                adb["keywords"] = filter_ai_keywords(adb["keywords"])

        if stk:
            stk_cat = stk.get("category") or stk.get("stock_category", "Travel")
            from dashboard.stock_metadata import map_to_shutterstock_categories
            stk["shutterstock_categories"] = map_to_shutterstock_categories(
                stk.get("shutterstock_categories") or stk_cat,
                title=stk.get("title") or "",
                description=stk.get("description") or "",
                keywords=stk.get("keywords") or []
            )

        res_all = {
            "artheroes": ah,
            "displate": disp,
            "stock": stk
        }
        if adb:
            res_all["adobe"] = adb
        if ah and ah.get("title"):
            res_all["redbubble"] = adapt_art_heroes_to_redbubble(
                ah.get("title", ""),
                ah.get("description", ""),
                ah.get("keywords", []),
                profile="wall_art"
            )
        return res_all

    # Target is "Both" (ArtHeroes + Displate)
    artheroes = data.get("artheroes", {})
    displate = data.get("displate", {})

    if not artheroes and "title" in data:
        artheroes = {
            "title": data.get("title"),
            "description": data.get("description"),
            "keywords": data.get("keywords", [])
        }
    if not displate and "displate_title" in data:
        displate = {
            "title": data.get("displate_title"),
            "description": data.get("displate_description"),
            "tags": data.get("displate_tags", [])
        }

    if isinstance(artheroes.get("keywords"), str):
        artheroes["keywords"] = [k.strip() for k in artheroes["keywords"].split(",") if k.strip()]
    if isinstance(displate.get("tags"), str):
        displate["tags"] = [k.strip() for k in displate["tags"].split(",") if k.strip()]

    if is_ai_generated:
        if "description" in artheroes:
            artheroes["description"] = strip_ai_photo_attributions(artheroes["description"])
        if "description" in displate:
            displate["description"] = strip_ai_photo_attributions(displate["description"])
        if "keywords" in artheroes:
            artheroes["keywords"] = filter_ai_keywords(artheroes["keywords"])
        if "tags" in displate:
            displate["tags"] = filter_ai_keywords(displate["tags"])

    return {
        "artheroes": artheroes,
        "displate": displate
    }


def get_prompt_for_target(target, description, user_context="", is_editorial=False, is_ai_generated=False, is_infrared=False, is_surreal=False, is_adobe_hybrid=False, **kwargs):
    hybrid_active = is_hybrid_requested(user_context=user_context, flag_value=is_adobe_hybrid or kwargs.get("is_adobe_hybrid", False))

    if is_ai_generated:
        attribution_instruction = "Do NOT append any creator or artist attribution tagline (such as 'Original photography by...', 'Digital artwork by...', or 'Created by...'). Simply conclude the narrative naturally with the visual or interior styling advice."
        ai_instruction_rule = """
CRITICAL MEDIUM CONSTRAINT (AI GENERATED CONTENT):
- This visual asset is AI GENERATED (generative AI digital artwork / illustration).
- STRICT PROHIBITION: DO NOT use the terms 'photography', 'photograph', 'camera', 'lens', 'shutter', 'shot on', 'photo', or 'DSLR' anywhere in titles, descriptions, or keywords!
- STRICT PROHIBITION: DO NOT add any creator tagline like 'Original photography by...', 'Digital artwork created by...', 'Created by Angelus H.' or any creator credits! Simply conclude the narrative naturally.
- Refer to the work strictly as 'fine art digital artwork', 'digital illustration', 'artistic composition', or 'fine art print'.
- Keywords MUST EXCLUDE photography terms ('fine art photography', 'camera', 'photo').
- Keywords MUST INCLUDE digital art terms: 'digital artwork, generative ai, illustration, concept art, artistic print, digital art'.
"""
    else:
        attribution_instruction = "Conclude the final sentence strictly with: 'Original fine art photography by Angelus H.'"
        ai_instruction_rule = ""

    if is_editorial:
        editorial_instruction = "EDITORIAL USE ONLY. Scene features a specific historical artifact, real branded railway locomotive, landmark, or event."
        editorial_desc_rule = "MANDATORY EDITORIAL FORMAT: Strictly begin with 'CITY, COUNTRY - MONTH YEAR: ' in all caps followed by factual caption (e.g. 'BUDAPEST, HUNGARY - MAY 2024: Vintage electric locomotive...'). Do not use commercial marketing phrases."
    else:
        editorial_instruction = "COMMERCIAL STOCK. Clean commercial metadata."
        editorial_desc_rule = "Clear, factual description explaining the scene, subject, lighting, and potential commercial uses."

    if target == "ArtHeroes":
        base = ART_HEROES_PROMPT_TEMPLATE.format(description=description, attribution_instruction=attribution_instruction)
    elif target == "Displate":
        base = DISPLATE_PROMPT_TEMPLATE.format(description=description, attribution_instruction=attribution_instruction)
    elif target == "Redbubble":
        base = REDBUBBLE_2026_SEO_PROMPT_TEMPLATE.format(description=description)
    elif target in ("Redbubble_WallArt", "Redbubble (Wall Art)"):
        base = REDBUBBLE_WALLART_PROMPT_TEMPLATE.format(description=description)
    elif target in ("Redbubble_Merch", "Redbubble (Merch)", "Merch"):
        base = REDBUBBLE_MERCH_PROMPT_TEMPLATE.format(description=description)
    elif target in ("Stock", "Microstock"):
        if hybrid_active:
            base = ADOBE_HYBRID_STOCK_PROMPT_TEMPLATE.format(
                description=description,
                editorial_instruction=editorial_instruction,
                editorial_desc_rule=editorial_desc_rule
            )
        else:
            base = STOCK_PROMPT_TEMPLATE.format(
                description=description,
                editorial_instruction=editorial_instruction,
                editorial_desc_rule=editorial_desc_rule
            )
    elif target in ("All", "ALL"):
        if hybrid_active:
            base = ALL_PLATFORMS_HYBRID_PROMPT_TEMPLATE.format(
                description=description,
                editorial_instruction=editorial_instruction,
                editorial_desc_rule=editorial_desc_rule,
                attribution_instruction=attribution_instruction
            )
        else:
            base = ALL_PLATFORMS_PROMPT_TEMPLATE.format(
                description=description,
                editorial_instruction=editorial_instruction,
                editorial_desc_rule=editorial_desc_rule,
                attribution_instruction=attribution_instruction
            )
    else:
        base = COMBINED_PROMPT_TEMPLATE.format(description=description, attribution_instruction=attribution_instruction)

    # Append style and medium directives
    directives = []
    if ai_instruction_rule:
        directives.append(ai_instruction_rule.strip())

    if is_infrared:
        directives.append("""
INFRARED AESTHETIC DIRECTIVE (IR / 720nm / Wood Effect):
- The scene features the ethereal beauty of infrared light: glowing ethereal white/silver foliage, dramatic high-contrast dark skies, and surreal luminous atmosphere.
- CRITICAL: Never mistake or describe infrared glowing white foliage as winter snow or frost!
- Keywords must include: 'infrared photography, 720nm, wood effect, ir photo, glowing foliage, infrared landscape'.
""".strip())

    if is_surreal:
        directives.append("""
SURREAL & CONCEPTUAL STYLE DIRECTIVE:
- Emphasize dreamlike, otherworldly, metaphysical, imaginative, and mysterious qualities.
- Evoke poetic wonder and cosmic transcendence.
- Keywords must include: 'surreal, surrealism, dreamlike, otherworldly, conceptual art, fantasy, ethereal'.
""".strip())

    if directives:
        base += "\n\n" + "\n\n".join(directives)

    if user_context and user_context.strip():
        base += f"""

CRITICAL PHOTOGRAPHER / ARTIST CONTEXT:
{user_context.strip()}

MANDATORY INSTRUCTIONS REGARDING CONTEXT:
1. Seamlessly integrate the specific subject, theme, characters, landmarks, or technique from the context into the titles, descriptions, and keywords/tags.
2. If the context specifies a subject or theme (e.g. 'linux engineer', 'cyberpunk samurai', 'coffee lover'), make it the core focus of the title, narrative story, and search tags.
3. If geographic location or landmark details are provided, accurately feature them; otherwise focus on the depicted subject, character, or theme.
"""
    return base


def generate_with_ollama(image_path, target="Both", vision_model="llava:7b", copy_model="llama3.2:latest", user_context="", is_editorial=False, is_ai_generated=False, is_infrared=False, is_surreal=False, is_adobe_hybrid=False, **kwargs):
    """Two-stage local pipeline: Vision describe -> Copywrite structured JSON."""
    visual_desc = get_local_vision_description(image_path, vision_model=vision_model, user_context=user_context)
    prompt = get_prompt_for_target(
        target, visual_desc, user_context=user_context,
        is_editorial=is_editorial, is_ai_generated=is_ai_generated,
        is_infrared=is_infrared, is_surreal=is_surreal,
        is_adobe_hybrid=is_adobe_hybrid, **kwargs
    )
    
    payload = {
        "model": copy_model,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    resp = requests.post(OLLAMA_API_URL, json=payload, timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(f"Ollama Copywriter error ({resp.status_code}): {resp.text}")
    
    raw = resp.json().get("response", "")
    return parse_response_json(raw, target=target, is_ai_generated=is_ai_generated)


def generate_with_gemini(image_path, target="Both", api_key=None, user_context="", is_editorial=False, is_ai_generated=False, is_infrared=False, is_surreal=False, is_adobe_hybrid=False, **kwargs):
    """Call Google Gemini Flash cloud API."""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY is not set.")

    art_label = "the provided AI digital artwork" if is_ai_generated else "the provided photograph"
    system_prompt = get_prompt_for_target(
        target, art_label, user_context=user_context,
        is_editorial=is_editorial, is_ai_generated=is_ai_generated,
        is_infrared=is_infrared, is_surreal=is_surreal,
        is_adobe_hybrid=is_adobe_hybrid, **kwargs
    )
    image_b64 = encode_thumbnail_base64(image_path, max_dim=768)

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": system_prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_b64
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "response_mime_type": "application/json"
        }
    }

    url = f"{GEMINI_API_URL}?key={key}"
    resp = requests.post(url, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API Error ({resp.status_code}): {resp.text}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        feedback = data.get("promptFeedback", {})
        raise RuntimeError(f"Gemini API returned no candidates. Prompt feedback: {feedback}")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts or "text" not in parts[0]:
        raise RuntimeError(f"Gemini API candidate contained no text: {candidates[0]}")
    raw_text = parts[0]["text"]
    return parse_response_json(raw_text, target=target, is_ai_generated=is_ai_generated)


def generate_metadata(image_path, target="Both", engine="Google Gemini Cloud (~$0.002/img)", api_key=None, user_context="", is_editorial=False, is_ai_generated=False, is_infrared=False, is_surreal=False, is_adobe_hybrid=False, **kwargs):
    """Router for local vs cloud generation."""
    if "Ollama" in engine:
        return generate_with_ollama(
            image_path, target=target, user_context=user_context,
            is_editorial=is_editorial, is_ai_generated=is_ai_generated,
            is_infrared=is_infrared, is_surreal=is_surreal,
            is_adobe_hybrid=is_adobe_hybrid, **kwargs
        )
    else:
        return generate_with_gemini(
            image_path, target=target, api_key=api_key, user_context=user_context,
            is_editorial=is_editorial, is_ai_generated=is_ai_generated,
            is_infrared=is_infrared, is_surreal=is_surreal,
            is_adobe_hybrid=is_adobe_hybrid, **kwargs
        )
