from fastapi import APIRouter, HTTPException
import json, os, requests, time, uuid
from datetime import datetime

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

def get_ig_config():
    settings = load_settings()
    fb = settings.get("facebook", {})
    ig = settings.get("instagram", {})
    token = fb.get("access_token", "")
    account_id = ig.get("account_id", "")
    max_hashtags = int(ig.get("max_hashtags", 5))
    return token, account_id, max_hashtags

@router.get("/auth/status")
async def auth_status():
    token, account_id, _ = get_ig_config()
    if not token or not account_id:
        return {"connected": False}
    resp = requests.get(
        f"https://graph.facebook.com/v18.0/{account_id}?fields=name,username&access_token={token}"
    )
    data = resp.json()
    return {"connected": resp.status_code == 200, "username": data.get("username", "") if resp.status_code == 200 else ""}

@router.post("/upload")
async def upload_to_instagram(data: dict):
    token, account_id, max_hashtags = get_ig_config()
    if not token or not account_id:
        raise HTTPException(401, "Instagram not configured. Add Account ID in Settings.")
    
    video_path = data.get("video_path", "").lstrip("/")
    title = data.get("title", "My Reel")
    hashtags = data.get("hashtags", [])[:max_hashtags]
    thumbnail_path = data.get("thumbnail_path", "")
    video_url = data.get("video_url", "")  # Instagram requires publicly accessible URL
    
    if not video_url:
        raise HTTPException(400, "Instagram requires a publicly accessible video URL. Use ngrok or a server URL.")
    
    caption = title
    if hashtags:
        caption += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)
    
    try:
        # Step 1: Create media container
        container_data = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": token
        }
        
        if thumbnail_path:
            thumb_path = thumbnail_path.lstrip("/")
            if os.path.exists(thumb_path):
                container_data["thumb_offset"] = "0"
        
        container_resp = requests.post(
            f"https://graph.facebook.com/v18.0/{account_id}/media",
            data=container_data
        )
        container = container_resp.json()
        
        if "error" in container:
            raise HTTPException(500, f"Instagram container creation failed: {container['error']['message']}")
        
        container_id = container.get("id")
        if not container_id:
            raise HTTPException(500, "Failed to create Instagram media container")
        
        # Step 2: Poll for processing status
        max_attempts = 30
        for attempt in range(max_attempts):
            status_resp = requests.get(
                f"https://graph.facebook.com/v18.0/{container_id}?fields=status_code,status&access_token={token}"
            )
            status_data = status_resp.json()
            status_code = status_data.get("status_code", "")
            
            if status_code == "FINISHED":
                break
            elif status_code == "ERROR":
                raise HTTPException(500, f"Instagram processing error: {status_data.get('status', 'Unknown')}")
            
            time.sleep(5)
        else:
            raise HTTPException(500, "Instagram video processing timed out")
        
        # Step 3: Publish
        publish_resp = requests.post(
            f"https://graph.facebook.com/v18.0/{account_id}/media_publish",
            data={"creation_id": container_id, "access_token": token}
        )
        publish_data = publish_resp.json()
        
        if "error" in publish_data:
            raise HTTPException(500, f"Instagram publish failed: {publish_data['error']['message']}")
        
        media_id = publish_data.get("id")
        add_history("instagram", title, "success", video_path)
        return {"success": True, "media_id": media_id, "url": f"https://www.instagram.com/p/{media_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        add_history("instagram", title, "failed", video_path, error_msg)
        raise HTTPException(500, f"Instagram upload error: {error_msg}")

@router.get("/accounts")
async def get_accounts():
    """Get Instagram accounts connected to Facebook pages"""
    settings = load_settings()
    token = settings.get("facebook", {}).get("access_token", "")
    if not token:
        raise HTTPException(401, "No Facebook access token configured")
    
    pages_resp = requests.get(f"https://graph.facebook.com/v18.0/me/accounts?access_token={token}")
    pages_data = pages_resp.json()
    
    accounts = []
    for page in pages_data.get("data", []):
        page_id = page["id"]
        page_token = page.get("access_token", token)
        ig_resp = requests.get(
            f"https://graph.facebook.com/v18.0/{page_id}?fields=instagram_business_account&access_token={page_token}"
        )
        ig_data = ig_resp.json()
        ig_account = ig_data.get("instagram_business_account")
        if ig_account:
            ig_info_resp = requests.get(
                f"https://graph.facebook.com/v18.0/{ig_account['id']}?fields=name,username&access_token={page_token}"
            )
            ig_info = ig_info_resp.json()
            accounts.append({
                "id": ig_account["id"],
                "username": ig_info.get("username", ""),
                "name": ig_info.get("name", ""),
                "page_name": page["name"]
            })
    
    return {"accounts": accounts}
