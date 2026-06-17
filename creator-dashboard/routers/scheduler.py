from fastapi import APIRouter, HTTPException
import json, os, uuid
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import requests

router = APIRouter()

# Global scheduler instance
scheduler = BackgroundScheduler()
scheduler.start()

def load_schedules():
    if not os.path.exists("schedules.json"):
        return []
    with open("schedules.json") as f:
        return json.load(f)

def save_schedules(schedules):
    with open("schedules.json", "w") as f:
        json.dump(schedules, f, indent=2)

def execute_scheduled_upload(schedule_id: str):
    """Execute a scheduled upload"""
    schedules = load_schedules()
    schedule = next((s for s in schedules if s["id"] == schedule_id), None)
    if not schedule:
        return
    
    # Update status to running
    for s in schedules:
        if s["id"] == schedule_id:
            s["status"] = "running"
            s["executed_at"] = datetime.now().isoformat()
    save_schedules(schedules)
    
    platforms = schedule.get("platforms", [])
    results = {}
    
    for platform in platforms:
        try:
            if platform == "youtube":
                resp = requests.post("http://localhost:8000/api/youtube/upload", json=schedule.get("youtube_data", {}))
                results["youtube"] = {"success": resp.status_code == 200, "data": resp.json()}
            elif platform == "facebook":
                resp = requests.post("http://localhost:8000/api/facebook/upload", json=schedule.get("facebook_data", {}))
                results["facebook"] = {"success": resp.status_code == 200, "data": resp.json()}
            elif platform == "instagram":
                resp = requests.post("http://localhost:8000/api/instagram/upload", json=schedule.get("instagram_data", {}))
                results["instagram"] = {"success": resp.status_code == 200, "data": resp.json()}
        except Exception as e:
            results[platform] = {"success": False, "error": str(e)}
    
    # Update final status
    schedules = load_schedules()
    all_success = all(r.get("success", False) for r in results.values())
    for s in schedules:
        if s["id"] == schedule_id:
            s["status"] = "completed" if all_success else "partial_failure"
            s["results"] = results
            s["completed_at"] = datetime.now().isoformat()
    save_schedules(schedules)

@router.get("/list")
async def list_schedules():
    return load_schedules()

@router.post("/create")
async def create_schedule(data: dict):
    scheduled_time = data.get("scheduled_time")  # ISO format
    platforms = data.get("platforms", [])
    
    if not scheduled_time or not platforms:
        raise HTTPException(400, "scheduled_time and platforms are required")
    
    try:
        run_time = datetime.fromisoformat(scheduled_time)
    except ValueError:
        raise HTTPException(400, "Invalid datetime format. Use ISO format: 2024-01-15T14:30:00")
    
    if run_time <= datetime.now():
        raise HTTPException(400, "Scheduled time must be in the future")
    
    schedule_id = str(uuid.uuid4())
    schedule = {
        "id": schedule_id,
        "scheduled_time": scheduled_time,
        "platforms": platforms,
        "title": data.get("title", "Scheduled Upload"),
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "youtube_data": data.get("youtube_data", {}),
        "facebook_data": data.get("facebook_data", {}),
        "instagram_data": data.get("instagram_data", {})
    }
    
    # Schedule the job
    scheduler.add_job(
        execute_scheduled_upload,
        trigger=DateTrigger(run_date=run_time),
        args=[schedule_id],
        id=schedule_id
    )
    
    schedules = load_schedules()
    schedules.append(schedule)
    save_schedules(schedules)
    
    return {"success": True, "schedule": schedule}

@router.delete("/{schedule_id}")
async def cancel_schedule(schedule_id: str):
    schedules = load_schedules()
    schedule = next((s for s in schedules if s["id"] == schedule_id), None)
    if not schedule:
        raise HTTPException(404, "Schedule not found")
    
    # Cancel APScheduler job if pending
    try:
        if scheduler.get_job(schedule_id):
            scheduler.remove_job(schedule_id)
    except Exception:
        pass
    
    schedules = [s for s in schedules if s["id"] != schedule_id]
    save_schedules(schedules)
    return {"success": True}

@router.get("/restore")
async def restore_schedules():
    """Restore pending schedules on startup"""
    schedules = load_schedules()
    restored = 0
    now = datetime.now()
    
    for schedule in schedules:
        if schedule.get("status") == "pending":
            try:
                run_time = datetime.fromisoformat(schedule["scheduled_time"])
                if run_time > now:
                    scheduler.add_job(
                        execute_scheduled_upload,
                        trigger=DateTrigger(run_date=run_time),
                        args=[schedule["id"]],
                        id=schedule["id"],
                        replace_existing=True
                    )
                    restored += 1
                else:
                    # Mark as missed
                    schedule["status"] = "missed"
            except Exception:
                pass
    
    save_schedules(schedules)
    return {"restored": restored}
