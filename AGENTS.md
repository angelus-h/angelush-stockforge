# AI Agent Instructions for StockForge

## Core Operating Rules

### 1. Image Downscaling & Strict Token Efficiency (Cost Optimization)
- **Automatic Downscaling Rule:** Whenever analyzing, inspecting, or processing image files referenced by the user or disk, **NEVER** pass or inspect full-resolution 20-50 Megapixel RAW/JPEG files directly into multimodal LLM prompts.
- **Max Thumbnail Size:** Always extract or generate a compressed preview thumbnail with **maximum dimension of 768px** (using `raw_loader.get_thumbnail_bytes` or `encode_thumbnail_base64(..., max_dim=768)`). This ensures each vision API call uses only ~250 tokens (< $0.0003) instead of tens of thousands of tokens.
- **Reference by Path/Name:** Prefer referencing files by relative path or database ID instead of injecting raw binary data into chat turns.

### 2. Concise & Direct Output
- Prioritize high density of information over conversational filler.
- Never output unnecessary preambles or postambles.

### 3. Safety & Codebase Standards
- Follow conventions defined in `PROJECT_CONTEXT.md` and `REPO_MAP.md`.
- Ensure all user-facing UI and error strings remain strictly in English.
- Verify unit tests after making code modifications (`python -m unittest discover -s tests`).
