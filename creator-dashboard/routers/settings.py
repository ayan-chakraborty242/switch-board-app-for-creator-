from fastapi import APIRouter, HTTPException
import json, os

router = APIRouter()

SETTINGS_FILE = "settings.json"
TEMPLATES_FILE = "templates.json"

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE) as f:
        return json.load(f)

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_templates():
    if not os.path.exists(TEMPLATES_FILE):
        return {"titles": [], "hashtags": [], "descriptions": []}
    with open(TEMPLATES_FILE) as f:
        return json.load(f)

def save_templates(data):
    with open(TEMPLATES_FILE, "w") as f:
        json.dump(data, f, indent=2)

@router.get("")
async def get_settings():
    settings = load_settings()
    # Mask sensitive values for display
    masked = json.loads(json.dumps(settings))
    for platform in ["youtube", "facebook"]:
        if platform in masked:
            for key in ["client_secret", "access_token"]:
                if masked[platform].get(key):
                    val = masked[platform][key]
                    masked[platform][key] = val[:4] + "•" * 8 + val[-4:] if len(val) > 8 else "•" * len(val)
    return masked

@router.get("/raw")
async def get_settings_raw():
    """Get unmasked settings for editing"""
    return load_settings()

@router.post("")
async def update_settings(data: dict):
    settings = load_settings()
    
    for section, values in data.items():
        if section not in settings:
            settings[section] = {}
        for key, value in values.items():
            # Don't overwrite with masked placeholder values
            if isinstance(value, str) and "•" in value:
                continue
            settings[section][key] = value
    
    save_settings(settings)
    return {"success": True, "settings": settings}

@router.get("/templates")
async def get_templates():
    return load_templates()

@router.post("/templates")
async def update_templates(data: dict):
    templates = load_templates()
    
    for key in ["titles", "hashtags", "descriptions"]:
        if key in data:
            templates[key] = data[key]
    
    save_templates(templates)
    return {"success": True, "templates": templates}

@router.post("/templates/add")
async def add_template_item(data: dict):
    """Add a single item (title, hashtag set, or description) to saved templates"""
    templates = load_templates()
    category = data.get("category")  # 'titles', 'hashtags', 'descriptions'
    value = data.get("value")
    
    if category not in ["titles", "hashtags", "descriptions"]:
        raise HTTPException(400, "Invalid category")
    if not value:
        raise HTTPException(400, "Value is required")
    
    if category not in templates:
        templates[category] = []
    
    if value not in templates[category]:
        templates[category].insert(0, value)
        templates[category] = templates[category][:20]  # Keep last 20
    
    save_templates(templates)
    return {"success": True, "templates": templates}

@router.delete("/templates/{category}/{index}")
async def delete_template_item(category: str, index: int):
    templates = load_templates()
    if category not in templates:
        raise HTTPException(404, "Category not found")
    
    if 0 <= index < len(templates[category]):
        templates[category].pop(index)
        save_templates(templates)
        return {"success": True}
    
    raise HTTPException(404, "Item not found")
