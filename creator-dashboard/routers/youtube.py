from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import RedirectResponse
import json, os, requests
from pathlib import Path
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import uuid

router = APIRouter()
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtubepartner"
]

def load_settings():
    with open("settings.json") as f:
        return json.load(f)

def load_tokens():
    if not os.path.exists("oauth_tokens.json"):
        return {}
    with open("oauth_tokens.json") as f:
        return json.load(f)

def save_tokens(tokens):
    with open("oauth_tokens.json", "w") as f:
        json.dump(tokens, f, indent=2)

def get_yt_credentials():
    tokens = load_tokens()
    yt = tokens.get("youtube", {})
    if not yt:
        return None
    creds = Credentials(
        token=yt.get("access_token"),
        refresh_token=yt.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=yt.get("client_id"),
        client_secret=yt.get("client_secret"),
        scopes=SCOPES
    )
    return creds

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

@router.get("/auth/start")
async def auth_start():
    settings = load_settings()
    yt = settings.get("youtube", {})
    if not yt.get("client_id") or not yt.get("client_secret"):
        raise HTTPException(400, "YouTube credentials not configured in Settings")
    
    client_config = {
        "web": {
            "client_id": yt["client_id"],
            "client_secret": yt["client_secret"],
            "redirect_uris": [yt.get("redirect_uri", "http://localhost:8000/auth/youtube/callback")],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = yt.get("redirect_uri", "http://localhost:8000/auth/youtube/callback")
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    return {"auth_url": auth_url}

async def exchange_code(code: str):
    try:
        settings = load_settings()
        yt = settings.get("youtube", {})
        client_config = {
            "web": {
                "client_id": yt["client_id"],
                "client_secret": yt["client_secret"],
                "redirect_uris": [yt.get("redirect_uri", "http://localhost:8000/auth/youtube/callback")],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }
        flow = Flow.from_client_config(client_config, scopes=SCOPES)
        flow.redirect_uri = yt.get("redirect_uri", "http://localhost:8000/auth/youtube/callback")
        flow.fetch_token(code=code)
        creds = flow.credentials
        tokens = load_tokens()
        tokens["youtube"] = {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "client_id": yt["client_id"],
            "client_secret": yt["client_secret"]
        }
        save_tokens(tokens)
        return {"success": True, "message": "YouTube connected successfully!"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.get("/auth/status")
async def auth_status():
    tokens = load_tokens()
    return {"connected": bool(tokens.get("youtube", {}).get("access_token"))}

@router.post("/upload")
async def upload_to_youtube(data: dict):
    creds = get_yt_credentials()
    if not creds:
        raise HTTPException(401, "YouTube not authenticated")
    
    video_path = data.get("video_path", "").lstrip("/")
    title = data.get("title", "My Short")
    description = data.get("description", "")
    tags = data.get("tags", [])
    thumbnail_path = data.get("thumbnail_path", "")
    privacy = data.get("privacy", "public")
    
    if not os.path.exists(video_path):
        raise HTTPException(404, "Video file not found")
    
    try:
        youtube = build("youtube", "v3", credentials=creds)
        
        body = {
            "snippet": {
                "title": title,
                "description": f"{description}\n\n#Shorts",
                "tags": tags + ["#Shorts", "Shorts"],
                "categoryId": "22"
            },
            "status": {"privacyStatus": privacy}
        }
        
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/*")
        request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
        
        response = None
        while response is None:
            status, response = request.next_chunk()
        
        video_id = response["id"]
        
        # Upload thumbnail if provided
        if thumbnail_path:
            thumb_path = thumbnail_path.lstrip("/")
            if os.path.exists(thumb_path):
                try:
                    youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(thumb_path)
                    ).execute()
                except Exception as e:
                    pass  # Thumbnail upload failed, but video is uploaded
        
        url = f"https://www.youtube.com/shorts/{video_id}"
        add_history("youtube", title, "success", video_path)
        return {"success": True, "video_id": video_id, "url": url}
        
    except HttpError as e:
        error_msg = str(e)
        add_history("youtube", title, "failed", video_path, error_msg)
        raise HTTPException(500, f"YouTube upload failed: {error_msg}")

@router.get("/audio-library")
async def get_audio_library(q: str = ""):
    """Fetch YouTube Audio Library tracks via YouTube Data API"""
    creds = get_yt_credentials()
    if not creds:
        return {"tracks": [], "note": "Connect YouTube to browse audio library"}
    
    try:
        youtube = build("youtube", "v3", credentials=creds)
        search_params = {
            "part": "snippet",
            "type": "video",
            "videoCategoryId": "10",
            "videoLicense": "creativeCommon",
            "maxResults": 20,
            "q": q if q else "background music no copyright"
        }
        result = youtube.search().list(**search_params).execute()
        tracks = []
        for item in result.get("items", []):
            tracks.append({
                "id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "thumbnail": item["snippet"]["thumbnails"]["default"]["url"]
            })
        return {"tracks": tracks}
    except Exception as e:
        return {"tracks": [], "error": str(e)}

@router.post("/revoke")
async def revoke_youtube():
    tokens = load_tokens()
    tokens.pop("youtube", None)
    save_tokens(tokens)
    return {"success": True}
