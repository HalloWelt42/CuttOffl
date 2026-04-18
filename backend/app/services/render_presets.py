"""
CuttOffl Backend - Render-Presets.

Die eine Definition der Export-Presets. Frontend lädt sie per
GET /api/render/presets -- dadurch sind Presets nicht mehr im Frontend
hart kodiert und können von beiden Seiten (UI und Skripte/Tour) aus
derselben Quelle bedient werden.

Die Ziel-Bitraten orientieren sich an offiziellen Empfehlungen
(YouTube SDR 30 fps, Instagram, TikTok). Wo keine Empfehlungen
existieren (X, generisch), nehmen wir Werte, die in der Praxis gut
aussehen und nicht unnötig Platz fressen.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.edl import OutputProfile


class RenderPreset(BaseModel):
    """Ein Preset beschreibt genau einen sinnvollen OutputProfile-Satz
    plus Metadaten für die UI (Icon, Farbe, Titel, Text)."""
    id: str
    icon: str                      # Font-Awesome-Klasse
    color: str                     # Hex-Farbe (UI-Akzent)
    title: str
    note: str                      # Einzeiler unter dem Titel
    profile: OutputProfile
    hint: Optional[str] = None     # Optionaler längerer Erklärungstext


# ---------------------------------------------------------------------------
# Preset-Liste
# ---------------------------------------------------------------------------

_YOUTUBE_1080 = RenderPreset(
    id="youtube-1080",
    icon="fa-brands fa-youtube",
    color="#FF0033",
    title="YouTube 1080p",
    note="1920x1080, H.264, 8 Mbit/s -- YouTube-Standard",
    profile=OutputProfile(
        codec="h264", container="mp4", resolution="1080p",
        bitrate="8M", crf=None,
        audio_codec="aac", audio_bitrate="192k",
    ),
)

_YOUTUBE_4K = RenderPreset(
    id="youtube-4k",
    icon="fa-brands fa-youtube",
    color="#FF0033",
    title="YouTube 4K",
    note="3840x2160, HEVC, 35 Mbit/s -- für hochaufgelöstes Material",
    profile=OutputProfile(
        codec="hevc", container="mp4", resolution="2160p",
        bitrate="35M", crf=None,
        audio_codec="aac", audio_bitrate="192k",
    ),
)

_REEL = RenderPreset(
    id="reel",
    icon="fa-brands fa-tiktok",
    color="#25F4EE",
    title="Reel / TikTok",
    note="1080p, H.264, 6 Mbit/s, Lautheit normalisiert",
    profile=OutputProfile(
        codec="h264", container="mp4", resolution="1080p",
        bitrate="6M", crf=None,
        audio_codec="aac", audio_bitrate="160k",
        audio_normalize=True,
    ),
    hint=("Schneide das Video vorher hochkant (9:16) im Editor zu -- "
          "CuttOffl dreht oder croppt noch nicht automatisch."),
)

_INSTAGRAM = RenderPreset(
    id="instagram-feed",
    icon="fa-brands fa-instagram",
    color="#E4405F",
    title="Instagram Feed",
    note="1080p, H.264, 5 Mbit/s -- auch für 1:1 geeignet",
    profile=OutputProfile(
        codec="h264", container="mp4", resolution="1080p",
        bitrate="5M", crf=None,
        audio_codec="aac", audio_bitrate="160k",
        audio_normalize=True,
    ),
)

_X = RenderPreset(
    id="x-twitter",
    icon="fa-brands fa-x-twitter",
    color="#E5E5E5",
    title="X / Twitter",
    note="720p, H.264, 5 Mbit/s -- unter der 512-MB-Grenze",
    profile=OutputProfile(
        codec="h264", container="mp4", resolution="720p",
        bitrate="5M", crf=None,
        audio_codec="aac", audio_bitrate="128k",
        audio_normalize=True,
    ),
)

_PODCAST = RenderPreset(
    id="podcast",
    icon="fa-solid fa-microphone",
    color="#FF7043",
    title="Podcast / Stimme",
    note="480p, H.264, 800 kbit/s, Mono + Lautheit normalisiert",
    profile=OutputProfile(
        codec="h264", container="mp4", resolution="480p",
        bitrate="800k", crf=None,
        audio_codec="aac", audio_bitrate="96k",
        audio_normalize=True, audio_mono=True,
    ),
)

_WEB = RenderPreset(
    id="web-compact",
    icon="fa-solid fa-leaf",
    color="#10B981",
    title="Web kompakt",
    note="720p, H.264 CRF 26 -- klein, lädt schnell",
    profile=OutputProfile(
        codec="h264", container="mp4", resolution="720p",
        bitrate=None, crf=26,
        audio_codec="aac", audio_bitrate="128k",
    ),
)

_ARCHIVE = RenderPreset(
    id="archive",
    icon="fa-solid fa-box-archive",
    color="#D4A574",
    title="Archiv",
    note="Quell-Auflösung, HEVC CRF 18 -- sehr hohe Qualität",
    profile=OutputProfile(
        codec="hevc", container="mp4", resolution="source",
        bitrate=None, crf=18,
        audio_codec="aac", audio_bitrate="256k",
    ),
)

_PASSTHROUGH = RenderPreset(
    id="passthrough",
    icon="fa-solid fa-scissors",
    color="#94A3B8",
    title="Nur schneiden",
    note="Quelle unverändert durchreichen -- keyframe-genau, kein Reencode",
    profile=OutputProfile(
        codec="source", container="mp4", resolution="source",
        bitrate=None, crf=None,
        audio_codec="copy", audio_bitrate="160k",
    ),
    hint=("Schneidet nur an Keyframes. Kein Qualitätsverlust, "
          "sekundenschneller Export. Das Video bleibt 1:1 wie die Quelle."),
)


RENDER_PRESETS: list[RenderPreset] = [
    _YOUTUBE_1080, _YOUTUBE_4K, _REEL, _INSTAGRAM, _X,
    _PODCAST, _WEB, _ARCHIVE, _PASSTHROUGH,
]


def get_preset(preset_id: str) -> Optional[RenderPreset]:
    return next((p for p in RENDER_PRESETS if p.id == preset_id), None)
