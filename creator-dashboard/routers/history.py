from fastapi import APIRouter, HTTPException
import json, os, requests
from datetime import datetime

router = APIRouter()

HISTORY_FILE = "upload_history.json"

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE) as f:
        return json.load(f)

@router.get("/list")
async def get_history(limit: int = 50, platform: str = None):
    history = load_history()
    if platform:
        history = [h for h in history if h["platform"] == platform]
    return history[:limit]

@router.delete("/clear")
async def clear_history():
    with open(HISTORY_FILE, "w") as f:
        json.dump([], f)
    return {"success": True}

@router.post("/publish-all")
async def publish_to_all(data: dict):
    """Publish to all selected platforms simultaneously, return per-platform results"""
    platforms = data.get("platforms", ["youtube", "facebook", "instagram"])
    results = {}
    
    if "youtube" in platforms:
        try:
            resp = requests.post("http://localhost:8000/api/youtube/upload", json=data.get("youtube_data", {}), timeout=600)
            results["youtube"] = {"success": resp.status_code == 200, **resp.json()} if resp.status_code == 200 else {"success": False, "error": resp.json().get("detail", "Unknown error")}
        except Exception as e:
            results["youtube"] = {"success": False, "error": str(e)}
    
    if "facebook" in platforms:
        try:
            resp = requests.post("http://localhost:8000/api/facebook/upload", json=data.get("facebook_data", {}), timeout=600)
            results["facebook"] = {"success": resp.status_code == 200, **resp.json()} if resp.status_code == 200 else {"success": False, "error": resp.json().get("detail", "Unknown error")}
        except Exception as e:
            results["facebook"] = {"success": False, "error": str(e)}
    
    if "instagram" in platforms:
        try:
            resp = requests.post("http://localhost:8000/api/instagram/upload", json=data.get("instagram_data", {}), timeout=600)
            results["instagram"] = {"success": resp.status_code == 200, **resp.json()} if resp.status_code == 200 else {"success": False, "error": resp.json().get("detail", "Unknown error")}
        except Exception as e:
            results["instagram"] = {"success": False, "error": str(e)}
    
    return {"results": results}
