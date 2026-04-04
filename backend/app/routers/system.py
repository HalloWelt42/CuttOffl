"""
CuttOffl Backend - System-Router.

Health-Check, Version, HW-Info.
"""

from fastapi import APIRouter

from app.config import APP_NAME, HOST, PORT, VERSION
from app.models.schemas import PingResponse
from app.services.ffmpeg_service import get_ffmpeg_version
from app.services.hwaccel_service import detect_hw_encoder

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    hw = await detect_hw_encoder()
    ff_version = await get_ffmpeg_version()
    return PingResponse(
        app=APP_NAME,
        version=VERSION,
        status="ok",
        host=HOST,
        port=PORT,
        hw_encoder=hw,
        ffmpeg_version=ff_version,
    )
