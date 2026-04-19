#!/usr/bin/env python3
"""
CuttOffl -- Tour-Audio bauen (rein rechnerisch, knackfreier Pfad).

Baut aus den pre-generierten Tour-Audio-MP3s in
frontend/public/tour-audio/ eine zusammenhaengende WAV-Datei, die
dem Demo-Modus-Timing der Tour entspricht.

Ansatz: **keine amix-Filterkette**. Stattdessen werden pro Schritt
einzelne PCM-WAV-Zwischendateien erzeugt (normalisiert auf 48 kHz
Stereo s16) und am Ende per `ffmpeg -f concat` stream-copy zu einer
grossen WAV verbunden. Dadurch entstehen keine amix-Knackser an den
Segment-Grenzen und kein Resample-Pre-Roll, der den Anfang
verschluckt.

Timing:
    t = 0
    fuer jede Tour in TOUR_ORDER:
      fuer jeden Schritt i:
        wenn <tour-id>-<i>.mp3 existiert:
          Audio-Segment (MP3 -> WAV 48 kHz s16 stereo)
          danach DEMO_AUDIO_BUFFER_MS Stille
        sonst:
          DEMO_FALLBACK_MS Stille (Platzhalter fuer demo_ms-Schritt)

Ausgabe: notes/tour-audio.wav
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOUR_AUDIO_DIR = ROOT / "frontend" / "public" / "tour-audio"
DEFAULT_OUTPUT = ROOT / "notes" / "tour-audio.wav"

TOUR_ORDER = [
    "erste-schritte",
    "bibliothek",
    "renderer",
    "tastenkuerzel",
    "ki-untertitel",
]

DEMO_AUDIO_BUFFER_MS = 2500
DEMO_FALLBACK_MS = 4500

SAMPLE_RATE = 48_000
CHANNELS = 2

MAX_STEPS_PER_TOUR = 32


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def media_duration_ms(path: Path) -> int:
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ], text=True).strip()
    return int(float(out) * 1000)


def mp3_to_wav(src: Path, dst: Path) -> None:
    """Normalisiert eine MP3 zu 48 kHz Stereo s16 WAV ohne Padding."""
    subprocess.check_call([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-ac", str(CHANNELS),
        "-ar", str(SAMPLE_RATE),
        "-c:a", "pcm_s16le",
        # -af aformat erzwingt finales Sample-Format; kein Resample-
        # Pre-Roll, keine Fade-Ins der Decoder.
        "-af", f"aformat=sample_fmts=s16:channel_layouts=stereo,aresample=async=0:first_pts=0",
        str(dst),
    ])


def silence_wav(duration_s: float, dst: Path) -> None:
    """Erzeugt eine Stille-WAV exakter Laenge."""
    if duration_s <= 0:
        return
    subprocess.check_call([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi",
        "-t", f"{duration_s:.6f}",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate={SAMPLE_RATE}",
        "-c:a", "pcm_s16le",
        str(dst),
    ])


def concat_wavs(parts: list[Path], dst: Path) -> None:
    """Verbindet mehrere WAVs per concat-Demuxer (stream-copy) zu
    einer. Alle Inputs muessen identisches Sample-Format / -Rate /
    Channel-Layout haben -- das garantieren wir durch die PCM-
    Erzeugung oben."""
    list_path = dst.with_suffix(".list.txt")
    with list_path.open("w", encoding="utf-8") as f:
        for p in parts:
            f.write(f"file '{p.as_posix()}'\n")
    subprocess.check_call([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", str(list_path),
        "-c", "copy",
        str(dst),
    ])
    list_path.unlink(missing_ok=True)


def build(output_path: Path) -> None:
    if not TOUR_AUDIO_DIR.exists():
        log(f"[fehler] Tour-Audio-Ordner fehlt: {TOUR_AUDIO_DIR}")
        sys.exit(1)

    tmpdir = Path(tempfile.mkdtemp(prefix="tour-audio-"))
    parts: list[Path] = []
    idx = 0
    total_ms = 0
    audios_used = 0

    try:
        for tour_id in TOUR_ORDER:
            step_count = 0
            for i in range(MAX_STEPS_PER_TOUR):
                mp3 = TOUR_AUDIO_DIR / f"{tour_id}-{i}.mp3"
                if mp3.exists():
                    step_count = i + 1
            if step_count == 0:
                log(f"[warn] Keine MP3s fuer Tour {tour_id!r} -- uebersprungen")
                continue
            log(f"[info] Tour {tour_id}: {step_count} Schritte")

            for i in range(step_count):
                mp3 = TOUR_AUDIO_DIR / f"{tour_id}-{i}.mp3"
                if mp3.exists():
                    # Audio-Segment als WAV + direkt danach Puffer-Stille
                    wav = tmpdir / f"seg-{idx:04d}-audio.wav"
                    mp3_to_wav(mp3, wav)
                    parts.append(wav)
                    idx += 1
                    audios_used += 1
                    total_ms += media_duration_ms(wav)

                    sil = tmpdir / f"seg-{idx:04d}-buffer.wav"
                    silence_wav(DEMO_AUDIO_BUFFER_MS / 1000.0, sil)
                    parts.append(sil)
                    idx += 1
                    total_ms += DEMO_AUDIO_BUFFER_MS
                else:
                    # Schritt ohne Audio -> Stille-Platzhalter
                    sil = tmpdir / f"seg-{idx:04d}-silence.wav"
                    silence_wav(DEMO_FALLBACK_MS / 1000.0, sil)
                    parts.append(sil)
                    idx += 1
                    total_ms += DEMO_FALLBACK_MS

        if not parts:
            log("[fehler] Keine Segmente gefunden.")
            sys.exit(1)

        log(f"[info] {audios_used} Audio-Segmente + Stille, "
            f"{total_ms/1000:.2f} s ({total_ms/60000:.1f} min)")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        log(f"[info] ffmpeg concat -> {output_path}")
        concat_wavs(parts, output_path)

        size_mb = output_path.stat().st_size / 1024 / 1024
        log(f"[fertig] {output_path}  "
            f"({size_mb:.1f} MB, {total_ms/1000:.1f} s)")
    finally:
        # tmpdir aufraeumen
        try:
            import shutil as _sh
            _sh.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    build(out)


if __name__ == "__main__":
    main()
