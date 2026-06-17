# Switchboard — Creator Dashboard

A personal one-click publisher for **YouTube Shorts**, **Facebook Reels**, and **Instagram Reels**. Upload once, publish everywhere. Works great on mobile.

---

## Features

- **One-click publishing** to all three platforms simultaneously
- **AI-generated metadata** — titles, descriptions, hashtags, YouTube SEO tags via Claude
- **Frame picker** for YouTube thumbnails (scrub through your video and pick any frame)
- **Custom thumbnails** for all platforms
- **Facebook → Instagram sync** (title & first N hashtags auto-synced)
- **APScheduler-based scheduling** — fresh uploads at your chosen time
- **Upload history** with per-platform status
- **Saved templates** — titles and hashtag sets auto-saved after each publish
- **Drag-and-drop** video upload
- **Mobile-first** responsive design — works on your phone

---

## Quick Start

```bash
# 1. Clone / download the project
cd creator-dashboard

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
./start.sh
# or
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 4. Open in browser
#    Desktop: http://localhost:8000
#    Phone (same WiFi): http://<your-local-ip>:8000
```

---

## Platform Setup

### YouTube

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**
2. Create **OAuth 2.0 Client ID** → Web application
3. Add Authorized redirect URI: `http://localhost:8000/auth/youtube/callback`
   - For phone access: also add `http://<your-local-ip>:8000/auth/youtube/callback`
4. Enable **YouTube Data API v3** in your project
5. Open Switchboard → **Settings** → paste Client ID and Client Secret → Save
6. Click **Connect** on the YouTube channel card → authorize in browser

### Facebook Reels

1. Go to [Meta for Developers](https://developers.facebook.com/) → create an App
2. Add **Facebook Login** and **Pages API** products
3. Open [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
4. Generate a **Page Access Token** with these permissions:
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `pages_show_list`
5. Open Switchboard → **Settings** → paste the token and your **Page ID** → Save

> **Get your Page ID**: Go to your Facebook Page → About → scroll to the bottom or check the URL.

### Instagram Reels

Instagram requires your video to be at a **publicly accessible URL**. Options:

- **Same server**: If your machine has a public IP or domain, use that.
- **ngrok** (easiest for local dev): `ngrok http 8000` → use the HTTPS URL in the Instagram URL field
- **Cloud storage**: Upload to S3/Cloudflare R2 and use that URL

1. Connect Facebook (above) — Instagram uses the same token
2. Find your **Instagram Business Account ID**:
   - In Graph API Explorer: `GET /me/accounts` → find your page → `GET /{page-id}?fields=instagram_business_account`
3. Open Switchboard → **Settings** → paste the Instagram Account ID → Save

---

## AI Generation (optional)

1. Get an [Anthropic API key](https://console.anthropic.com/)
2. Open **Settings** → paste under **Anthropic API key** → Save
3. After uploading a video, describe the clip in the AI card and click **Generate**

---

## File Structure

```
creator-dashboard/
├── main.py              # FastAPI app entry point
├── start.sh             # Launch script
├── requirements.txt
├── settings.json        # Your API keys and config (gitignore this!)
├── oauth_tokens.json    # YouTube OAuth tokens (gitignore this!)
├── schedules.json       # Pending/past schedules
├── templates.json       # Saved titles and hashtag sets
├── upload_history.json  # History of all uploads
├── uploads/             # Uploaded videos
├── thumbnails/          # Uploaded/extracted thumbnails
├── routers/
│   ├── upload.py        # File upload endpoints
│   ├── youtube.py       # YouTube API + OAuth
│   ├── facebook.py      # Facebook Graph API
│   ├── instagram.py     # Instagram Graph API
│   ├── scheduler.py     # APScheduler background jobs
│   ├── settings.py      # Settings and templates CRUD
│   ├── ai_tools.py      # Claude API for AI generation
│   └── history.py       # Upload history + publish-all
├── static/
│   ├── css/style.css
│   └── js/app.js
└── templates/
    ├── index.html
    └── auth_result.html
```

---

## Security Notes

- This app is for **personal use** — no authentication is built in
- **Do not expose it to the internet** without adding auth
- Add `settings.json` and `oauth_tokens.json` to `.gitignore` — they contain secrets
- For phone access on home WiFi, local IP (`192.168.x.x`) is fine

---

## Requirements

- Python 3.10+
- `ffmpeg` (for video frame extraction — `sudo apt install ffmpeg` or `brew install ffmpeg`)
- All Python packages in `requirements.txt`
