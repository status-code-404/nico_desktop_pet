"""
API routes — thin HTTP layer, delegates to service/
"""

import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from server.config import settings
from server.schemas import (
    ChatRequest, ChatResponse,
    DrinkingStatusResponse, FaceDetectResponse, FaceRecognizeResponse,
    FaceRegisterRequest, FaceRegisterResponse, WaterDrinkingCheckResponse,
)
from service import chat as chat_svc
from service import face as face_svc
from service import voice as voice_svc

router = APIRouter()

# ═══════════════════════════════════════════════════════════ Chat

@router.delete("/api/v1/chat/history")
async def clear_chat_history():
    chat_svc.clear_history()
    return {"message": "history cleared"}

@router.post("/api/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        content = await chat_svc.send(req.message)
        return ChatResponse(message_id=uuid.uuid4().hex[:12], content=content)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")

@router.post("/api/v1/chat/stream")
async def chat_stream(req: ChatRequest):
    async def gen():
        try:
            async for chunk in chat_svc.stream(req.message):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {e}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

# ═══════════════════════════════════════════════════════════ Voice

@router.post("/api/v1/voice/transcribe")
async def voice_transcribe(file: UploadFile = File(...), language: Optional[str] = Form(None)):
    try:
        result = await voice_svc.transcribe(file)
        if settings.debug_voice:
            print(f"[debug:voice] STT: {result['text']!r}")
        return {"text": result["text"], "language": result["language"], "duration_s": result["duration_s"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/voice/chat", response_model=ChatResponse)
async def voice_chat(file: UploadFile = File(...), language: Optional[str] = Form(None)):
    try:
        reply = await voice_svc.chat(file)
        return ChatResponse(message_id=uuid.uuid4().hex[:12], content=reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/voice/tts")
async def voice_tts(text: str = Form(...)):
    """Stream TTS results: each line is JSON array of file paths for one batch."""
    try:
        async def stream():
            async for path in voice_svc.tts(text):
                import json
                yield json.dumps({"file": path}, ensure_ascii=False) + "\n"
        return StreamingResponse(stream(), media_type="application/x-ndjson")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/voice/chat/audio")
async def voice_chat_audio(file: UploadFile = File(...), language: Optional[str] = Form(None)):
    try:
        path = await voice_svc.chat_audio(file)
        return FileResponse(path, media_type="audio/wav", filename=f"nicole_{uuid.uuid4().hex[:8]}.wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════ Face

@router.post("/api/v1/face/detect", response_model=FaceDetectResponse)
async def face_detect(image_path: str):
    try:
        faces = await face_svc.detect(image_path)
        return FaceDetectResponse(faces=faces, face_count=len(faces))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/api/v1/face/register", response_model=FaceRegisterResponse)
async def face_register(req: FaceRegisterRequest):
    try:
        result = await face_svc.register(req.name, req.image_path)
        return FaceRegisterResponse(user_id=result["user_id"], name=result["name"],
            encoding_shape=result["encoding_shape"], message=f"Registered '{req.name}'")
    except FileNotFoundError as e: raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e: raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e: raise HTTPException(status_code=501, detail=str(e))

@router.post("/api/v1/face/recognize", response_model=FaceRecognizeResponse)
async def face_recognize(image_path: str):
    try:
        r = await face_svc.recognize(image_path)
        return FaceRecognizeResponse(**r)
    except FileNotFoundError as e: raise HTTPException(status_code=404, detail=str(e))

@router.post("/api/v1/face/drinking-check", response_model=WaterDrinkingCheckResponse)
async def drinking_check(image_path: str):
    try:
        r = await face_svc.check_drinking(image_path)
        return WaterDrinkingCheckResponse(**r)
    except FileNotFoundError as e: raise HTTPException(status_code=404, detail=str(e))

@router.get("/api/v1/face/drinking-status", response_model=DrinkingStatusResponse)
async def drinking_status(user_id: str):
    if user_id not in face_svc.face_service.known_faces:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    return DrinkingStatusResponse(**face_svc.drinking_status(user_id))

@router.get("/api/v1/face/users")
async def list_users():
    return {"users": face_svc.list_users()}

@router.delete("/api/v1/face/users/{user_id}")
async def unregister_user(user_id: str):
    if not face_svc.unregister(user_id):
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    return {"message": f"User '{user_id}' removed"}

@router.post("/api/v1/face/camera-check")
async def camera_check():
    r = await face_svc.camera_check()
    if "error" in r: raise HTTPException(status_code=503, detail=r["error"])
    return r
