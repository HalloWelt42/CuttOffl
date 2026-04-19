"""
CuttOffl Backend - Audio-Mix-Service.

Unabhaengig vom Video-Render: nimmt eine Liste AudioClips + Output-
Optionen (normalize, mono) und erzeugt daraus EINE finale WAV-Datei.
Das Ergebnis kann spaeter im Video-Render als einzelner Track
eingesetzt werden -- billigere ffmpeg-Kette, wiederverwendbar in
anderen Projekten, jederzeit downloadbar.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable, Optional

from app.services.ffmpeg_service import ffmpeg_binary

logger = logging.getLogger(__name__)


def _db_to_linear(db: float) -> float:
    return 10 ** (float(db or 0) / 20.0)


def _clip_duration(c) -> float:
    return max(0.05, float(c.src_end) - float(c.src_start))


def total_duration_s(audio_clips: list) -> float:
    """Laenge der Ziel-WAV: bis zum Ende des letzten Clips auf der
    Timeline. Ein Clip mit timeline_start=20, duration=5 reicht bis
    sec 25 -- egal wo andere Clips liegen."""
    if not audio_clips:
        return 0.0
    end = 0.0
    for c in audio_clips:
        e = float(c.timeline_start) + _clip_duration(c)
        if e > end:
            end = e
    return end


async def build_audio_mix_wav(
    audio_clips: list,
    audio_sources: dict[str, Path],
    dest: Path,
    normalize: bool = False,
    mono: bool = False,
    sample_rate: int = 48_000,
) -> float:
    """Baut aus den Clips eine einzelne WAV-Datei bei dest.
    Gibt die Gesamtdauer in Sekunden zurueck.

    audio_clips: Liste AudioClip-artiger Objekte (src_start, src_end,
      timeline_start, gain_db, fade_in_s, fade_out_s, file_id).
    audio_sources: file_id -> Pfad-Mapping.
    normalize: EBU R128 loudnorm am Ende der Kette.
    mono: Stereo-auf-Mono-Downmix am Ende der Kette.
    """
    total_s = total_duration_s(audio_clips)
    if total_s <= 0:
        raise RuntimeError("Keine Audio-Clips zum Mixen.")

    dest.parent.mkdir(parents=True, exist_ok=True)

    # anullsrc als Basis-Laengen-Garant (sonst koennte amix kuerzer
    # ausfallen, falls alle Clips zu Beginn der Timeline sitzen).
    args: list[str] = [
        ffmpeg_binary(), "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi",
        "-t", f"{total_s:.3f}",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate={sample_rate}",
    ]

    inputs: list[tuple[int, object]] = []
    for clip in audio_clips:
        src = audio_sources.get(clip.file_id)
        if not src or not Path(src).exists():
            logger.warning(
                f"Audio-Mix: file_id={clip.file_id} nicht gefunden, "
                f"Clip uebersprungen"
            )
            continue
        args += ["-i", str(src)]
        inputs.append((len(inputs) + 1, clip))

    filter_parts: list[str] = []
    labels = ["[0:a]"]  # Stille-Basis, damit die Ziel-Laenge erhalten bleibt
    for idx, clip in inputs:
        src_start = float(clip.src_start)
        src_end = float(clip.src_end)
        dur = max(0.05, src_end - src_start)
        delay_ms = int(float(clip.timeline_start) * 1000)
        vol = _db_to_linear(clip.gain_db)
        parts = [
            f"[{idx}:a]atrim={src_start:.3f}:{src_end:.3f}",
            "asetpts=PTS-STARTPTS",
            f"aresample={sample_rate}:async=0:first_pts=0",
            "aformat=sample_fmts=fltp:channel_layouts=stereo",
            f"volume={vol:.4f}",
        ]
        if clip.fade_in_s and clip.fade_in_s > 0:
            parts.append(
                f"afade=t=in:st=0:d={float(clip.fade_in_s):.3f}"
            )
        if clip.fade_out_s and clip.fade_out_s > 0:
            fade_start = max(0.0, dur - float(clip.fade_out_s))
            parts.append(
                f"afade=t=out:st={fade_start:.3f}:"
                f"d={float(clip.fade_out_s):.3f}"
            )
        if delay_ms > 0:
            parts.append(f"adelay={delay_ms}|{delay_ms}")
        label = f"[c{idx}]"
        filter_parts.append(",".join(parts) + label)
        labels.append(label)

    pre_mix_label = "[premix]" if (normalize or mono) else "[mix]"
    filter_parts.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:"
        f"duration=longest:dropout_transition=0:normalize=0"
        f"{pre_mix_label}"
    )
    post: list[str] = []
    if mono:
        post.append("pan=mono|c0=.5*c0+.5*c1")
    if normalize:
        post.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    if post:
        filter_parts.append(f"{pre_mix_label}{','.join(post)}[mix]")

    args += [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[mix]",
        "-ac", "1" if mono else "2",
        "-ar", str(sample_rate),
        "-c:a", "pcm_s16le",
        str(dest),
    ]

    logger.info("ffmpeg-audio-mix-wav: " + " ".join(args))
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"Audio-Mix fehlgeschlagen: "
            f"{stderr.decode('utf-8', errors='replace').strip()}"
        )

    return total_s
