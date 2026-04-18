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
nur frame-genaue Clips muessen transkodiert werden.
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


ProgressCb = Optional[Callable[[float, str], None]]


_RE_KV = re.compile(r"^([a-zA-Z_]+)=(.*)$")


# ---------------------------------------------------------------------------
# Encoder-Wahl
# ---------------------------------------------------------------------------

async def _pick_video_encoder(codec: str) -> tuple[str, list[str]]:
    """Gibt (Encoder-Name, zusaetzliche Codec-Flags) zurueck."""
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
    """Fuehrt ffmpeg aus und ruft on_out_seconds(sec) waehrend der Arbeit auf."""
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
    """Baut die Audio-Filterkette aus den Flags. None = kein Filter noetig.
    Reihenfolge: Mono-Downmix vor loudnorm, damit loudnorm auf dem
    finalen Mix rechnet."""
    filters = []
    if output.audio_mono:
        filters.append("pan=mono|c0=.5*c0+.5*c1")
    if output.audio_normalize:
        # Standard-Ziel nach EBU R128 -- ausreichend fuer Web/SocialMedia
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    return ",".join(filters) if filters else None


def _needs_reencode(clip: Clip, output: OutputProfile) -> bool:
    """Erzwingt Re-Encoding, wenn Audio-Filter aktiv sind -- sonst greifen
    die Filter nicht (copy-Mode kopiert den AV-Stream 1:1)."""
    if clip.mode == "reencode":
        return True
    if output.audio_mute or output.audio_normalize or output.audio_mono:
        return True
    return False


async def _build_clip(
    source: Path,
    clip: Clip,
    dest: Path,
    output: OutputProfile,
    encoder: str,
    encoder_flags: list[str],
    scale_vf: Optional[str],
    on_sec: Callable[[float], None],
) -> None:
    """Erzeugt genau ein Segment ins dest."""
    base = [ffmpeg_binary(), "-y", "-hide_banner", "-loglevel", "error"]
    reencode = _needs_reencode(clip, output)
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
        # Reencode: output-seek + Filter
        args = base + [
            "-ss", f"{clip.src_start:.3f}",
            "-to", f"{clip.src_end:.3f}",
            "-i", str(source),
            "-c:v", encoder, *encoder_flags,
        ]
        if output.bitrate:
            args += ["-b:v", output.bitrate]
        elif encoder in ("libx264", "libx265") and output.crf is not None:
            args += ["-crf", str(output.crf)]
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
    """Fuehrt alle Segmente per concat-Demuxer zu einem File zusammen (-c copy)."""
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
) -> Path:
    """Rendert die EDL gegen `source` und gibt den Pfad zum fertigen Video zurueck."""
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

    # Wenn alle Clips copy + keine Skalierung noetig + nur Container-kompatibel,
    # koennte man auf den Concat-Merge ohne Re-Encode auch alles belassen.
    # Das passiert hier automatisch, weil die Segmente dann bereits mit `-c copy` entstehen.

    segments: list[Path] = []
    done_sec = 0.0

    def make_segment_cb(clip_duration: float):
        def inner(clip_sec: float) -> None:
            pct = (done_sec + min(clip_sec, clip_duration)) / total
            if progress_cb is not None:
                progress_cb(max(0.0, min(pct, 0.999)), "rendering")
        return inner

    try:
        for i, clip in enumerate(edl.timeline):
            seg = work / f"seg_{i:04d}.{container}"
            await _build_clip(
                source=source,
                clip=clip,
                dest=seg,
                output=output,
                encoder=encoder,
                encoder_flags=encoder_flags,
                scale_vf=scale_vf,
                on_sec=make_segment_cb(clip.duration),
            )
            segments.append(seg)
            done_sec += clip.duration
            if progress_cb is not None:
                progress_cb(min(0.999, done_sec / total), "rendering")

        if progress_cb is not None:
            progress_cb(0.999, "merging")

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
        # work-Verzeichnis aufraeumen
        try:
            shutil.rmtree(work, ignore_errors=True)
        except Exception:
            pass

    if progress_cb is not None:
        progress_cb(1.0, "done")

    logger.info(f"Render fertig: {final} ({len(segments)} Segmente, {total:.2f}s gesamt)")
    return final
