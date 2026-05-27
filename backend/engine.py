"""Missing-person detection engine with tracker-first temporal matching."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
from deepface import DeepFace
from ultralytics import YOLO
from logger_config import logger

try:
    import torch
except Exception:  # pragma: no cover - optional acceleration
    torch = None

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("ABSL_MIN_LOG_LEVEL", "2")

warnings.filterwarnings(
    "ignore",
    message=r"From .*tf_keras.*sparse_softmax_cross_entropy.*deprecated.*",
    category=UserWarning,
)

FACE_MODEL_NAME = os.getenv("FACE_MODEL_NAME", "Facenet512")
FACE_DETECTOR_BACKEND = os.getenv("FACE_DETECTOR_BACKEND", "retinaface")
TRACK_FACE_DETECTOR_BACKEND = os.getenv("TRACK_FACE_DETECTOR_BACKEND", "retinaface")
TRACKER_TYPE = os.getenv("TRACKER_TYPE", "bytetrack").strip().lower()
PERSON_CLASS_ID = 0
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.85"))
FACE_CONFIDENCE_THRESHOLD = float(os.getenv("FACE_CONFIDENCE_THRESHOLD", "0.60"))
YOLO_CONFIDENCE = float(os.getenv("YOLO_CONFIDENCE", "0.35"))
YOLO_IMAGE_SIZE = int(os.getenv("YOLO_IMAGE_SIZE", "640"))
MAX_PERSONS_PER_FRAME = int(os.getenv("MAX_PERSONS_PER_FRAME", "6"))
MAX_FRAME_WIDTH = int(os.getenv("MAX_FRAME_WIDTH", "960"))
PERSON_CROP_PADDING = int(os.getenv("PERSON_CROP_PADDING", "24"))
MATCH_RESET_FRAMES = max(1, int(os.getenv("MATCH_RESET_FRAMES", "4")))
MATCH_CONFIRM_FRAMES = max(1, int(os.getenv("MATCH_CONFIRM_FRAMES", "1")))
SNAPSHOT_DIR = Path(os.getenv("MATCH_SNAPSHOT_DIR", "output/snapshots"))
YOLO_DEVICE = 0 if torch is not None and torch.cuda.is_available() else "cpu"
YOLO_HALF = bool(torch is not None and torch.cuda.is_available())

PROFILE_PRESETS: dict[str, dict[str, float]] = {
    "fast": {
        "match_threshold": max(0.75, MATCH_THRESHOLD - 0.05),
        "yolo_confidence": max(0.25, YOLO_CONFIDENCE - 0.05),
        "confirm_frames": max(1, MATCH_CONFIRM_FRAMES - 1),
    },
    "balanced": {
        "match_threshold": MATCH_THRESHOLD,
        "yolo_confidence": YOLO_CONFIDENCE,
        "confirm_frames": MATCH_CONFIRM_FRAMES,
    },
    "accurate": {
        "match_threshold": min(0.95, MATCH_THRESHOLD + 0.03),
        "yolo_confidence": min(0.70, YOLO_CONFIDENCE + 0.05),
        "confirm_frames": max(2, MATCH_CONFIRM_FRAMES + 1),
    },
}


@dataclass
class FaceMatch:
    location: tuple[int, int, int, int]
    similarity: float
    euclidean_distance: float
    track_id: int


@dataclass
class TrackedPerson:
    track_id: int | None
    confidence: float
    location: tuple[int, int, int, int]
    crop: np.ndarray


@dataclass
class MatchAlert:
    camera: str
    timestamp: str
    video_timestamp: str
    score: float
    euclidean_distance: float
    snapshot: str
    bounding_box: tuple[int, int, int, int] | None
    track_id: int | None


_yolo_model: YOLO | None = None


def get_profile_config(profile: str | None) -> dict[str, float]:
    normalized = (profile or "balanced").strip().lower()
    return PROFILE_PRESETS.get(normalized, PROFILE_PRESETS["balanced"])


def _normalize(embedding: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(embedding))
    if norm == 0.0:
        return embedding.astype(np.float32, copy=False)
    return (embedding / norm).astype(np.float32, copy=False)


def _resolve_yolo_model_path() -> Path:
    candidates = [
        os.getenv("YOLO_MODEL_PATH"),
        "backend/yolov12n.engine",
        "yolov12n.engine",
        "backend/yolov12n_openvino_model",
        "yolov12n_openvino_model",
        "backend/yolov12n.pt",
        "yolov12n.pt",
        "backend/yolov8n.pt",
        "yolov8n.pt",
    ]

    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path

    raise FileNotFoundError(
        "No YOLO weights found. Place yolov12n.pt, yolov12n.engine, or yolov12n_openvino_model/ in the workspace, or keep yolov8n.pt as fallback."
    )


def get_yolo_model() -> YOLO:
    global _yolo_model
    if _yolo_model is None:
        _yolo_model = YOLO(str(_resolve_yolo_model_path()))
        try:
            _yolo_model.fuse()
        except Exception:
            pass
    return _yolo_model


def warm_up_models() -> None:
    DeepFace.build_model(FACE_MODEL_NAME)
    get_yolo_model()
    logger.bind(
        event="models_warmed", face_model=FACE_MODEL_NAME, tracker=TRACKER_TYPE
    ).info("Models warmed successfully")


def _represent_face(
    image: np.ndarray,
    detector_backend: str,
    enforce_detection: bool,
) -> list[dict[str, Any]]:
    return DeepFace.represent(
        img_path=image,
        model_name=FACE_MODEL_NAME,
        detector_backend=detector_backend,
        enforce_detection=enforce_detection,
        align=True,
    )


def _extract_embedding(
    image: np.ndarray,
    *,
    enforce_detection: bool,
    detector_backend: str,
) -> np.ndarray:
    results = _represent_face(
        image,
        detector_backend=detector_backend,
        enforce_detection=enforce_detection,
    )
    if not results:
        raise ValueError("No face could be extracted from the supplied image.")

    best_result: dict[str, Any] | None = None
    best_confidence = -1.0
    for result in results:
        embedding = result.get("embedding")
        if embedding is None:
            continue
        confidence = float(result.get("face_confidence") or 0.0)
        if confidence > best_confidence:
            best_confidence = confidence
            best_result = result

    if best_result is None:
        raise ValueError("No usable face embedding was returned.")

    if not enforce_detection and best_confidence < FACE_CONFIDENCE_THRESHOLD:
        raise ValueError("Detected face confidence is too low for matching.")

    return _normalize(np.asarray(best_result["embedding"], dtype=np.float32))


def load_encoding_from_image(image_bytes: bytes) -> np.ndarray:
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Invalid image")

    try:
        return _extract_embedding(
            image,
            enforce_detection=True,
            detector_backend=FACE_DETECTOR_BACKEND,
        )
    except Exception as exc:
        raise ValueError(
            f"Could not extract facial features from reference image: {exc}"
        ) from exc


def cosine_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    a = _normalize(embedding1)
    b = _normalize(embedding2)
    return float(np.clip(np.dot(a, b), -1.0, 1.0))


def euclidean_distance(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    a = _normalize(embedding1)
    b = _normalize(embedding2)
    return float(np.linalg.norm(a - b))


def _expand_crop(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    top = max(0, y1 - PERSON_CROP_PADDING)
    left = max(0, x1 - PERSON_CROP_PADDING)
    bottom = min(frame.shape[0], y2 + PERSON_CROP_PADDING)
    right = min(frame.shape[1], x2 + PERSON_CROP_PADDING)
    return frame[top:bottom, left:right]


def _fit_frame(frame: np.ndarray) -> np.ndarray:
    if frame.shape[1] <= MAX_FRAME_WIDTH:
        return frame
    scale = MAX_FRAME_WIDTH / frame.shape[1]
    return cv2.resize(frame, (MAX_FRAME_WIDTH, int(frame.shape[0] * scale)))


def _tracker_config() -> str:
    return "botsort.yaml" if TRACKER_TYPE == "botsort" else "bytetrack.yaml"


def _tracked_people(frame: np.ndarray, yolo_confidence: float) -> list[TrackedPerson]:
    results = get_yolo_model().track(
        frame,
        classes=[PERSON_CLASS_ID],
        conf=yolo_confidence,
        imgsz=YOLO_IMAGE_SIZE,
        tracker=_tracker_config(),
        persist=True,
        device=YOLO_DEVICE,
        half=YOLO_HALF,
        verbose=False,
    )

    tracked: list[TrackedPerson] = []
    for result in results:
        if result.boxes is None:
            continue
        for box in result.boxes:
            confidence = float(box.conf[0])
            if confidence < yolo_confidence:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            crop = _expand_crop(frame, x1, y1, x2, y2)
            if crop.size == 0:
                continue

            track_id = None
            if box.id is not None:
                track_id = int(box.id[0])

            tracked.append(
                TrackedPerson(
                    track_id=track_id,
                    confidence=confidence,
                    location=(x1, y1, x2, y2),
                    crop=crop,
                )
            )

    tracked.sort(key=lambda item: item.confidence, reverse=True)
    return tracked[:MAX_PERSONS_PER_FRAME]


def _save_match_snapshot(
    frame: np.ndarray,
    camera_id: str,
    timestamp: datetime,
    location: tuple[int, int, int, int] | None = None,
) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_path = (
        SNAPSHOT_DIR / f"{camera_id}_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
    )

    marked_frame = frame.copy()
    marked_frame = _blur_non_target_faces(marked_frame, location)
    if location is not None:
        x1, y1, x2, y2 = location
        x1 = max(0, min(int(x1), marked_frame.shape[1] - 1))
        y1 = max(0, min(int(y1), marked_frame.shape[0] - 1))
        x2 = max(0, min(int(x2), marked_frame.shape[1] - 1))
        y2 = max(0, min(int(y2), marked_frame.shape[0] - 1))
        cv2.rectangle(marked_frame, (x1, y1), (x2, y2), (0, 255, 255), 4)
        label_y = max(18, y1 - 10)
        cv2.rectangle(
            marked_frame,
            (x1, max(0, y1 - 24)),
            (min(marked_frame.shape[1] - 1, x1 + 170), y1),
            (0, 255, 255),
            -1,
        )
        cv2.putText(
            marked_frame,
            "DETECTED PERSON",
            (x1 + 6, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )

    cv2.imwrite(str(snapshot_path), marked_frame)
    return snapshot_path


def _overlaps_target(
    face_area: tuple[int, int, int, int], target: tuple[int, int, int, int] | None
) -> bool:
    if target is None:
        return False

    fx1, fy1, fx2, fy2 = face_area
    tx1, ty1, tx2, ty2 = target
    inter_left = max(fx1, tx1)
    inter_top = max(fy1, ty1)
    inter_right = min(fx2, tx2)
    inter_bottom = min(fy2, ty2)
    return inter_left < inter_right and inter_top < inter_bottom


def _blur_non_target_faces(
    frame: np.ndarray,
    target_location: tuple[int, int, int, int] | None,
) -> np.ndarray:
    try:
        faces = DeepFace.extract_faces(
            img_path=frame,
            detector_backend=TRACK_FACE_DETECTOR_BACKEND,
            enforce_detection=False,
            align=False,
        )
    except Exception:
        return frame

    output = frame.copy()
    for face in faces:
        facial_area = face.get("facial_area") or {}
        x = int(facial_area.get("x") or 0)
        y = int(facial_area.get("y") or 0)
        w = int(facial_area.get("w") or 0)
        h = int(facial_area.get("h") or 0)
        if w <= 0 or h <= 0:
            continue

        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(output.shape[1], x + w)
        y2 = min(output.shape[0], y + h)
        if x2 <= x1 or y2 <= y1:
            continue

        if _overlaps_target((x1, y1, x2, y2), target_location):
            continue

        roi = output[y1:y2, x1:x2]
        if roi.size == 0:
            continue
        blurred_roi = cv2.GaussianBlur(roi, (31, 31), 0)
        output[y1:y2, x1:x2] = blurred_roi

    return output


def _append_match_alert(
    alerts_list: list[dict[str, Any]],
    *,
    camera_id: str,
    score: float,
    euclidean_dist: float,
    event_time: datetime,
    video_timestamp: str,
    frame: np.ndarray,
    track_id: int | None,
    location: tuple[int, int, int, int] | None = None,
) -> None:
    snapshot_path = _save_match_snapshot(frame, camera_id, event_time, location)
    alert = MatchAlert(
        camera=camera_id,
        timestamp=event_time.isoformat(sep=" ", timespec="seconds"),
        video_timestamp=video_timestamp,
        score=round(score, 4),
        euclidean_distance=round(euclidean_dist, 4),
        snapshot=snapshot_path.name,
        bounding_box=location,
        track_id=track_id,
    )
    alerts_list.append(alert.__dict__)
    logger.bind(
        event="match_threshold_crossed",
        camera=camera_id,
        score=round(score, 4),
        track_id=track_id,
        video_timestamp=video_timestamp,
    ).info("Match threshold crossed")


def _get_or_cache_track_embedding(
    person: TrackedPerson,
    track_embeddings: dict[int, np.ndarray | None],
) -> np.ndarray | None:
    if person.track_id is None:
        return None

    if person.track_id in track_embeddings:
        return track_embeddings[person.track_id]

    try:
        embedding = _extract_embedding(
            person.crop,
            enforce_detection=True,
            detector_backend=TRACK_FACE_DETECTOR_BACKEND,
        )
    except Exception:
        track_embeddings[person.track_id] = None
        return None

    track_embeddings[person.track_id] = embedding
    return embedding


def _best_face_match(
    target_encoding: np.ndarray,
    tracked_people: list[TrackedPerson],
    track_embeddings: dict[int, np.ndarray | None],
) -> FaceMatch | None:
    best_match: FaceMatch | None = None
    for person in tracked_people:
        if person.track_id is None:
            continue

        embedding = _get_or_cache_track_embedding(person, track_embeddings)
        if embedding is None:
            continue

        similarity = cosine_similarity(target_encoding, embedding)
        distance = euclidean_distance(target_encoding, embedding)
        if best_match is None or similarity > best_match.similarity:
            best_match = FaceMatch(
                location=person.location,
                similarity=similarity,
                euclidean_distance=distance,
                track_id=person.track_id,
            )
    return best_match


def analyze_video_alerts(
    video_path: str,
    camera_id: str,
    target_encoding: np.ndarray,
    alerts_list: list[dict[str, Any]],
    *,
    profile: str,
    progress: dict[str, Any] | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    alert_callback: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    profile_config = get_profile_config(profile)
    match_threshold = float(profile_config["match_threshold"])
    yolo_confidence = float(profile_config["yolo_confidence"])
    confirm_frames = max(1, int(profile_config["confirm_frames"]))

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0))
    frame_index = 0
    match_active = False
    match_streak = 0
    non_match_streak = 0
    track_embeddings: dict[int, np.ndarray | None] = {}

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame_index += 1
            frame = _fit_frame(frame)

            tracked_people = _tracked_people(frame, yolo_confidence=yolo_confidence)
            best_match = _best_face_match(
                target_encoding=target_encoding,
                tracked_people=tracked_people,
                track_embeddings=track_embeddings,
            )

            is_match = bool(best_match and best_match.similarity >= match_threshold)
            if is_match and best_match is not None:
                match_streak += 1
                non_match_streak = 0
                if not match_active and match_streak >= confirm_frames:
                    match_active = True
                    event_time = datetime.now()
                    video_timestamp = str(timedelta(seconds=int(frame_index / fps)))
                    _append_match_alert(
                        alerts_list,
                        camera_id=camera_id,
                        score=best_match.similarity,
                        euclidean_dist=best_match.euclidean_distance,
                        event_time=event_time,
                        video_timestamp=video_timestamp,
                        frame=frame,
                        location=best_match.location,
                        track_id=best_match.track_id,
                    )
                    if alert_callback is not None and alerts_list:
                        alert_callback(dict(alerts_list[-1]))
            else:
                match_streak = 0
                non_match_streak += 1
                if non_match_streak >= MATCH_RESET_FRAMES:
                    match_active = False

            if progress is not None:
                progress["processed_frames"] = min(
                    int(progress.get("processed_frames", 0)) + 1,
                    int(progress.get("total_frames", total_frames)),
                )
                progress["current_camera"] = camera_id

            if progress_callback is not None:
                progress_callback(
                    {
                        "camera": camera_id,
                        "frame_index": frame_index,
                        "camera_total_frames": total_frames,
                        "latest_box": list(best_match.location) if best_match else None,
                        "track_id": best_match.track_id if best_match else None,
                        "score": (
                            round(best_match.similarity, 4) if best_match else None
                        ),
                    }
                )
    finally:
        cap.release()
