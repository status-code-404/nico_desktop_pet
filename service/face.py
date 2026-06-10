"""
Face service — detection, recognition, drinking monitoring.
Uses: core.vision.face
"""

from core.vision.face import face_service


async def detect(image_path: str) -> list:
    return await face_service.detect_faces(image_path)


async def register(name: str, image_path: str) -> dict:
    return await face_service.register_face(name, image_path)


async def recognize(image_path: str) -> dict:
    return await face_service.recognize(image_path)


async def check_drinking(image_path: str) -> dict:
    return await face_service.check_drinking(image_path)


def drinking_status(user_id: str) -> dict:
    return face_service.get_drinking_status(user_id)


def list_users() -> list:
    return face_service.list_users()


def unregister(user_id: str) -> bool:
    return face_service.unregister(user_id)


async def camera_check() -> dict:
    return await face_service.camera_check()
