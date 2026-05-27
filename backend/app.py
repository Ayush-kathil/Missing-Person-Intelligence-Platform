import os
import shutil
import tempfile
import asyncio
import csv
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
import uuid

# Import new SQLite DB methods
from db import get_session, set_session, delete_session, flush_all_sessions
import engine
from logger_config import logger

SHARED_SESSIONS_DIR = Path(os.getenv("SHARED_SESSIONS_DIR", "sessions"))
SNAPSHOT_DIR = Path(os.getenv("MATCH_SNAPSHOT_DIR", "output/snapshots"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize in-memory state for active background tasks
    app.state.active_tasks = {}
    logger.bind(event="startup").info("Pre-loading AI models (YOLOv12 prioritized)")
    try:
        engine.warm_up_models()
        logger.bind(event="startup").info("AI models loaded successfully")
    except Exception as e:
        logger.bind(event="startup", error=str(e)).error("Model pre-loading warning")
    yield
    logger.bind(event="shutdown").info("FastAPI lifespan shutdown completed")

app = FastAPI(title="Surveillance Analysis API", lifespan=lifespan)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_session_workdir(session_id: str) -> Path:
    session_root = SHARED_SESSIONS_DIR / session_id
    session_root.mkdir(parents=True, exist_ok=True)
    return session_root


def _save_uploaded_file(upload: UploadFile, destination: Path) -> int:
    upload.file.seek(0)
    with open(destination, "wb") as buffer:
        shutil.copyfileobj(upload.file, buffer, length=8 * 1024 * 1024)
    return int(destination.stat().st_size)


# --- BACKGROUND ANALYSIS WORKER ---

def run_analysis_sync(
    session_id: str,
    cam1_path: str,
    cam2_path: str,
    reference_path: str,
    profile: str,
    state_dict: dict
):
    """Synchronous worker that runs YOLO/DeepFace in the background thread."""
    state_dict["state"] = "processing"
    
    try:
        with open(reference_path, "rb") as f:
            ref_bytes = f.read()
        target_encoding = engine.load_encoding_from_image(ref_bytes)
        
        alerts_list = []
        progress_data = {
            "processed_frames": 0,
            "total_frames": 1,
            "current_camera": "CAM-1"
        }

        def on_progress(p_data):
            state_dict["current_camera"] = p_data.get("camera", "CAM-1")
            state_dict["processed_frames"] = p_data.get("frame_index", 0)
            state_dict["total_frames"] = max(1, p_data.get("camera_total_frames", 1))
            state_dict["progress_percent"] = int((state_dict["processed_frames"] / state_dict["total_frames"]) * 100)
            if p_data.get("latest_box"):
                state_dict["latest_boxes"][state_dict["current_camera"]] = p_data["latest_box"]

        def on_alert(alert_data):
            state_dict["alerts_count"] += 1

        # Analyze CAM-1
        engine.analyze_video_alerts(
            cam1_path, "CAM-1", target_encoding, alerts_list,
            profile=profile, progress=progress_data,
            progress_callback=on_progress, alert_callback=on_alert
        )

        # Analyze CAM-2
        if os.path.exists(cam2_path):
            engine.analyze_video_alerts(
                cam2_path, "CAM-2", target_encoding, alerts_list,
                profile=profile, progress=progress_data,
                progress_callback=on_progress, alert_callback=on_alert
            )

        # Finalize
        state_dict["state"] = "completed"
        state_dict["alerts"] = alerts_list
        state_dict["progress_percent"] = 100

        # Persist to SQLite
        session_data = get_session(session_id) or {}
        session_data.update(state_dict)
        set_session(session_id, session_data)

    except Exception as e:
        logger.bind(event="background_task_error", error=str(e)).error("Analysis failed")
        state_dict["state"] = "failed"
        state_dict["error"] = str(e)
        session_data = get_session(session_id) or {}
        session_data.update(state_dict)
        set_session(session_id, session_data)


def _task_payload(session_id: str) -> dict[str, Any]:
    """Builds the telemetry payload by checking in-memory active tasks first, then SQLite fallback."""
    # Check if actively running in memory
    active_task = app.state.active_tasks.get(session_id)
    if active_task:
        return active_task

    # Fallback to SQLite (if completed, failed, or historical)
    session = get_session(session_id)
    if not session:
        return {
            "state": "not_found",
            "progress_percent": 0,
            "processed_frames": 0,
            "total_frames": 1,
            "alerts_count": 0,
            "alerts": [],
            "latest_boxes": {"CAM-1": None, "CAM-2": None},
            "error": "Session not found",
        }

    return {
        "state": session.get("state", "pending"),
        "progress_percent": int(session.get("progress_percent") or 0),
        "processed_frames": int(session.get("processed_frames") or 0),
        "total_frames": max(1, int(session.get("total_frames") or 1)),
        "alerts_count": int(session.get("alerts_count") or 0),
        "latest_boxes": session.get("latest_boxes") or {"CAM-1": None, "CAM-2": None},
        "profile": session.get("profile", "balanced"),
        "current_camera": session.get("current_camera", "CAM-1"),
        "error": session.get("error"),
        "alerts": session.get("alerts") or [],
    }

# --- ENDPOINTS ---

@app.post("/api/analyze")
async def analyze_surveillance(
    background_tasks: BackgroundTasks,
    missing_image: UploadFile = File(...),
    cam1_video: UploadFile = File(...),
    cam2_video: UploadFile = File(...),
    profile: str = Form("balanced"),
):
    try:
        img_bytes = await missing_image.read()
        if not img_bytes:
            raise HTTPException(status_code=400, detail="Reference image is empty.")

        session_id = str(uuid.uuid4())
        temp_dir = _build_session_workdir(session_id)
        cam1_path = str(temp_dir / "cam1.mp4")
        cam2_path = str(temp_dir / "cam2.mp4")
        reference_filename = Path(missing_image.filename or "reference.jpg").name
        reference_path = str(temp_dir / reference_filename)
        
        with open(reference_path, "wb") as reference_buffer:
            reference_buffer.write(img_bytes)

        cam1_size, cam2_size = await asyncio.gather(
            asyncio.to_thread(_save_uploaded_file, cam1_video, Path(cam1_path)),
            asyncio.to_thread(_save_uploaded_file, cam2_video, Path(cam2_path)),
        )

        normalized_profile = profile.strip().lower() if profile else "balanced"
        if normalized_profile not in {"fast", "balanced", "accurate"}:
            normalized_profile = "balanced"

        # Initialize tracking state
        app.state.active_tasks[session_id] = {
            "state": "pending",
            "progress_percent": 0,
            "processed_frames": 0,
            "total_frames": 1,
            "alerts_count": 0,
            "alerts": [],
            "latest_boxes": {"CAM-1": None, "CAM-2": None},
            "profile": normalized_profile,
            "current_camera": "CAM-1",
            "error": None,
        }

        # Save initial session metadata to SQLite
        session_data = {
            "CAM-1": cam1_path,
            "CAM-2": cam2_path,
            "reference": reference_path,
            "profile": normalized_profile,
            "created_at": datetime.utcnow().isoformat(),
            "cam1_size": cam1_size,
            "cam2_size": cam2_size,
        }
        set_session(session_id, session_data)

        # Trigger background task without Celery!
        background_tasks.add_task(
            run_analysis_sync,
            session_id,
            cam1_path,
            cam2_path,
            reference_path,
            normalized_profile,
            app.state.active_tasks[session_id]
        )

        logger.bind(event="session_created", session_id=session_id, profile=normalized_profile).info(
            "Session created and local background task queued"
        )
        
        return {
            "status": "success",
            "session_id": session_id,
            "profile": normalized_profile,
            "job_state": "pending",
        }

    except Exception as e:
        logger.bind(event="session_create_failed", error=str(e)).exception("Session creation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/video/{session_id}/{cam_id}")
async def get_video(session_id: str, cam_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if cam_id not in ["CAM-1", "CAM-2"]:
        raise HTTPException(status_code=404, detail="Invalid camera ID")
        
    video_path = session.get(cam_id)
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    return FileResponse(video_path, media_type="video/mp4")


@app.get("/api/alerts/{session_id}")
async def get_alerts(session_id: str):
    payload = _task_payload(session_id)
    return {
        "alerts": payload.get("alerts", []),
        "job_state": payload.get("state", "pending"),
        "profile": payload.get("profile", "balanced"),
        "latest_boxes": payload.get("latest_boxes", {"CAM-1": None, "CAM-2": None}),
    }


@app.get("/api/progress/{session_id}")
async def get_progress(session_id: str):
    payload = _task_payload(session_id)
    return {
        "state": payload.get("state", "pending"),
        "progress_percent": payload.get("progress_percent", 0),
        "processed_frames": payload.get("processed_frames", 0),
        "total_frames": payload.get("total_frames", 1),
        "current_camera": payload.get("current_camera", "CAM-1"),
        "alerts_count": payload.get("alerts_count", 0),
        "profile": payload.get("profile", "balanced"),
        "error": payload.get("error"),
        "latest_boxes": payload.get("latest_boxes", {"CAM-1": None, "CAM-2": None}),
    }


@app.websocket("/ws/session/{session_id}")
async def session_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            payload = _task_payload(session_id)
            await websocket.send_json(payload)
            state = str(payload.get("state", "pending")).lower()
            if state in {"completed", "failed", "error", "not_found"}:
                break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
    except Exception as e:
        logger.bind(event="ws_error", error=str(e)).error("WebSocket error")
        await websocket.close(code=1011)


@app.get("/api/snapshots/{session_id}/{filename}")
async def get_snapshot(session_id: str, filename: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    safe_filename = Path(filename).name
    snapshot_path = Path(__file__).resolve().parent / "output" / "snapshots" / safe_filename

    if not snapshot_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return FileResponse(snapshot_path, media_type="image/jpeg", filename=safe_filename)


@app.get("/api/export/{session_id}")
async def export_session_artifacts(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    payload = _task_payload(session_id)
    state = str(payload.get("state") or "pending").lower()
    if state not in {"completed", "failed", "error"}:
        raise HTTPException(status_code=409, detail="Session export is available after analysis finishes")

    alerts = payload.get("alerts") or []
    export_path = Path(tempfile.gettempdir()) / f"evidence_{session_id}.zip"
    alerts_json = json.dumps(alerts, indent=2)

    alerts_csv_rows: list[dict[str, Any]] = []
    for alert in alerts:
        alerts_csv_rows.append(
            {
                "timestamp": alert.get("timestamp", ""),
                "camera": alert.get("camera", ""),
                "confidence_score": alert.get("score", ""),
                "video_timestamp": alert.get("video_timestamp", ""),
                "track_id": alert.get("track_id", ""),
            }
        )

    csv_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    csv_path = Path(csv_file.name)
    csv_file.close()
    with open(csv_path, "w", newline="", encoding="utf-8") as csv_buffer:
        writer = csv.DictWriter(
            csv_buffer,
            fieldnames=["timestamp", "camera", "confidence_score", "video_timestamp", "track_id"],
        )
        writer.writeheader()
        writer.writerows(alerts_csv_rows)

    with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_buffer:
        reference_path = Path(str(session.get("reference") or ""))
        if reference_path.exists() and reference_path.is_file():
            zip_buffer.write(reference_path, arcname=f"reference/{reference_path.name}")

        zip_buffer.writestr("alerts/alerts.json", alerts_json)
        zip_buffer.write(csv_path, arcname="alerts/alerts.csv")

        for alert in alerts:
            snapshot_name = Path(str(alert.get("snapshot") or "")).name
            if not snapshot_name:
                continue
            snapshot_path = SNAPSHOT_DIR / snapshot_name
            if snapshot_path.exists() and snapshot_path.is_file():
                zip_buffer.write(snapshot_path, arcname=f"snapshots/{snapshot_name}")

    try:
        csv_path.unlink(missing_ok=True)
    except Exception:
        pass

    logger.bind(event="session_export", session_id=session_id, alert_count=len(alerts)).info(
        "Evidence export generated"
    )
    return FileResponse(
        path=export_path,
        media_type="application/zip",
        filename=f"evidence_{session_id}.zip",
    )


@app.get("/health")
def read_root():
    return {"status": "Online"}


class ResetRequest(BaseModel):
    session_id: str | None = None
    prune_outputs: bool = True


@app.post("/api/system/reset-workspace")
async def reset_workspace(payload: ResetRequest):
    if payload.session_id:
        # If currently running, we'd need cancellation tokens, but for student version we just clear state
        if payload.session_id in app.state.active_tasks:
            app.state.active_tasks[payload.session_id]["state"] = "failed"
            app.state.active_tasks[payload.session_id]["error"] = "Cancelled"
        delete_session(payload.session_id)
    else:
        for sid in app.state.active_tasks:
            app.state.active_tasks[sid]["state"] = "failed"
            app.state.active_tasks[sid]["error"] = "Cancelled"
        flush_all_sessions()

    return {
        "status": "success",
        "message": "Workspace reset completed.",
    }
