
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uvicorn
import json
import os


# --------------------
# Create required directories
# --------------------
for directory in ["uploads", "thumbnails", "static", "templates"]:
    Path(directory).mkdir(exist_ok=True)


# --------------------
# Initialize JSON files
# --------------------
def init_json_file(path: str, default_data):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=2)


json_files = {
    "schedules.json": [],
    "templates.json": {
        "titles": [],
        "hashtags": [],
        "descriptions": [],
    },
    "settings.json": {
        "youtube": {
            "client_id": "",
            "client_secret": "",
            "redirect_uri": "http://localhost:8000/auth/youtube/callback",
        },
        "facebook": {
            "app_id": "",
            "app_secret": "",
            "access_token": "",
            "page_id": "",
        },
        "instagram": {
            "account_id": "",
            "max_hashtags": 5,
        },
        "general": {
            "default_title": "",
            "auto_generate_ai": False,
        },
    },
    "upload_history.json": [],
    "oauth_tokens.json": {},
}

for file, default in json_files.items():
    init_json_file(file, default)


# --------------------
# FastAPI App
# --------------------
app = FastAPI(
    title="Creator Dashboard",
    version="1.0.0"
)

# --------------------
# Middleware
# --------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------
# Static files
# --------------------
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/thumbnails", StaticFiles(directory="thumbnails"), name="thumbnails")

templates = Jinja2Templates(directory="templates")

# --------------------
# Routers
# --------------------
# Moving imports here ensures that 'app' and 'templates' are defined before 
# the routers are loaded, preventing circular import crashes.
from routers import (
    upload,
    youtube,
    facebook,
    instagram,
    scheduler,
    settings,
    ai_tools,
    history,
)

app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(youtube.router, prefix="/api/youtube", tags=["YouTube"])
app.include_router(facebook.router, prefix="/api/facebook", tags=["Facebook"])
app.include_router(instagram.router, prefix="/api/instagram", tags=["Instagram"])
app.include_router(scheduler.router, prefix="/api/schedule", tags=["Scheduler"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(ai_tools.router, prefix="/api/ai", tags=["AI"])
app.include_router(history.router, prefix="/api/history", tags=["History"])


# --------------------
# Routes
# --------------------
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@app.get("/auth/youtube/callback")
async def youtube_callback(
    request: Request,
    code: str = None,
    error: str = None,
):
    if error:
        return templates.TemplateResponse(
            "auth_result.html",
            {
                "request": request,
                "success": False,
                "platform": "YouTube",
                "message": error,
            },
        )

    if code:
        result = await youtube.exchange_code(code)

        return templates.TemplateResponse(
            "auth_result.html",
            {
                "request": request,
                "success": result["success"],
                "platform": "YouTube",
                "message": result.get("message", ""),
            },
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
