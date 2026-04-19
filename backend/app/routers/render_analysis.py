"""
CuttOffl Backend - Render-Analyse.

Single Source of Truth für die Frage "was passiert beim Render?".
Sowohl der echte Renderer als auch die UI-Anzeige rufen dieselbe
Funktion `analyze_output` auf. Damit kann die UI-Anzeige nicht mehr
von dem abweichen, was der Renderer tatsächlich tut -- Frontend-
Duplikate der Regeln entfallen.

Liefert pro OutputProfile + Quelldatei:
  - mode: 'copy' | 'reencode'
  - reason: leer bei copy, sonst kurze Begründung
  - estimated_bytes: geschätzte Ausgabegröße
  - video_kbps, audio_kbps: zur Anzeige im Dialog
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import db
from app.models.edl import OutputProfile
from app.services.render_presets import RENDER_PRESETS, RenderPreset
from app.services.render_service import (
    _output_forces_reencode, _norm_vcodec,
)

router = APIRouter(prefix="/api/render", tags=["render"])


class AnalyzeRequest(BaseModel):
    output: OutputProfile
    source_file_id: Optional[str] = None
    # Dauer des zu rendernden Materials in Sekunden (Summe aller EDL-Clips).
    total_seconds: float = Field(ge=0.0)
    # Audio-Override-Infos (fuer UI-Anzeige); das Backend rendert beim
    # echten Job die volle EDL, die analyze-Route braucht nur die
    # Zaehlung der Clips und die mute_original-Flag.
    audio_track_count: int = 0
    mute_original: bool = False


class AnalyzeResponse(BaseModel):
    mode: str                     # 'copy' | 'reencode'
    reason: str                   # leer wenn mode='copy'
    estimated_bytes: int
    video_kbps: float
    audio_kbps: float
    # Zur Info: tatsächlich genutzte Werte, falls codec='source' aufgelöst
    # wurde. resolved_codec ist der echte Video-Codec, der beim Render
    # zum Einsatz käme.
    resolved_codec: str
    source_video_codec: Optional[str] = None
    source_audio_codec: Optional[str] = None
    source_bitrate_kbps: Optional[float] = None
    # Audio-Override-Status fuer den Export-Dialog.
    audio_mode: str = "original"   # 'original' | 'replaced' | 'mixed' | 'muted'
    audio_track_count: int = 0


def _parse_bitrate_kbps(s: Optional[str]) -> float:
    """'8M' -> 8000, '500k' -> 500, '1500000' -> 1500. None/'' -> 0."""
    if not s:
        return 0.0
    s = str(s).strip().lower()
    mult = 1.0
    if s.endswith("m"):
        mult = 1000.0
        s = s[:-1]
    elif s.endswith("k"):
        mult = 1.0
        s = s[:-1]
    else:
        mult = 1 / 1000.0  # nackte Zahl -> bit/s
    try:
        return float(s) * mult
    except ValueError:
        return 0.0


def _resolution_factor(resolution: Optional[str]) -> float:
    if not resolution:
        return 1.0
    r = resolution.lower()
    table = {
        "480p": 0.25, "720p": 0.50, "1080p": 1.00,
        "1440p": 1.75, "2160p": 4.00, "source": 1.0,
    }
    if r in table:
        return table[r]
    # "1280x720" etc.
    if "x" in r:
        try:
            w, h = r.split("x")
            px = int(w) * int(h)
            return px / (1920.0 * 1080.0)
        except Exception:
            return 1.0
    return 1.0


def _estimate_video_kbps(
    output: OutputProfile, source_kbps: Optional[float]
) -> float:
    """Zielt, wie viel kbit/s das Video beim Render haben würde.

    - bitrate explizit gesetzt: exakt dieser Wert
    - crf gesetzt: Hausnummer aus Auflösung + Codec + CRF
    - weder noch: bei Passthrough die Quell-Bitrate, sonst Fallback
    """
    if output.bitrate:
        return _parse_bitrate_kbps(output.bitrate)
    if output.crf is not None:
        crf = float(output.crf)
        # 1080p H.264 Basis: CRF 14 -> 50 Mbps, 23 -> 6 Mbps, 32 -> 0.8 Mbps
        kbps = 50_000.0 / (2 ** ((crf - 14) / 3))
        kbps *= _resolution_factor(output.resolution)
        if output.codec == "hevc":
            kbps *= 0.6
        return kbps
    # Kein Target -> Quell-Bitrate (falls bekannt)
    if source_kbps and source_kbps > 0:
        return source_kbps
    return 6000.0


def analyze_output(
    output: OutputProfile,
    source_meta: Optional[dict],
    total_seconds: float,
    audio_track_count: int = 0,
    mute_original: bool = False,
) -> AnalyzeResponse:
    """Die eine Funktion, die sowohl Render-Service als auch API nutzen."""
    forced, reason = _output_forces_reencode(output, source_meta)
    mode = "reencode" if forced else "copy"

    # Audio-Bitrate: bei copy die Quelle, sonst das Ziel-Setting.
    # Mute heißt keine Audio-Bytes.
    if output.audio_mute:
        audio_kbps = 0.0
    elif mode == "copy" or output.audio_codec == "copy":
        # Bei Copy: Audio-Bitrate aus Quelle (wenn bekannt), Fallback
        # aus dem Ziel-Setting.
        if source_meta and source_meta.get("audio_bitrate_kbps"):
            audio_kbps = float(source_meta["audio_bitrate_kbps"])
        else:
            audio_kbps = _parse_bitrate_kbps(output.audio_bitrate)
    else:
        audio_kbps = _parse_bitrate_kbps(output.audio_bitrate)

    # Quell-Bitrate für Copy-Modus und als Fallback
    source_bitrate_kbps: Optional[float] = None
    if source_meta:
        size = source_meta.get("size_bytes") or 0
        dur = source_meta.get("duration_s") or 0
        if size and dur and dur > 0:
            source_bitrate_kbps = (size * 8) / dur / 1000.0

    # Video-kbps
    if mode == "copy" and source_bitrate_kbps:
        # Bei Copy = Quelle. Minus Audio-Anteil (der ist in source_bitrate
        # mit drin).
        video_kbps = max(200.0, source_bitrate_kbps - (audio_kbps or 0))
    else:
        video_kbps = _estimate_video_kbps(output, source_bitrate_kbps)

    # Gesamtgröße
    if mode == "copy" and source_meta and source_meta.get("size_bytes") \
            and source_meta.get("duration_s"):
        # Quelle proportional zur Clip-Länge -- exakt, keine Schätzung.
        dur = float(source_meta["duration_s"])
        ratio = min(1.0, total_seconds / dur) if dur > 0 else 0.0
        estimated_bytes = int(float(source_meta["size_bytes"]) * ratio)
    else:
        total_kbits = (video_kbps + audio_kbps) * total_seconds
        overhead = 1.02 if output.container == "mp4" else 1.04
        estimated_bytes = int((total_kbits * 1000 / 8) * overhead)

    resolved = output.codec
    if resolved == "source" and source_meta:
        src = _norm_vcodec(source_meta.get("video_codec"))
        resolved = src if src in ("h264", "hevc") else "h264"

    # Audio-Modus ableiten: was der User beim Abspielen hoert.
    if audio_track_count > 0 and mute_original:
        audio_mode = "replaced"     # Override-Clips ersetzen Original
    elif audio_track_count > 0:
        audio_mode = "mixed"        # Override-Clips zusaetzlich zu Original
    elif mute_original:
        audio_mode = "muted"        # Nur Video, kein Ton
    else:
        audio_mode = "original"

    return AnalyzeResponse(
        mode=mode,
        reason=reason,
        estimated_bytes=estimated_bytes,
        video_kbps=round(video_kbps, 1),
        audio_kbps=round(audio_kbps, 1),
        resolved_codec=resolved,
        source_video_codec=(source_meta or {}).get("video_codec"),
        source_audio_codec=(source_meta or {}).get("audio_codec"),
        source_bitrate_kbps=(
            round(source_bitrate_kbps, 1) if source_bitrate_kbps else None
        ),
        audio_mode=audio_mode,
        audio_track_count=audio_track_count,
    )


@router.get("/presets", response_model=list[RenderPreset])
async def list_presets() -> list[RenderPreset]:
    """Alle Export-Presets. Frontend lädt sie einmal und rendert daraus
    die Schnellwahl-Kacheln. Presets sind backend-seitig definiert,
    damit sie auch von Skripten oder der Tour konsistent genutzt
    werden können -- und nicht im Frontend hart kodiert leben."""
    return RENDER_PRESETS


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    """Analyse eines Output-Profils gegen eine Quelldatei.

    Frontend ruft das bei jeder Dialog-Änderung auf (mit Debounce),
    um mode/reason/Größenschätzung konsistent mit dem echten Renderer
    anzuzeigen. Keine Dopplung der Regeln mehr.
    """
    source_meta: Optional[dict] = None
    if body.source_file_id:
        row = await db.fetch_one(
            """SELECT video_codec, audio_codec, width, height, fps,
                      size_bytes, duration_s
               FROM files WHERE id = ?""",
            (body.source_file_id,),
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Quelldatei nicht gefunden")
        source_meta = {
            "video_codec": row["video_codec"],
            "audio_codec": row["audio_codec"],
            "width": row["width"],
            "height": row["height"],
            "fps": row["fps"],
            "size_bytes": row["size_bytes"],
            "duration_s": row["duration_s"],
        }

    return analyze_output(
        body.output,
        source_meta,
        body.total_seconds,
        audio_track_count=body.audio_track_count,
        mute_original=body.mute_original,
    )
