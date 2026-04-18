#!/usr/bin/env python3
"""
CuttOffl -- Tour-Audio bauen.

Liest data/tmp/tour-recording.json (wird vom Frontend waehrend einer
Tour-Aufnahme geschrieben, wenn die URL ?tour_record=1 gesetzt war)
und baut daraus eine einzige WAV-Datei:

  - tour_start bei t_ms=0 legt den Zeit-Nullpunkt fest.
  - Jedes audio_start { t_ms, text } findet die passende MP3 im
    TTS-Cache (gleiche Hash-Logik wie app/routers/speak.py:
    sha256(VOICE_ID + "|" + text), erste 32 hex-Zeichen).
  - Audios werden nicht abgeschnitten. Wenn ein folgendes audio_start
    kommt, bevor das vorige durchgelaufen ist, wird es hinter das
    vorige geschoben (Gesamtlaenge wird ggf. laenger als der letzte
    Event-Timestamp).
  - Zwischen Audios: Stille.

Ausgabe: notes/tour-audio.wav (notes/ ist gitignored).

Benutzung:
  ./tools/build_tour_audio.py [eingabe.json] [ausgabe.wav]

Ohne Argumente: data/tmp/tour-recording.json -> notes/tour-audio.wav
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "tmp" / "tour-recording.json"
DEFAULT_OUTPUT = ROOT / "notes" / "tour-audio.wav"

# Damit wir keine Logik duplizieren: Sanitize und Cache-Pfad kommen
# direkt aus dem Backend. So passt der Hash garantiert -- wenn das
# Backend die Voice-ID oder die Sanitize-Regeln aendert, zieht das
# Tool automatisch nach.
sys.path.insert(0, str(ROOT / "backend"))
from app.routers.speak import (  # noqa: E402
    cache_path_for, sanitize_for_speech,
)

SAMPLE_RATE = 48_000


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def mp3_duration_ms(path: Path) -> int:
    """ffprobe liefert Dauer in Sekunden, wir runden auf ms."""
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ], text=True).strip()
    return int(float(out) * 1000)


def build(input_path: Path, output_path: Path) -> None:
    if not input_path.exists():
        log(f"[fehler] Eingabedatei fehlt: {input_path}")
        sys.exit(1)
    events = json.loads(input_path.read_text("utf-8"))
    if not events:
        log("[fehler] Keine Events in der Aufnahme.")
        sys.exit(1)

    # tour_start einordnen
    events.sort(key=lambda e: e.get("t_ms", 0))
    audios = [e for e in events if e.get("kind") == "audio_start"]
    if not audios:
        log("[fehler] Keine audio_start-Events.")
        sys.exit(1)

    log(f"[info] {len(events)} Events, davon {len(audios)} Audios.")

    # Pro Audio: MP3 finden, Laenge ermitteln, Zielposition festlegen.
    # cursor_ms = naechste freie Position auf der Output-Spur.
    segments: list[tuple[int, Path, int]] = []  # (start_ms, path, duration_ms)
    cursor_ms = 0
    missing = []

    for a in audios:
        raw = a.get("text", "")
        # Dieselbe Normalisierung wie im /speak-Endpoint, sonst stimmt
        # der Hash nicht -- der Backend-Endpoint bildet den Cache-Pfad
        # aus sanitize_for_speech(body.text).
        text = sanitize_for_speech(raw)
        if not text:
            continue
        mp3 = cache_path_for(text)
        if not mp3.exists():
            missing.append((a.get("t_ms"), text[:60]))
            continue
        try:
            dur = mp3_duration_ms(mp3)
        except Exception as e:
            log(f"[warn] ffprobe fehlgeschlagen fuer {mp3.name}: {e}")
            continue
        requested_start = int(a.get("t_ms", 0))
        start = max(cursor_ms, requested_start)
        segments.append((start, mp3, dur))
        cursor_ms = start + dur

    if not segments:
        log("[fehler] Keine passenden MP3s im TTS-Cache gefunden.")
        if missing:
            log("Fehlt im Cache (erste 5):")
            for t_ms, txt in missing[:5]:
                log(f"  t={t_ms}ms  {txt!r}")
        sys.exit(1)

    total_ms = segments[-1][0] + segments[-1][1]
    log(f"[info] Gesamtdauer: {total_ms / 1000:.2f} s "
        f"({len(segments)} Audio-Segmente)")

    # ffmpeg-Kommando: lavfi sine=0 als Stille-Basis + pro Audio ein
    # Input mit adelay, alles ueber amix mischen. Der Stille-Track
    # garantiert die Gesamt-Laenge.
    args: list[str] = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi",
        "-t", f"{total_ms / 1000:.3f}",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate={SAMPLE_RATE}",
    ]
    for _start, path, _dur in segments:
        args += ["-i", str(path)]

    # Filterkette bauen: pro Segment ein adelay auf Stereo, danach
    # amix mit allen Zweigen plus der Stille-Basis.
    filter_parts = []
    labels = ["[0:a]"]  # Stille-Track
    for idx, (start, _path, _dur) in enumerate(segments, start=1):
        filter_parts.append(
            f"[{idx}:a]aresample={SAMPLE_RATE},"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"adelay={start}|{start}[a{idx}]"
        )
        labels.append(f"[a{idx}]")
    mix_inputs = "".join(labels)
    # duration=longest laesst amix bis zum laengsten Eingang laufen;
    # weights=1..1 haelt die Pegel gleich (die Stille traegt nichts bei).
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

    if missing:
        log(f"[warn] {len(missing)} Audios nicht im Cache, uebersprungen:")
        for t_ms, txt in missing[:10]:
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
