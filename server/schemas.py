"""Pydantic data models."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FaceDetectResponse(BaseModel):
    faces: list[dict]
    face_count: int

class FaceRegisterRequest(BaseModel):
    name: str
    image_path: str

class FaceRegisterResponse(BaseModel):
    user_id: str
    name: str
    encoding_shape: list[int]
    message: str

class FaceRecognizeResponse(BaseModel):
    recognized: bool
    user_id: Optional[str] = None
    name: Optional[str] = None
    confidence: Optional[float] = None
    bbox: Optional[list[float]] = None

class WaterDrinkingCheckResponse(BaseModel):
    is_drinking: bool
    confidence: float
    user_id: Optional[str] = None
    person_name: Optional[str] = None
    last_drink_time: Optional[str] = None
    minutes_since_last_drink: Optional[float] = None
    needs_reminder: bool = False

class DrinkingStatusResponse(BaseModel):
    user_id: str
    person_name: str
    last_drink_time: Optional[str] = None
    minutes_since_last_drink: Optional[float] = None
    needs_reminder: bool
    drink_count_today: int

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    include_context: bool = True

class ChatResponse(BaseModel):
    message_id: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    character: str = "nicole"

class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Optional[str] = None
