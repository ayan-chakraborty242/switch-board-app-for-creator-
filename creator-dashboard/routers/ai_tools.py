from fastapi import APIRouter, HTTPException
import json, os, requests

router = APIRouter()

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

def get_api_key():
    # Check settings.json first, then environment variable
    if os.path.exists("settings.json"):
        with open("settings.json") as f:
            settings = json.load(f)
        key = settings.get("general", {}).get("anthropic_api_key", "")
        if key:
            return key
    return os.environ.get("ANTHROPIC_API_KEY", "")

@router.post("/generate")
async def generate_content(data: dict):
    """Generate title, description, hashtags, and YouTube tags based on video context"""
    api_key = get_api_key()
    if not api_key:
        raise HTTPException(400, "Anthropic API key not configured. Add it in Settings.")
    
    context = data.get("context", "")  # User description of video content
    platform_focus = data.get("platform", "all")  # 'youtube', 'facebook', 'instagram', 'all'
    
    if not context:
        raise HTTPException(400, "Please provide a brief description of your video content")
    
    prompt = f"""You are a social media content strategist for short-form video (Reels/Shorts).

Video content description: "{context}"

Generate optimized metadata for this video. Respond ONLY with valid JSON in this exact format, no markdown, no preamble:

{{
  "title": "catchy, hook-driven title under 60 characters",
  "description": "engaging 2-3 sentence description for YouTube",
  "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "youtube_tags": ["seo keyword 1", "seo keyword 2", "seo keyword 3", "seo keyword 4", "seo keyword 5"]
}}

Hashtags should be relevant, trending-style, no # symbol, mix of broad and niche. YouTube tags should be SEO keywords without # symbol."""

    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        
        if response.status_code != 200:
            raise HTTPException(500, f"AI generation failed: {response.text}")
        
        result = response.json()
        text = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        
        text = text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
        text = text.strip()
        
        parsed = json.loads(text)
        return {"success": True, **parsed}
        
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"AI returned invalid format: {str(e)}")
    except requests.RequestException as e:
        raise HTTPException(500, f"AI request failed: {str(e)}")
