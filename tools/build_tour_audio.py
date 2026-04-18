#!/usr/bin/env python3
"""
CuttOffl -- Tour-Audio bauen.

Liest data/tmp/tour-recording.json (wird vom Frontend waehrend einer
Tour-Aufnahme geschrieben, wenn die URL ?tour_record=1 gesetzt war)
und baut daraus eine einzige WAV-Datei mit zwei Quell-Typen:

1. TTS-Audios (audio_start-Events)
     Die MP3 wird im TTS-Cache gefunden ueber
     cache_path_for(sanitize_for_speech(text)). Der Audio laeuft
     immer voll durch -- wenn der naechste TTS-Start vor dem Ende
     des vorigen kaeme, schiebt sich der naechste dahinter.

2. Video-Audios (video_play + video_stop-Events)
     Waehrend der Tour laeuft im Editor das Demo-Video. Dessen
     Originalton wird aus data/originals/<file_id>.* per ffmpeg
     ausgeschnitten (von start_s bis stop_s) und an t_ms in den
     Mix gelegt. Damit TTS klar verstaendlich bleibt, werden
     Video-Audio-Segmente leiser gemischt (VIDEO_GAIN_DB).

Ausgabe: notes/tour-audio.wav

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
TMP_DIR = ROOT / "data" / "tmp" / "tour-audio-build"

# Hash- und Sanitize-Logik kommt direkt aus dem Backend -- keine
# Duplikation, keine Drift.
sys.path.insert(0, str(ROOT / "backend"))
from app.routers.speak import (  # noqa: E402
    cache_path_for, sanitize_for_speech,
)

SAMPLE_RATE = 48_000
# Video-Ton leiser mischen, damit TTS klar oben steht.
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
    # Erweiterung ist unbekannt; probiere gaengige Container.
    for p in ORIGINALS_DIR.glob(f"{file_id}.*"):
        return p
    return None


def extract_video_audio(file_id: str, start_s: float, duration_s: float) -> Path | None:
    """Schneidet die Tonspur aus der Quelldatei von start_s bis
    start_s + duration_s in eine tmp-WAV. Gecached -- identische
    Parameter liefern denselben Pfad, ohne neu zu extrahieren."""
    src = find_original(file_id)
    if src is None:
        log(f"[warn] Quelldatei fuer file_id={file_id} nicht in {ORIGINALS_DIR}")
        return None
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    key = f"{file_id[:12]}-{int(start_s*1000)}-{int(duration_s*1000)}.wav"
    dst = TMP_DIR / key
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start_s:.3f}",
        "-t", f"{duration_s:.3f}",
        "-i", str(src),
        "-vn",
        "-ac", "2",
        "-ar", str(SAMPLE_RATE),
        "-c:a", "pcm_s16le",
        str(dst),
    ]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        log(f"[warn] video-audio-extract fehlgeschlagen fuer {src.name}: {e}")
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

    # --- Segmente sammeln ---------------------------------------------
    # Jedes Segment = (start_ms, audio_path, duration_ms, gain_db).
    # TTS und Video-Audio landen im selben Mix.
    segments: list[tuple[int, Path, int, float]] = []
    tts_cursor_ms = 0   # Schutz gegen ueberlappende TTS (Video darf ueberlappen)
    missing_tts: list[tuple[float, str]] = []
    active_video: dict | None = None

    for e in events:
        kind = e.get("kind")
        t_ms = float(e.get("t_ms", 0) or 0)

        if kind == "audio_start":
            raw = e.get("text", "") or ""
            text = sanitize_for_speech(raw)
            if not text:
                continue
            mp3 = cache_path_for(text)
            if not mp3.exists():
                missing_tts.append((t_ms, text[:60]))
                continue
            try:
                dur = media_duration_ms(mp3)
            except Exception as err:
                log(f"[warn] ffprobe fehlgeschlagen fuer {mp3.name}: {err}")
                continue
            start = max(tts_cursor_ms, int(t_ms))
            segments.append((start, mp3, dur, 0.0))
            tts_cursor_ms = start + dur

        elif kind == "video_play":
            active_video = {
                "t_ms": t_ms,
                "file_id": e.get("file_id"),
                "start_s": float(e.get("start_s") or 0.0),
            }

        elif kind == "video_stop":
            if active_video and active_video.get("file_id"):
                stop_s = float(e.get("stop_s") or 0.0)
                dur_s = max(0.0, stop_s - active_video["start_s"])
                if dur_s >= 0.2:   # unter 200 ms ignorieren
                    clip = extract_video_audio(
                        active_video["file_id"],
                        active_video["start_s"],
                        dur_s,
                    )
                    if clip:
                        segments.append((
                            int(active_video["t_ms"]),
                            clip,
                            int(dur_s * 1000),
                            VIDEO_GAIN_DB,
                        ))
            active_video = None

    if not segments:
        log("[fehler] Keine verarbeitbaren Audio-/Video-Segmente gefunden.")
        if missing_tts:
            log("TTS fehlt im Cache (erste 5):")
            for t_ms, txt in missing_tts[:5]:
                log(f"  t={t_ms}ms  {txt!r}")
        sys.exit(1)

    total_ms = max(start + dur for start, _p, dur, _g in segments)
    tts_n = sum(1 for _s, _p, _d, g in segments if g == 0.0)
    vid_n = len(segments) - tts_n
    log(f"[info] {len(segments)} Segmente ({tts_n} TTS, {vid_n} Video), "
        f"Gesamtdauer {total_ms / 1000:.2f} s")

    # --- ffmpeg-filter_complex ----------------------------------------
    # anullsrc als Basis, dann pro Segment ein Zweig mit aresample +
    # aformat + volume + adelay. Am Ende amix mit weights=1..1.
    args: list[str] = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi",
        "-t", f"{total_ms / 1000:.3f}",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate={SAMPLE_RATE}",
    ]
    for _start, path, _dur, _gain in segments:
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
    mix_inputs = "".join(labels)
    weights = " ".join(["1"] * len(labels))
    filter_parts.append(
        f"{mix_inputs}amix=inputs={len(labels)}:duration=longest:"
        f"dropout_transition=0:weights={weights}[out]"
    )

    args += [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[out]",
        "-ac", "2",
        "-ar", str(SAMPLE_RATE),
        "-c:a", "pcm_s16le",
        str(output_path),
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    log(f"[info] ffmpeg laeuft -- {output_path}")
    try:
        subprocess.check_call(args)
    except subprocess.CalledProcessError as e:
        log(f"[fehler] ffmpeg: {e}")
        sys.exit(2)

    if missing_tts:
        log(f"[warn] {len(missing_tts)} TTS-Audios nicht im Cache, uebersprungen:")
        for t_ms, txt in missing_tts[:10]:
            log(f"  t={t_ms}ms  {txt!r}")

    size_mb = output_path.stat().st_size / 1024 / 1024
    log(f"[fertig] {output_path}  ({size_mb:.1f} MB, "
        f"{total_ms / 1000:.1f} s)")


def main() -> None:
    inp = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT
    build(inp, out)


if __name__ == "__main__":
    main()
