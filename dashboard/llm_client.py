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

    if target in ("Stock", "Microstock"):
        stock_data = data.get("stock") if isinstance(data.get("stock"), dict) else data
        kws = stock_data.get("keywords", [])
        if isinstance(kws, str):
            kws = [k.strip() for k in kws.split(",") if k.strip()]
        desc = stock_data.get("description") or stock_data.get("stock_description") or ""
        if is_ai_generated:
            desc = strip_ai_photo_attributions(desc)
            kws = filter_ai_keywords(kws)
        return {
            "stock": {
                "title": stock_data.get("title") or stock_data.get("stock_title"),
                "description": desc,
                "keywords": kws,
                "category": stock_data.get("category") or stock_data.get("stock_category", "Travel")
            }
        }

    if target in ("All", "ALL"):
        ah = data.get("artheroes", {})
        disp = data.get("displate", {})
        stk = data.get("stock", {})

        if isinstance(ah.get("keywords"), str):
            ah["keywords"] = [k.strip() for k in ah["keywords"].split(",") if k.strip()]
        if isinstance(disp.get("tags"), str):
            disp["tags"] = [k.strip() for k in disp["tags"].split(",") if k.strip()]
        if isinstance(stk.get("keywords"), str):
            stk["keywords"] = [k.strip() for k in stk["keywords"].split(",") if k.strip()]

        if is_ai_generated:
            if "description" in ah:
                ah["description"] = strip_ai_photo_attributions(ah["description"])
            if "description" in disp:
                disp["description"] = strip_ai_photo_attributions(disp["description"])
            if "description" in stk:
                stk["description"] = strip_ai_photo_attributions(stk["description"])
            if "keywords" in ah:
                ah["keywords"] = filter_ai_keywords(ah["keywords"])
            if "tags" in disp:
                disp["tags"] = filter_ai_keywords(disp["tags"])
            if "keywords" in stk:
                stk["keywords"] = filter_ai_keywords(stk["keywords"])

        return {
            "artheroes": ah,
            "displate": disp,
            "stock": stk
        }

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


def get_prompt_for_target(target, description, user_context="", is_editorial=False, is_ai_generated=False, is_infrared=False, is_surreal=False, **kwargs):
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
    elif target in ("Stock", "Microstock"):
        base = STOCK_PROMPT_TEMPLATE.format(
            description=description,
            editorial_instruction=editorial_instruction,
            editorial_desc_rule=editorial_desc_rule
        )
    elif target in ("All", "ALL"):
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
1. Seamlessly integrate the specific location, landmarks, technique, and subject into the titles, descriptions, and keywords/tags.
2. Ensure the exact geographic location and landmarks (e.g. castle, park, lake, city, country) are accurately featured in the title, story, and tags.
"""
    return base


def generate_with_ollama(image_path, target="Both", vision_model="llava:7b", copy_model="llama3.2:latest", user_context="", is_editorial=False, is_ai_generated=False, is_infrared=False, is_surreal=False, **kwargs):
    """Two-stage local pipeline: Vision describe -> Copywrite structured JSON."""
    visual_desc = get_local_vision_description(image_path, vision_model=vision_model, user_context=user_context)
    prompt = get_prompt_for_target(
        target, visual_desc, user_context=user_context,
        is_editorial=is_editorial, is_ai_generated=is_ai_generated,
        is_infrared=is_infrared, is_surreal=is_surreal
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


def generate_with_gemini(image_path, target="Both", api_key=None, user_context="", is_editorial=False, is_ai_generated=False, is_infrared=False, is_surreal=False, **kwargs):
    """Call Google Gemini Flash cloud API."""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY is not set.")

    art_label = "the provided AI digital artwork" if is_ai_generated else "the provided photograph"
    system_prompt = get_prompt_for_target(
        target, art_label, user_context=user_context,
        is_editorial=is_editorial, is_ai_generated=is_ai_generated,
        is_infrared=is_infrared, is_surreal=is_surreal
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


def generate_metadata(image_path, target="Both", engine="Google Gemini Cloud (~$0.002/img)", api_key=None, user_context="", is_editorial=False, is_ai_generated=False, is_infrared=False, is_surreal=False, **kwargs):
    """Router for local vs cloud generation."""
    if "Ollama" in engine:
        return generate_with_ollama(
            image_path, target=target, user_context=user_context,
            is_editorial=is_editorial, is_ai_generated=is_ai_generated,
            is_infrared=is_infrared, is_surreal=is_surreal, **kwargs
        )
    else:
        return generate_with_gemini(
            image_path, target=target, api_key=api_key, user_context=user_context,
            is_editorial=is_editorial, is_ai_generated=is_ai_generated,
            is_infrared=is_infrared, is_surreal=is_surreal, **kwargs
        )
