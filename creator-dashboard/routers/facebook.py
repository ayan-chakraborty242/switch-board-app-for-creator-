from fastapi import APIRouter, HTTPException
import json, os, requests
from pathlib import Path
from datetime import datetime
import uuid

router = APIRouter()

def load_settings():
    with open("settings.json") as f:
        return json.load(f)

def add_history(platform, title, status, video_path, error=None):
    history = []
    if os.path.exists("upload_history.json"):
        with open("upload_history.json") as f:
            history = json.load(f)
    history.insert(0, {
        "id": str(uuid.uuid4()),
        "platform": platform,
        "title": title,
        "status": status,
        "video": video_path,
        "timestamp": datetime.now().isoformat(),
        "error": error
    })
    history = history[:100]
    with open("upload_history.json", "w") as f:
        json.dump(history, f, indent=2)

def get_fb_config():
    settings = load_settings()
    fb = settings.get("facebook", {})
    token = fb.get("access_token", "")
    page_id = fb.get("page_id", "")
    return token, page_id

@router.get("/auth/status")
async def auth_status():
    token, page_id = get_fb_config()
    if not token or not page_id:
        return {"connected": False}
    # Verify token
    resp = requests.get(f"https://graph.facebook.com/v18.0/me?access_token={token}")
    return {"connected": resp.status_code == 200, "name": resp.json().get("name", "") if resp.status_code == 200 else ""}

@router.post("/upload")
async def upload_to_facebook(data: dict):
    token, page_id = get_fb_config()
    if not token or not page_id:
        raise HTTPException(401, "Facebook not configured. Add Page Access Token and Page ID in Settings.")
    
    video_path = data.get("video_path", "").lstrip("/")
    title = data.get("title", "My Reel")
    hashtags = data.get("hashtags", [])
    thumbnail_path = data.get("thumbnail_path", "")
    
    if not os.path.exists(video_path):
        raise HTTPException(404, "Video file not found")
    
    description = title
    if hashtags:
        description += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)
    
    try:
        # Step 1: Initialize upload session
        init_resp = requests.post(
            f"https://graph.facebook.com/v18.0/{page_id}/video_reels",
            data={"upload_phase": "start", "access_token": token}
        )
        init_data = init_resp.json()
        if "error" in init_data:
            raise HTTPException(500, f"Facebook API error: {init_data['error']['message']}")
        
        video_id = init_data.get("video_id")
        upload_url = init_data.get("upload_url")
        
        if not video_id or not upload_url:
            raise HTTPException(500, "Failed to initialize Facebook upload session")
        
        # Step 2: Upload video bytes
        file_size = os.path.getsize(video_path)
        with open(video_path, "rb") as f:
            upload_resp = requests.post(
                upload_url,
                headers={
                    "Authorization": f"OAuth {token}",
                    "offset": "0",
                    "file_size": str(file_size)
                },
                data=f
            )
        
        if upload_resp.status_code not in (200, 201):
            raise HTTPException(500, f"Facebook video upload failed: {upload_resp.text}")
        
        # Step 3: Finish upload and publish
        finish_data = {
            "upload_phase": "finish",
            "video_id": video_id,
            "access_token": token,
            "title": title,
            "description": description,
            "video_state": "PUBLISHED"
        }
        
        if thumbnail_path:
            thumb_path = thumbnail_path.lstrip("/")
            if os.path.exists(thumb_path):
                with open(thumb_path, "rb") as tf:
                    finish_resp = requests.post(
                        f"https://graph.facebook.com/v18.0/{page_id}/video_reels",
                        data=finish_data,
                        files={"thumb": tf}
                    )
            else:
                finish_resp = requests.post(
                    f"https://graph.facebook.com/v18.0/{page_id}/video_reels",
                    data=finish_data
                )
        else:
            finish_resp = requests.post(
                f"https://graph.facebook.com/v18.0/{page_id}/video_reels",
                data=finish_data
            )
        
        finish_data_resp = finish_resp.json()
        if "error" in finish_data_resp:
            raise HTTPException(500, f"Facebook publish failed: {finish_data_resp['error']['message']}")
        
        add_history("facebook", title, "success", video_path)
        return {"success": True, "video_id": video_id, "url": f"https://www.facebook.com/video/{video_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        add_history("facebook", title, "failed", video_path, error_msg)
        raise HTTPException(500, f"Facebook upload error: {error_msg}")

@router.get("/pages")
async def get_pages():
    """Get list of Facebook pages managed by user"""
    settings = load_settings()
    token = settings.get("facebook", {}).get("access_token", "")
    if not token:
        raise HTTPException(401, "No access token configured")
    
    resp = requests.get(f"https://graph.facebook.com/v18.0/me/accounts?access_token={token}")
    data = resp.json()
    if "error" in data:
        raise HTTPException(400, data["error"]["message"])
    
    pages = [{"id": p["id"], "name": p["name"]} for p in data.get("data", [])]
    return {"pages": pages}
