"""
CuttOffl Backend - Render-Service.

Wandelt eine EDL in eine Folge von FFmpeg-Kommandos um:

  1. Pro Clip wird ein Segment ins tmp/<job-id>/ geschrieben.
       - mode = "copy"     → `-c copy` (kein Re-Encode, keyframe-genau)
       - mode = "reencode" → H.264/HEVC mit Zielprofil (frame-genau)
  2. Danach werden alle Segmente per concat-Demuxer gemergt.
  3. Fortschritt: Summe aller Clip-Durationen = Gesamtnenner; pro Clip
     wird der out_time_us an die Gesamtposition addiert und in Prozent
     an einen Callback geschickt.

Die Hybrid-Strategie macht den Unterschied: Clips zwischen zwei
Keyframe-Snaps bleiben bit-identisch (Sekunden pro Stunde Material),
nur frame-genaue Clips müssen transkodiert werden.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from pathlib import Path
from typing import Callable, Optional

from app.config import EXPORTS_DIR, TMP_DIR
from app.models.edl import EDL, Clip, OutputProfile
from app.services.ffmpeg_service import ffmpeg_binary
from app.services.hwaccel_service import detect_hw_encoder

logger = logging.getLogger(__name__)


# progress_cb(pct, phase, info=None). info enthaelt optionale Zusatz-
# Angaben für die Frontend-Pipeline-Anzeige: clip_index, clip_total,
# step (z. B. "preparing", "encoding_clip", "merging"), note (ein
# lesbarer Status-Text).
ProgressCb = Optional[Callable[[float, str, Optional[dict]], None]]


_RE_KV = re.compile(r"^([a-zA-Z_]+)=(.*)$")


# ---------------------------------------------------------------------------
# Encoder-Wahl
# ---------------------------------------------------------------------------

async def _pick_video_encoder(codec: str) -> tuple[str, list[str]]:
    """Gibt (Encoder-Name, zusätzliche Codec-Flags) zurück."""
    hw = await detect_hw_encoder()
    codec = codec.lower()
    if codec == "h264":
        if hw == "h264_videotoolbox":
            return "h264_videotoolbox", ["-allow_sw", "1"]
        if hw == "h264_v4l2m2m":
            return "h264_v4l2m2m", []
        return "libx264", ["-preset", "medium"]
    if codec == "hevc":
        if hw == "h264_videotoolbox":
            return "hevc_videotoolbox", []
        return "libx265", ["-preset", "medium"]
    return "libx264", ["-preset", "medium"]


async def _hw_decode_flags(source_codec: Optional[str]) -> list[str]:
    """HW-Decode-Flags vor dem -i, damit 4K HEVC auf Apple Silicon und
    Raspberry Pi nicht den Software-Dekoder zum Flaschenhals machen.
    Spiegelt die Logik aus proxy_service._hw_decode_flags, damit beide
    Pipelines gleich schnell sind."""
    if not source_codec:
        return []
    codec = source_codec.lower()
    supported_vt = {"hevc", "h265", "h264", "avc1", "prores",
                    "h263", "mpeg1video", "mpeg2video", "mpeg4", "vp9"}
    try:
        hw = await detect_hw_encoder()
    except Exception:
        hw = None
    if hw == "h264_videotoolbox" and codec in supported_vt:
        return ["-hwaccel", "videotoolbox"]
    if hw == "h264_v4l2m2m":
        if codec in ("h264", "avc1"):
            return ["-c:v", "h264_v4l2m2m"]
        if codec in ("hevc", "h265"):
            return ["-c:v", "hevc_v4l2m2m"]
    return []


def _scale_filter(resolution: str) -> Optional[str]:
    if not resolution or resolution == "source":
        return None
    m = re.fullmatch(r"(\d+)p", resolution)
    if m:
        return f"scale=-2:{int(m.group(1))}"
    m = re.fullmatch(r"(\d+)x(\d+)", resolution)
    if m:
        return f"scale={m.group(1)}:{m.group(2)}"
    return None


# ---------------------------------------------------------------------------
# FFmpeg-Aufruf mit Progress-Stream
# ---------------------------------------------------------------------------

async def _run_with_progress(
    args: list[str],
    on_out_seconds: Callable[[float], None],
) -> int:
    """Führt ffmpeg aus und ruft on_out_seconds(sec) während der Arbeit auf."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None
    current: dict = {}
    try:
        async for line in proc.stdout:
            text = line.decode("utf-8", errors="replace").strip()
            m = _RE_KV.match(text)
            if not m:
                continue
            key, value = m.group(1), m.group(2)
            current[key] = value
            if key == "progress":
                try:
                    out_us = int(current.get("out_time_us", "0") or 0)
                except ValueError:
                    out_us = 0
                on_out_seconds(out_us / 1_000_000.0)
                current.clear()
                if value == "end":
                    break
    finally:
        rc = await proc.wait()
    if rc != 0:
        err = ""
        if proc.stderr is not None:
            err = (await proc.stderr.read()).decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg exit {rc}: {err.strip()}")
    return rc


# ---------------------------------------------------------------------------
# Clip-Build + Concat + Hauptablauf
# ---------------------------------------------------------------------------

def _audio_filter_chain(output: OutputProfile) -> Optional[str]:
    """Baut die Audio-Filterkette aus den Flags. None = kein Filter nötig.
    Reihenfolge: Mono-Downmix vor loudnorm, damit loudnorm auf dem
    finalen Mix rechnet."""
    filters = []
    if output.audio_mono:
        filters.append("pan=mono|c0=.5*c0+.5*c1")
    if output.audio_normalize:
        # Standard-Ziel nach EBU R128 -- ausreichend für Web/SocialMedia
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    return ",".join(filters) if filters else None


# Codec-Aliasse: ffprobe meldet "hevc", manche Container "h265"; unser
# Output-Profil kennt nur h264/hevc. Hier normalisieren wir, damit
# Gleich-Vergleiche ehrlich sind.
def _norm_vcodec(c: Optional[str]) -> str:
    if not c:
        return ""
    c = c.lower().strip()
    if c in ("hevc", "h265", "x265"):
        return "hevc"
    if c in ("h264", "avc", "avc1", "x264"):
        return "h264"
    return c


def _norm_acodec(c: Optional[str]) -> str:
    if not c:
        return ""
    return c.lower().strip()


def _output_forces_reencode(
    output: OutputProfile, source_meta: Optional[dict]
) -> tuple[bool, str]:
    """Entscheidet auf Profil-Ebene, ob dieses Ziel-Profil Re-Encoding
    fordert. Gibt (True/False, Grund) zurück.

    Copy-Mode kopiert den AV-Stream 1:1 -- Auflösung, Codec, Bitrate,
    Audio-Codec und Audio-Filter werden dann IGNORIERT. Das macht einen
    Render "in Sekunden fertig", obwohl der User ein anderes Ziel-
    Profil gewählt hat. Deshalb prüfen wir hier streng:
      - Auflösung ≠ "source"               → skalieren, geht nicht mit copy
      - Bitrate explizit gesetzt           → greift nur beim Transcode
      - Ziel-Codec ≠ Quell-Codec           → muss transkodiert werden
      - Ziel-Audio-Codec ≠ Quell-Audio     → muss transkodiert werden
      - Audio-Filter (mute/norm/mono)      → braucht Transcode
    """
    if output.audio_mute or output.audio_normalize or output.audio_mono:
        return True, "Audio-Filter aktiv"
    if output.resolution and output.resolution != "source":
        return True, f"Zielaufloesung {output.resolution}"
    if output.bitrate:
        return True, f"Ziel-Bitrate {output.bitrate}"
    if source_meta is not None:
        src_v = _norm_vcodec(source_meta.get("video_codec"))
        dst_v = _norm_vcodec(output.codec)
        if src_v and dst_v and src_v != dst_v:
            return True, f"Video-Codec-Wechsel {src_v}->{dst_v}"
        # Audio: "copy" in den Audio-Codec-Einstellungen umgeht jeden
        # Wechsel; sonst vergleichen wir die Codec-Namen.
        if output.audio_codec != "copy":
            src_a = _norm_acodec(source_meta.get("audio_codec"))
            dst_a = _norm_acodec(output.audio_codec)
            if src_a and dst_a and src_a != dst_a:
                return True, f"Audio-Codec-Wechsel {src_a}->{dst_a}"
    return False, ""


def _needs_reencode(
    clip: Clip,
    output: OutputProfile,
    profile_forces: bool = False,
) -> bool:
    """Entscheidet pro Clip, ob transkodiert werden muss. Zusätzlich zu
    Clip-eigenem mode='reencode' und Audio-Filter wirkt hier der
    profile_forces-Flag -- wenn das Output-Profil eh schon reencode
    erzwingt, müssen *alle* Clips transkodieren, damit der finale
    concat-Demuxer homogen kompatible Streams bekommt."""
    if clip.mode == "reencode":
        return True
    if output.audio_mute or output.audio_normalize or output.audio_mono:
        return True
    if profile_forces:
        return True
    return False


def _quality_args(encoder: str, output: OutputProfile) -> list[str]:
    """Mappt Bitrate/CRF auf encoder-spezifische Flags.

    - libx264/libx265: -b:v oder -crf
    - h264_videotoolbox/hevc_videotoolbox: -b:v oder -q:v (kennen kein
      -crf). CRF 0-51 -> q:v 100-0 linear gemappt (50 ≈ q 51, 23 ≈ 55).
    - h264_v4l2m2m: nur -b:v (Pi-HW-Encoder kennt keine CRF-artige
      Quality-Steuerung, Default ist hartes Bitrate-Target).
    """
    if output.bitrate:
        return ["-b:v", output.bitrate]
    if output.crf is None:
        return []
    crf = int(output.crf)
    if encoder in ("libx264", "libx265"):
        return ["-crf", str(crf)]
    if encoder in ("h264_videotoolbox", "hevc_videotoolbox"):
        # Apple-VT-Quality: 0-100 (100 = verlustfrei). Wir bilden
        # sinnvoll ab: CRF 18 -> q 75, 23 -> q 65, 28 -> q 55.
        q = max(0, min(100, 100 - crf * 2))
        return ["-q:v", str(q)]
    if encoder == "h264_v4l2m2m":
        # Fallback: ohne Bitrate kein Target -- geben wir eine sinnvolle
        # Default-Bitrate an, damit der Pi-Encoder nicht floatet.
        return ["-b:v", "6M"]
    return []


async def _build_clip(
    source: Path,
    clip: Clip,
    dest: Path,
    output: OutputProfile,
    encoder: str,
    encoder_flags: list[str],
    scale_vf: Optional[str],
    on_sec: Callable[[float], None],
    profile_forces_reencode: bool = False,
    source_codec: Optional[str] = None,
) -> None:
    """Erzeugt genau ein Segment ins dest."""
    base = [ffmpeg_binary(), "-y", "-hide_banner", "-loglevel", "error"]
    reencode = _needs_reencode(clip, output, profile_forces_reencode)
    hw_flags = await _hw_decode_flags(source_codec)
    # Bei copy-Mode OHNE Filter: schnelles verlustfreies Schneiden
    if not reencode:
        args = base + [
            "-ss", f"{clip.src_start:.3f}",
            "-to", f"{clip.src_end:.3f}",
            "-i", str(source),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-progress", "pipe:1", "-nostats",
            str(dest),
        ]
    else:
        # Reencode mit HW-Decode vor dem -i. Bei 4K HEVC spart das
        # Faktor 5-20 Rechenzeit gegenueber Software-Decode.
        args = base + [
            *hw_flags,
            "-ss", f"{clip.src_start:.3f}",
            "-to", f"{clip.src_end:.3f}",
            "-i", str(source),
            "-c:v", encoder, *encoder_flags,
            *_quality_args(encoder, output),
        ]
        if scale_vf:
            args += ["-vf", scale_vf]
        # Audio-Teil: komplette Stummschaltung via -an, sonst Codec +
        # Bitrate + optionale Filterkette (Mono/loudnorm).
        audio_args: list[str] = []
        if output.audio_mute:
            audio_args += ["-an"]
        else:
            audio_args += ["-c:a", output.audio_codec, "-b:a", output.audio_bitrate]
            chain = _audio_filter_chain(output)
            if chain:
                audio_args += ["-af", chain]
        args += [
            "-pix_fmt", "yuv420p",
            *audio_args,
            "-progress", "pipe:1", "-nostats",
            str(dest),
        ]
    await _run_with_progress(args, on_sec)


async def _concat_segments(segments: list[Path], dest: Path) -> None:
    """Führt alle Segmente per concat-Demuxer zu einem File zusammen (-c copy)."""
    list_file = dest.with_suffix(".list.txt")
    with list_file.open("w", encoding="utf-8") as f:
        for s in segments:
            f.write(f"file '{s.as_posix()}'\n")
    args = [
        ffmpeg_binary(), "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(dest),
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    list_file.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"concat fehlgeschlagen: {stderr.decode('utf-8', errors='replace')}"
        )


async def render_edl(
    source: Path,
    edl: EDL,
    job_id: str,
    progress_cb: ProgressCb = None,
    filename_suffix: str = "",
    source_meta: Optional[dict] = None,
) -> Path:
    """Rendert die EDL gegen `source` und gibt den Pfad zum fertigen Video zurück.

    source_meta: {video_codec, audio_codec, width, height, fps} -- wird
    benoetigt, um ehrlich zu entscheiden, ob der Copy-Mode reicht oder
    das Ziel-Profil Transcoding erzwingt.
    """
    if not edl.timeline:
        raise RuntimeError("EDL ist leer")
    if not source.exists():
        raise RuntimeError(f"Quelldatei fehlt: {source}")

    work = TMP_DIR / f"render-{job_id}"
    work.mkdir(parents=True, exist_ok=True)

    total = sum(c.duration for c in edl.timeline)
    if total <= 0:
        raise RuntimeError("EDL-Gesamtdauer ist 0")

    output = edl.output
    container = output.container
    encoder, encoder_flags = await _pick_video_encoder(output.codec)
    scale_vf = _scale_filter(output.resolution)

    # Profil-Ebene: erzwingt das Ziel-Profil ein Re-Encode (Skalierung,
    # Codec-Wechsel, Ziel-Bitrate, Audio-Filter)? Dann alle Clips
    # transkodieren -- der concat-Demuxer braucht homogene Streams.
    profile_forces, reason = _output_forces_reencode(output, source_meta)
    if profile_forces:
        logger.info(f"Render erzwingt Reencode: {reason}")
    else:
        logger.info(
            "Render bleibt im Copy-Mode -- Ziel-Profil passt zur Quelle"
        )

    segments: list[Path] = []
    done_sec = 0.0
    n_clips = len(edl.timeline)

    if progress_cb is not None:
        progress_cb(
            0.0, "preparing",
            {"clip_index": 0, "clip_total": n_clips, "step": "preparing",
             "note": f"Vorbereiten: Encoder {encoder}, {n_clips} Clip(s)"},
        )

    def make_segment_cb(idx: int, clip_duration: float, mode: str):
        def inner(clip_sec: float) -> None:
            pct = (done_sec + min(clip_sec, clip_duration)) / total
            if progress_cb is not None:
                progress_cb(
                    max(0.0, min(pct, 0.999)), "rendering",
                    {"clip_index": idx + 1, "clip_total": n_clips,
                     "step": "encoding_clip",
                     "note": f"Clip {idx + 1}/{n_clips} ({mode})"},
                )
        return inner

    try:
        for i, clip in enumerate(edl.timeline):
            seg = work / f"seg_{i:04d}.{container}"
            mode = "copy" if not _needs_reencode(clip, output, profile_forces) else "reencode"
            if progress_cb is not None:
                progress_cb(
                    min(0.999, done_sec / total), "rendering",
                    {"clip_index": i + 1, "clip_total": n_clips,
                     "step": "encoding_clip",
                     "note": f"Clip {i + 1}/{n_clips} startet ({mode})"},
                )
            await _build_clip(
                source=source,
                clip=clip,
                dest=seg,
                output=output,
                encoder=encoder,
                encoder_flags=encoder_flags,
                scale_vf=scale_vf,
                on_sec=make_segment_cb(i, clip.duration, mode),
                profile_forces_reencode=profile_forces,
                source_codec=(source_meta or {}).get("video_codec"),
            )
            segments.append(seg)
            done_sec += clip.duration
            if progress_cb is not None:
                progress_cb(
                    min(0.999, done_sec / total), "rendering",
                    {"clip_index": i + 1, "clip_total": n_clips,
                     "step": "clip_done",
                     "note": f"Clip {i + 1}/{n_clips} fertig"},
                )

        if progress_cb is not None:
            progress_cb(
                0.999, "merging",
                {"clip_index": n_clips, "clip_total": n_clips,
                 "step": "merging", "note": "Segmente zusammenfuehren"},
            )

        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        # Dateiname darf die UUID behalten, aber bei Einzel-Clip-Render wird
        # noch ein Marker eingefuegt (zum Unterscheiden in exports/).
        suffix_part = f"-{filename_suffix}" if filename_suffix else ""
        final = EXPORTS_DIR / f"{job_id}{suffix_part}.{container}"

        if len(segments) == 1:
            shutil.move(str(segments[0]), str(final))
        else:
            await _concat_segments(segments, final)

    finally:
        # work-Verzeichnis aufräumen
        try:
            shutil.rmtree(work, ignore_errors=True)
        except Exception:
            pass

    if progress_cb is not None:
        progress_cb(1.0, "done")

    logger.info(f"Render fertig: {final} ({len(segments)} Segmente, {total:.2f}s gesamt)")
    return final
