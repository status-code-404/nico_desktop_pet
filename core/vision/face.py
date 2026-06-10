"""
Face detection, recognition, and drinking-activity monitoring.

Detection: OpenCV Haar cascades (always available).
Recognition: face_recognition library with fallback to LBPH.
Drinking check: cup/container detection near mouth + hand-to-mouth gesture.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from server.config import settings

# ── face_recognition is optional (heavy dlib dep on arm64) ──
try:
    import face_recognition  # type: ignore

    HAS_FACE_RECOG = True
except ImportError:
    HAS_FACE_RECOG = False


# ── helpers ──────────────────────────────────────────────────────────

def _ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _now_iso() -> str:
    return datetime.now().isoformat()


# ── drinking-state persistence ───────────────────────────────────────

class DrinkingTracker:
    """Per-user drinking log, persisted as JSON in face_encodings_dir."""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        _ensure_dir(str(self.data_dir))
        self._state: dict[str, dict] = {}
        self._load()

    # ---- file io ----
    @property
    def _state_path(self) -> Path:
        return self.data_dir / "drinking_state.json"

    def _load(self) -> None:
        if self._state_path.exists():
            try:
                self._state = json.loads(self._state_path.read_text())
            except (json.JSONDecodeError, OSError):
                self._state = {}

    def _save(self) -> None:
        self._state_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2))

    # ---- public api ----
    def record_drink(self, name: str) -> None:
        today = _today_str()
        user = self._state.setdefault(name, {"drink_events": {}, "last_drink": None})
        events: dict = user["drink_events"]
        events.setdefault(today, [])
        now_iso = _now_iso()
        events[today].append(now_iso)
        user["last_drink"] = now_iso
        self._save()

    def last_drink(self, name: str) -> Optional[datetime]:
        user = self._state.get(name, {})
        raw = user.get("last_drink")
        if raw:
            return datetime.fromisoformat(raw)
        return None

    def drink_count_today(self, name: str) -> int:
        user = self._state.get(name, {})
        events: dict = user.get("drink_events", {})
        return len(events.get(_today_str(), []))

    def minutes_since_last_drink(self, name: str) -> Optional[float]:
        last = self.last_drink(name)
        if last is None:
            return None
        return (datetime.now() - last).total_seconds() / 60.0

    def needs_reminder(self, name: str) -> bool:
        mins = self.minutes_since_last_drink(name)
        if mins is None:
            return True
        return mins >= settings.drink_reminder_hours * 60


# ── Face service ─────────────────────────────────────────────────────

class FaceService:
    """Thin async wrapper; heavy cv2 calls run in executor via public async methods."""

    def __init__(self) -> None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        if not os.path.exists(cascade_path):
            raise FileNotFoundError(f"OpenCV haarcascade not found at {cascade_path}")
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

        self.encodings_dir = settings.face_encodings_dir
        _ensure_dir(self.encodings_dir)

        self.tracker = DrinkingTracker(self.encodings_dir)

        # known faces:  user_id -> list[ndarray]   (encodings)
        self.known_faces: dict[str, list[np.ndarray]] = {}
        self._user_profiles: dict[str, dict] = {}
        self._load_encodings()

        # ── user profiles (user_id -> metadata) ─────────────────────

    @property
    def _users_path(self) -> Path:
        return Path(self.encodings_dir) / "users.json"

    def _load_users(self) -> dict[str, dict]:
        if self._users_path.exists():
            try:
                return json.loads(self._users_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_users(self, users: dict) -> None:
        self._users_path.write_text(json.dumps(users, ensure_ascii=False, indent=2))

    def _lookup_user_id(self, name: str) -> Optional[str]:
        """Find user_id by name (case-insensitive)."""
        users = self._load_users()
        for uid, info in users.items():
            if info.get("name", "").lower() == name.lower():
                return uid
        return None

    # ── face encodings persistence ────────────────────────────────

    def _encodings_path(self, user_id: str) -> Path:
        safe = user_id.replace("/", "_").replace("\\", "_")
        return Path(self.encodings_dir) / f"{safe}.npy"

    def _load_encodings(self) -> None:
        if not HAS_FACE_RECOG:
            return
        for f in Path(self.encodings_dir).glob("*.npy"):
            if f.name.startswith("_") or f.name in ("users.json", "drinking_state.json"):
                continue
            uid = f.stem
            enc = np.load(str(f))
            self.known_faces[uid] = [enc]

        users = self._load_users()
        # Re-index: user_id -> encodings, plus name mapping
        self._user_profiles = users
        if self.known_faces:
            names = [users.get(uid, {}).get("name", uid) for uid in self.known_faces]
            print(f"[FaceService] loaded {len(self.known_faces)} known face(s): {names}")

    def _get_user_name(self, user_id: str) -> str:
        users = self._load_users()
        return users.get(user_id, {}).get("name", user_id)

    # ── detection ─────────────────────────────────────────────────

    def _detect_faces(self, image: np.ndarray) -> list[dict]:
        """Returns [{"bbox":[x,y,x2,y2], "confidence":float}, ...]."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # histogram equalisation for varying lighting
        gray = cv2.equalizeHist(gray)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        return [
            {"bbox": [int(x), int(y), int(x + w), int(y + h)], "confidence": 1.0}
            for (x, y, w, h) in faces
        ]

    async def detect_faces(self, image_path: str) -> list[dict]:
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {image_path}")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._detect_faces, img)

    # ── registration ──────────────────────────────────────────────

    def _register_face(self, name: str, image_path: str) -> dict:
        if not HAS_FACE_RECOG:
            raise RuntimeError("face_recognition library is not installed (dlib required)")
        img = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(img)
        if len(encodings) == 0:
            raise ValueError("No face found in image")

        # Check if this name is already registered — reuse user_id if so
        existing_id = self._lookup_user_id(name)
        if existing_id:
            user_id = existing_id
        else:
            user_id = uuid.uuid4().hex[:12]

        encoding = encodings[0]
        np.save(str(self._encodings_path(user_id)), encoding)
        self.known_faces[user_id] = [encoding]

        # persist user profile
        users = self._load_users()
        users[user_id] = {"name": name, "registered_at": _now_iso()}
        self._save_users(users)
        self._user_profiles = users

        self.tracker.record_drink(user_id)  # warm up user entry
        return {"user_id": user_id, "name": name, "encoding_shape": list(encoding.shape)}

    async def register_face(self, name: str, image_path: str) -> dict:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._register_face, name, image_path)

    # ── recognition ───────────────────────────────────────────────

    def _recognize(self, image: np.ndarray) -> dict:
        if not self.known_faces:
            return {"recognized": False}

        # get face locations with face_recognition (more robust than haar)
        if HAS_FACE_RECOG:
            # face_recognition uses RGB
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            locations = face_recognition.face_locations(rgb)
            if not locations:
                return {"recognized": False}
            encodings = face_recognition.face_encodings(rgb, locations)
        else:
            # fallback: haar detection, no encoding comparison
            faces = self._detect_faces(image)
            if not faces:
                return {"recognized": False}
            return {
                "recognized": False,
                "details": "face_recognition not available; install dlib for identification",
            }

        for enc, loc in zip(encodings, locations):
            for user_id, known_enc_list in self.known_faces.items():
                distances = face_recognition.face_distance(known_enc_list, enc)
                min_dist = float(distances.min())
                if min_dist < 0.5:  # threshold: lower = stricter
                    top, right, bottom, left = loc
                    name = self._get_user_name(user_id)
                    return {
                        "recognized": True,
                        "user_id": user_id,
                        "name": name,
                        "confidence": round(1.0 - min_dist, 3),
                        "bbox": [float(left), float(top), float(right), float(bottom)],
                    }

        return {"recognized": False}

    async def recognize(self, image_path: str) -> dict:
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {image_path}")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._recognize, img)

    # ── drinking check ────────────────────────────────────────────

    @staticmethod
    def _detect_cup_near_mouth(image: np.ndarray, face_bbox: list[int]) -> tuple[bool, float]:
        """
        Check for cup/container below the mouth using HoughCircles + colour cues.
        Returns (is_drinking, confidence).
        """
        x, y, x2, y2 = face_bbox
        fh = y2 - y  # face height
        fw = x2 - x  # face width

        # Region of interest: below nose, wider than face to include hands
        mouth_top = int(y + fh * 0.55)
        mouth_bottom = int(y + fh * 1.8)
        roi_x1 = max(0, int(x - fw * 0.3))
        roi_x2 = int(x2 + fw * 0.3)
        roi_y1 = max(0, mouth_top)
        roi_y2 = min(image.shape[0], mouth_bottom)

        roi = image[roi_y1:roi_y2, roi_x1:roi_x2]
        if roi.size == 0:
            return False, 0.0

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)

        # HoughCircles for cup/rim detection
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=30,
            param1=50,
            param2=25,
            minRadius=int(fw * 0.08),
            maxRadius=int(fw * 0.5),
        )

        if circles is not None:
            # found a circular object — likely cup rim
            confidence = min(1.0, len(circles[0]) * 0.4)
            return True, confidence

        # Fallback: detect hand-to-mouth via skin colour in mouth area
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        # skin colour ranges (broad, tuned for normal & East-Asian skin tones)
        skin_mask = cv2.inRange(hsv, np.array([0, 20, 70]), np.array([25, 170, 255]))
        skin_ratio = np.count_nonzero(skin_mask) / skin_mask.size

        if skin_ratio > 0.25:
            return True, 0.5

        return False, 0.0

    def _check_drinking_sync(self, image_path: str) -> dict:
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {image_path}")

        face_results = self._detect_faces(img)
        if not face_results:
            return {
                "is_drinking": False,
                "confidence": 0.0,
                "person_name": None,
                "last_drink_time": None,
                "minutes_since_last_drink": None,
                "needs_reminder": False,
            }

        # Pick the largest face as primary
        best = max(face_results, key=lambda f: (f["bbox"][2] - f["bbox"][0]) * (f["bbox"][3] - f["bbox"][1]))
        bbox = best["bbox"]

        is_drinking, confidence = self._detect_cup_near_mouth(img, bbox)

        # Try to identify
        user_id = None
        person_name = None
        if self.known_faces:
            rec = self._recognize(img)
            if rec.get("recognized"):
                user_id = rec["user_id"]
                person_name = rec["name"]

        result: dict = {
            "is_drinking": is_drinking,
            "confidence": round(confidence, 2),
            "user_id": user_id,
            "person_name": person_name,
        }

        if user_id:
            if is_drinking and confidence >= 0.3:
                self.tracker.record_drink(user_id)
                # Don't re-trigger for 5 min
                last = self.tracker.last_drink(user_id)
                if last and (datetime.now() - last).total_seconds() < 300:
                    is_drinking = True  # keep the flag

            last_drink = self.tracker.last_drink(user_id)
            mins_since = self.tracker.minutes_since_last_drink(user_id)
            needs = self.tracker.needs_reminder(user_id)

            result.update({
                "last_drink_time": last_drink.isoformat() if last_drink else None,
                "minutes_since_last_drink": round(mins_since, 1) if mins_since else None,
                "needs_reminder": needs,
            })
        else:
            result.update({
                "last_drink_time": None,
                "minutes_since_last_drink": None,
                "needs_reminder": False,
            })

        return result

    async def check_drinking(self, image_path: str) -> dict:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._check_drinking_sync, image_path)

    # ── drinking status ───────────────────────────────────────────

    def get_drinking_status(self, user_id: str) -> dict:
        last = self.tracker.last_drink(user_id)
        mins = self.tracker.minutes_since_last_drink(user_id)
        count = self.tracker.drink_count_today(user_id)
        needs = self.tracker.needs_reminder(user_id)
        name = self._get_user_name(user_id)

        return {
            "user_id": user_id,
            "person_name": name,
            "last_drink_time": last.isoformat() if last else None,
            "minutes_since_last_drink": round(mins, 1) if mins else None,
            "needs_reminder": needs,
            "drink_count_today": count,
        }

    # ── user management ──────────────────────────────────────────

    def list_users(self) -> list[dict]:
        users = self._load_users()
        result = []
        for uid, info in users.items():
            status = self.get_drinking_status(uid)
            result.append({
                "user_id": uid,
                "name": info.get("name", uid),
                "registered_at": info.get("registered_at"),
                "drink_count_today": status["drink_count_today"],
                "needs_reminder": status["needs_reminder"],
            })
        return result

    def unregister(self, user_id: str) -> bool:
        users = self._load_users()
        if user_id not in users:
            return False
        del users[user_id]
        self._save_users(users)
        self._user_profiles = users
        self.known_faces.pop(user_id, None)
        enc_path = self._encodings_path(user_id)
        if enc_path.exists():
            enc_path.unlink()
        return True

    # ── camera capture ────────────────────────────────────────────

    def _capture_from_camera(self, save_path: str) -> bool:
        """Capture one frame from the built-in camera. Return True on success."""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return False
        ret, frame = cap.read()
        cap.release()
        if ret:
            cv2.imwrite(save_path, frame)
            return True
        return False

    async def capture_from_camera(self, save_path: str) -> bool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._capture_from_camera, save_path)

    # ── convenience: capture + check in one call ──────────────────

    async def camera_check(self) -> dict:
        """Capture from camera, detect faces, check drinking, return combined result."""
        tmp_path = str(self.tracker.data_dir / "_latest_capture.jpg")
        ok = await self.capture_from_camera(tmp_path)
        if not ok:
            return {"error": "Camera not available"}

        faces = await self.detect_faces(tmp_path)
        drinking = await self.check_drinking(tmp_path)

        # if face detected but not recognized, try to recognize
        recognition = {}
        if faces:
            recognition = await self.recognize(tmp_path)

        return {
            "faces": faces,
            "recognition": recognition,
            "drinking": drinking,
            "image_path": tmp_path,
            "timestamp": _now_iso(),
        }


# ── module singleton ─────────────────────────────────────────────────

face_service = FaceService()
