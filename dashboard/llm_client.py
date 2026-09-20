"""
Unified AI Client for StockForge.
Supports:
1. Local Ollama (100% Free, Private, $0.00 cost using installed local models like llava, llama3.2, qwen)
2. Direct Google Gemini REST API (~$0.002/image cloud backup)

Supports generating for Art Heroes only, Displate only, or Both platforms simultaneously.
"""

import os
import io
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
   - Para 3: Available finishes (textured canvas, framed prints, sleek acrylic, metal) and conclude with: 'Original fine art photography by Angelus H.'
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
2. 'description': Strictly between 450 and 470 characters in total length (including spaces). High-impact fine art copywriting highlighting luminous contrast on steel metal finish (matte/gloss) and modern wall decor appeal. Conclude with: 'Original fine art photography by Angelus H.'
3. 'tags': Array of up to 20 highly searchable tags (1-2 words each, e.g. fine art, metal print, wall decor, landscape, architecture, modern art).

Output exclusively valid JSON:
{{
  "title": "...",
  "description": "Engaging description strictly 450-470 characters long concluding with Original fine art photography by Angelus H.",
  "tags": ["fine art", "metal print", "wall decor", "infrared photography", "720nm", "wood effect", "lednice valtice", "czech republic", "medieval castle", "castle ruin", "landscape photography", "pentax kr", "architectural art", "dramatic sky", "glowing foliage", "modern art", "living room decor", "travel photography", "heritage site", "metal poster"]
}}"""

COMBINED_PROMPT_TEMPLATE = """You are an elite Print-on-Demand (POD) fine art copywriter specializing in Art Heroes (European interior design) and Displate (metal posters).
Visual Scene Description: {description}

Produce high-converting fine art metadata adhering strictly to the respective guidelines for both platforms.

1. ART HEROES RULES:
- 'title': [Emotional Mood] + [Core Subject] + [Explicit Room/Styling Suggestion]
- 'description': Strictly 3 cohesive paragraphs separated by double newlines:
  * Para 1: Atmospheric visual storytelling, lighting, mood, season.
  * Para 2: Specific interior room recommendations (Living Room, Bedroom, Kitchen, etc.) and matching styles (Scandinavian, Modern Rustic, Contemporary).
  * Para 3: Available finishes (textured canvas, framed prints, sleek acrylic, metal) and conclude with: 'Original fine art photography by Angelus H.'
- 'keywords': Array of strictly 12 high-relevance search tags.

2. DISPLATE RULES:
- 'displate_title': Punchy, evocative, fine art metal poster title under 60 characters.
- 'displate_description': Strictly between 450 and 470 characters in total length (including spaces). Highlight luminous contrast on steel metal finish and modern wall decor appeal. Conclude with: 'Original fine art photography by Angelus H.'
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
    "description": "Engaging description strictly 450-470 characters long concluding with Original fine art photography by Angelus H.",
    "tags": ["fine art", "metal print", "wall decor", "infrared photography", "720nm", "wood effect", "lednice valtice", "czech republic", "medieval castle", "castle ruin", "landscape photography", "pentax kr", "architectural art", "dramatic sky", "glowing foliage", "modern art", "living room decor", "travel photography", "heritage site", "metal poster"]
  }}
}}"""


def encode_thumbnail_base64(image_path, max_dim=512):
    """Resize image to max_dim and return base64 string."""
    with Image.open(image_path) as img:
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


def parse_response_json(raw_text, target="Both"):
    """Parse JSON and normalize based on target platform."""
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
        return {
            "artheroes": {
                "title": data.get("title"),
                "description": data.get("description"),
                "keywords": kws
            }
        }

    if target == "Displate":
        tags = data.get("tags") or data.get("displate_tags") or data.get("keywords", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        return {
            "displate": {
                "title": data.get("title") or data.get("displate_title"),
                "description": data.get("description") or data.get("displate_description"),
                "tags": tags
            }
        }

    # Target is "Both"
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

    return {
        "artheroes": artheroes,
        "displate": displate
    }


def get_prompt_for_target(target, description, user_context=""):
    if target == "ArtHeroes":
        base = ART_HEROES_PROMPT_TEMPLATE.format(description=description)
    elif target == "Displate":
        base = DISPLATE_PROMPT_TEMPLATE.format(description=description)
    else:
        base = COMBINED_PROMPT_TEMPLATE.format(description=description)

    if user_context and user_context.strip():
        base += f"""

CRITICAL PHOTOGRAPHER CONTEXT & TECHNIQUE NOTES:
{user_context.strip()}

MANDATORY INSTRUCTIONS REGARDING CONTEXT:
1. Seamlessly integrate the specific location, landmarks, technique, and camera specifications into the titles, descriptions, and keywords/tags.
2. If infrared photography (IR / 720nm / Wood effect) is mentioned, explicitly describe the dreamlike infrared aesthetic (ethereal glowing foliage, surreal high-contrast skies, silver-white leaves). NEVER confuse infrared white foliage with winter snow or frost!
3. Ensure the exact geographic location and landmarks (e.g. castle, park, lake, city, country) are accurately featured in the title, story, and tags.
"""
    return base


def generate_with_ollama(image_path, target="Both", vision_model="llava:7b", copy_model="llama3.2:latest", user_context=""):
    """Two-stage local pipeline: Vision describe -> Copywrite structured JSON."""
    visual_desc = get_local_vision_description(image_path, vision_model=vision_model, user_context=user_context)
    prompt = get_prompt_for_target(target, visual_desc, user_context=user_context)
    
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
    return parse_response_json(raw, target=target)


def generate_with_gemini(image_path, target="Both", api_key=None, user_context=""):
    """Call Google Gemini Flash cloud API."""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY is not set.")

    system_prompt = get_prompt_for_target(target, "the provided fine art photograph", user_context=user_context)
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
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    return parse_response_json(raw_text, target=target)


def generate_metadata(image_path, target="Both", engine="Local Ollama (100% Free - $0.00)", api_key=None, user_context=""):
    """Router for local vs cloud generation."""
    if "Ollama" in engine:
        return generate_with_ollama(image_path, target=target, user_context=user_context)
    else:
        return generate_with_gemini(image_path, target=target, api_key=api_key, user_context=user_context)
