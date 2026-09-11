#!/usr/bin/env python3
import os
import json
import base64
from google import genai
from google.genai import types

# Requires google-genai SDK
# pip install google-genai
# Ensure GEMINI_API_KEY environment variable is set.

def get_base64_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def generate_metadata_for_image(image_path, original_title=""):
    client = genai.Client()
    
    # Jenny Rainbow & Matt Payne Hybrid Prompt Strategy
    system_instruction = """
    You are an expert Fine Art America (FAA) SEO specialist and interior design art consultant.
    Your task is to analyze the provided image and generate metadata following the successful strategies of top-selling artists (like Jenny Rainbow and Matt Payne).

    CRITICAL RULES:
    1. TITLE: Must be a long-tail, SEO-optimized title using the formula: [Main Subject/Emotion] + [Light/Mood] + [Location if applicable] + [Interior Decor / Wall Art tag]. Do NOT use numbering (like #1). Max 80 chars.
    2. DESCRIPTION: Must be exactly 3 paragraphs.
       - P1: Emotional storytelling, describing the mood, light, and what makes the scene unique (e.g. ethereal unseen light for infrared, historic charm for castles).
       - P2: Interior design focus. Mention specific rooms (e.g. bedroom, executive office, boutique hotel) and concepts like 'healing art', 'feng shui', or 'calming sanctuary'.
       - P3: Premium quality & trust. Mention museum-grade archival materials, 30-day money-back guarantee, and global shipping by Fine Art America.
    3. TAGS: A list of long-tail and exact-match keywords (e.g. "czech gardens", "healing art prints", "surreal infrared landscape"). Must be ordered by relevance (most important first). The total length of the comma-separated string MUST NOT exceed 480 characters.
    """
    
    b64_image = get_base64_image(image_path)
    
    # Define the strict JSON schema we expect back
    schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "optimized_title": types.Schema(type=types.Type.STRING, description="The SEO and decor optimized title"),
            "description_p1_emotion": types.Schema(type=types.Type.STRING, description="Paragraph 1: Emotion and subject"),
            "description_p2_decor": types.Schema(type=types.Type.STRING, description="Paragraph 2: Interior design and rooms"),
            "description_p3_trust": types.Schema(type=types.Type.STRING, description="Paragraph 3: Printing quality and guarantee"),
            "tags": types.Schema(
                type=types.Type.ARRAY, 
                items=types.Schema(type=types.Type.STRING),
                description="List of highly relevant tags. Most important first."
            )
        },
        required=["optimized_title", "description_p1_emotion", "description_p2_decor", "description_p3_trust", "tags"]
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(data=base64.b64decode(b64_image), mime_type='image/jpeg'),
                f"Analyze this image. The original working title/context is: {original_title}. Generate the metadata."
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.7,
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None

if __name__ == "__main__":
    print("Gemini Flash FAA Metadata Generator Ready.")
    print("Usage: Call generate_metadata_for_image('/path/to/image.jpg', 'Optional original title')")
