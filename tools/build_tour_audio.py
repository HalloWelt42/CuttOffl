#!/usr/bin/env python3
"""
CuttOffl -- Tour-Audio bauen.

Liest data/tmp/tour-recording.json, das von der Backend-Middleware
waehrend einer Recorder-Session geschrieben wurde, und baut daraus
eine WAV-Datei mit:

- tts-Events:         Text -> MP3 aus data/tts-cache
- tour_audio-Events:  ID -> MP3 aus frontend/public/tour-audio
- video_play-Events:  file_id + start/stop -> Audio aus
                      data/originals/<file_id>.*

Audios werden nicht gekuerzt. Wenn sich Segmente ueberlappen wuerden,
schiebt sich das spaetere dahinter, die Gesamtlaenge waechst
entsprechend.

Ausgabe: notes/tour-audio.wav (notes/ ist gitignored).

Benutzung:
  ./tools/build_tour_audio.py [eingabe.json] [ausgabe.wav]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "tmp" / "tour-recording.json"
DEFAULT_OUTPUT = ROOT / "notes" / "tour-audio.wav"
ORIGINALS_DIR = ROOT / "data" / "originals"
TOUR_AUDIO_DIR = ROOT / "frontend" / "public" / "tour-audio"
TMP_DIR = ROOT / "data" / "tmp" / "tour-audio-build"

# Hash- und Sanitize-Logik direkt aus dem Backend.
sys.path.insert(0, str(ROOT / "backend"))
from app.routers.speak import (  # noqa: E402
    cache_path_for, sanitize_for_speech,
)

SAMPLE_RATE = 48_000
# Video-Ton unterhalb der TTS mischen, damit die Erklaerung oben steht.
VIDEO_GAIN_DB = -12.0


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def db_to_linear(db: float) -> float:
    return 10 ** (db / 20.0)


def media_duration_ms(path: Path) -> int:
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ], text=True).strip()
    return int(float(out) * 1000)


def find_original(file_id: str) -> Path | None:
    for p in ORIGINALS_DIR.glob(f"{file_id}.*"):
        return p
    return None


def find_tour_audio(audio_id: str) -> Path | None:
    p = TOUR_AUDIO_DIR / f"{audio_id}.mp3"
    return p if p.exists() else None


def extract_range(src: Path, start_s: float, duration_s: float,
                  cache_key: str) -> Path | None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    dst = TMP_DIR / f"{cache_key}.wav"
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start_s:.3f}",
        "-t", f"{duration_s:.3f}",
        "-i", str(src),
        "-vn", "-ac", "2", "-ar", str(SAMPLE_RATE),
        "-c:a", "pcm_s16le",
        str(dst),
    ]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        log(f"[warn] extract fehlgeschlagen fuer {src.name}: {e}")
        return None
    return dst


def build(input_path: Path, output_path: Path) -> None:
    if not input_path.exists():
        log(f"[fehler] Eingabedatei fehlt: {input_path}")
        sys.exit(1)
    events = json.loads(input_path.read_text("utf-8"))
    if not events:
        log("[fehler] Keine Events in der Aufnahme.")
        sys.exit(1)
    events.sort(key=lambda e: e.get("t_ms", 0))

    # Segment-Sammler: (start_ms, path, duration_ms, gain_db)
    segments: list[tuple[int, Path, int, float]] = []
    tts_cursor_ms = 0
    missing: list[tuple[float, str]] = []
    # Laufende video_play-Zuordnung: { file_id -> (t_ms_start, ffprobe-freier
    # Marker) }. Ein video_play-Event enthaelt zu Beginn nur den GET-Zeitpunkt.
    # Das Ende wird daraus abgeleitet, indem wir pro file_id die Folge-
    # Events beobachten: sobald ein anderer Event-Typ reinkommt oder ein
    # Range-Wechsel erkennbar waere, endet der laufende video_play.
    # Vereinfachung: Wir halten den zuletzt gesehenen video_play-Zeitpunkt
    # pro file_id und nehmen als Video-Dauer die Zeit bis zum naechsten
    # Event fuer die gleiche file_id (oder bis zum Ende).
    open_video: dict | None = None

    def flush_video(end_ms: float) -> None:
        nonlocal open_video
        if not open_video:
            return
        dur_ms = max(0.0, end_ms - open_video["t_ms"])
        if dur_ms >= 200:
            src = find_original(open_video["file_id"])
            if src is not None:
                cache_key = (f"video-{open_video['file_id'][:12]}-"
                             f"{int(open_video['t_ms'])}-{int(dur_ms)}")
                clip = extract_range(src, 0.0, dur_ms / 1000.0, cache_key)
                # Hinweis: start_s=0 -- wir wissen nur, _dass_ das Proxy-
                # Video geladen wurde, nicht die Abspielposition. Fuer eine
                # sinnvolle Rekonstruktion der Musik nehmen wir einfach
                # den Beginn der Datei.
                if clip is not None:
                    segments.append((
                        int(open_video["t_ms"]),
                        clip,
                        int(dur_ms),
                        VIDEO_GAIN_DB,
                    ))
        open_video = None

    for e in events:
        kind = e.get("kind")
        t_ms = float(e.get("t_ms", 0) or 0)

        if kind == "tts":
            raw = e.get("text", "") or ""
            text = sanitize_for_speech(raw)
            if not text:
                continue
            mp3 = cache_path_for(text)
            if not mp3.exists():
                missing.append((t_ms, f"[tts] {text[:60]}"))
                continue
            try:
                dur = media_duration_ms(mp3)
            except Exception as err:
                log(f"[warn] ffprobe fuer {mp3.name}: {err}")
                continue
            start = max(tts_cursor_ms, int(t_ms))
            segments.append((start, mp3, dur, 0.0))
            tts_cursor_ms = start + dur
            flush_video(t_ms)

        elif kind == "tour_audio":
            audio_id = e.get("tour_audio_id") or ""
            mp3 = find_tour_audio(audio_id)
            if mp3 is None:
                missing.append((t_ms, f"[tour] {audio_id}"))
                continue
            try:
                dur = media_duration_ms(mp3)
            except Exception as err:
                log(f"[warn] ffprobe fuer {mp3.name}: {err}")
                continue
            start = max(tts_cursor_ms, int(t_ms))
            segments.append((start, mp3, dur, 0.0))
            tts_cursor_ms = start + dur
            flush_video(t_ms)

        elif kind == "video_play":
            # neuer Video-Block. Einen laufenden schliessen, einen neuen oeffnen.
            flush_video(t_ms)
            open_video = {"t_ms": t_ms, "file_id": e.get("file_id")}

        elif kind == "tour_end":
            flush_video(t_ms)

    # Am Ende: falls noch ein video_play offen ist, bis zum letzten
    # bekannten Zeitpunkt laufen lassen.
    if open_video:
        last_t = events[-1].get("t_ms", open_video["t_ms"])
        flush_video(float(last_t))

    if not segments:
        log("[fehler] Keine verarbeitbaren Audio-/Video-Segmente.")
        if missing:
            log("Fehlende MP3s (erste 5):")
            for t_ms, txt in missing[:5]:
                log(f"  t={t_ms}ms  {txt!r}")
        sys.exit(1)

    total_ms = max(start + dur for start, _p, dur, _g in segments)
    tts_n = sum(1 for _s, _p, _d, g in segments if g == 0.0)
    vid_n = len(segments) - tts_n
    log(f"[info] {len(segments)} Segmente "
        f"({tts_n} Audio, {vid_n} Video), {total_ms/1000:.2f} s")

    # ffmpeg: anullsrc als Basis + adelay pro Segment.
    args = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi",
        "-t", f"{total_ms / 1000:.3f}",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate={SAMPLE_RATE}",
    ]
    for _s, path, _d, _g in segments:
        args += ["-i", str(path)]
    filter_parts = []
    labels = ["[0:a]"]
    for idx, (start, _path, _dur, gain_db) in enumerate(segments, start=1):
        vol = db_to_linear(gain_db)
        filter_parts.append(
            f"[{idx}:a]aresample={SAMPLE_RATE},"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"volume={vol:.4f},"
            f"adelay={start}|{start}[a{idx}]"
        )
        labels.append(f"[a{idx}]")
    filter_parts.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:"
        f"duration=longest:dropout_transition=0[out]"
    )
    args += [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[out]",
        "-ac", "2", "-ar", str(SAMPLE_RATE),
        "-c:a", "pcm_s16le",
        str(output_path),
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    log(f"[info] ffmpeg -> {output_path}")
    try:
        subprocess.check_call(args)
    except subprocess.CalledProcessError as e:
        log(f"[fehler] ffmpeg: {e}")
        sys.exit(2)

    if missing:
        log(f"[warn] {len(missing)} MP3s fehlten:")
        for t_ms, txt in missing[:10]:
            log(f"  t={t_ms}ms  {txt!r}")

    size_mb = output_path.stat().st_size / 1024 / 1024
    log(f"[fertig] {output_path}  ({size_mb:.1f} MB, {total_ms/1000:.1f} s)")


def main() -> None:
    inp = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT
    build(inp, out)


if __name__ == "__main__":
    main()
