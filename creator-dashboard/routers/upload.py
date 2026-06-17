from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os, shutil, uuid, json
from pathlib import Path
from datetime import datetime

router = APIRouter()

ALLOWED_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".webp"}
MAX_VIDEO_MB = 500
MAX_IMAGE_MB = 10

def get_ext(filename: str) -> str:
    return Path(filename).suffix.lower()

@router.post("/video")
async def upload_video(file: UploadFile = File(...)):
    ext = get_ext(file.filename)
    if ext not in ALLOWED_VIDEO:
        raise HTTPException(400, f"Unsupported format. Allowed: {', '.join(ALLOWED_VIDEO)}")
    
    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ext}"
    dest = Path("uploads") / filename
    
    size = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_VIDEO_MB * 1024 * 1024:
                os.remove(dest)
                raise HTTPException(413, f"Video exceeds {MAX_VIDEO_MB}MB limit")
            f.write(chunk)
    
    return {"success": True, "file_id": file_id, "filename": filename, "path": f"/uploads/{filename}", "size_mb": round(size / 1024 / 1024, 2)}

@router.post("/thumbnail")
async def upload_thumbnail(file: UploadFile = File(...)):
    ext = get_ext(file.filename)
    if ext not in ALLOWED_IMAGE:
        raise HTTPException(400, f"Unsupported format. Allowed: {', '.join(ALLOWED_IMAGE)}")
    
    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ext}"
    dest = Path("thumbnails") / filename
    
    size = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_IMAGE_MB * 1024 * 1024:
                os.remove(dest)
                raise HTTPException(413, f"Image exceeds {MAX_IMAGE_MB}MB limit")
            f.write(chunk)
    
    return {"success": True, "file_id": file_id, "filename": filename, "path": f"/thumbnails/{filename}"}

@router.post("/extract-frame")
async def extract_frame(data: dict):
    """Extract a frame from video at given timestamp (seconds)"""
    video_path = data.get("video_path", "").lstrip("/")
    timestamp = float(data.get("timestamp", 0))
    
    if not os.path.exists(video_path):
        raise HTTPException(404, "Video file not found")
    
    frame_id = str(uuid.uuid4())
    frame_filename = f"{frame_id}.jpg"
    frame_path = Path("thumbnails") / frame_filename
    
    # Use ffmpeg if available, otherwise fallback
    ret = os.system(f'ffmpeg -ss {timestamp} -i "{video_path}" -vframes 1 -q:v 2 "{frame_path}" -y 2>/dev/null')
    
    if ret != 0 or not frame_path.exists():
        raise HTTPException(500, "Could not extract frame. Ensure ffmpeg is installed.")
    
    return {"success": True, "path": f"/thumbnails/{frame_filename}", "filename": frame_filename}

@router.get("/list")
async def list_uploads():
    files = []
    for f in Path("uploads").iterdir():
        if f.is_file():
            stat = f.stat()
            files.append({
                "filename": f.name,
                "path": f"/uploads/{f.name}",
                "size_mb": round(stat.st_size / 1024 / 1024, 2),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    return sorted(files, key=lambda x: x["modified"], reverse=True)

@router.delete("/video/{filename}")
async def delete_video(filename: str):
    path = Path("uploads") / filename
    if path.exists():
        path.unlink()
        return {"success": True}
    raise HTTPException(404, "File not found")
