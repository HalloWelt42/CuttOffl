#!/usr/bin/env python3
"""
CuttOffl -- Tour-Audio bauen (rein rechnerisch).

Baut aus den vorhandenen Tour-Audio-MP3s in
frontend/public/tour-audio/ eine zusammenhaengende Audio-Spur, die dem
Demo-Modus-Timing der Tour entspricht.

Es gibt keine Live-Aufnahme mehr. Das Timing wird rekonstruiert, wie
der TourOverlay im Demo-Modus ablaeuft:

    t = 0
    fuer jede Tour in TOUR_ORDER:
      fuer jeden Schritt i = 0..N-1:
        wenn <tour-id>-<i>.mp3 existiert:
          Audio startet bei t, Laenge aus ffprobe
          t += Audio-Laenge + DEMO_AUDIO_BUFFER_MS
        sonst:
          t += DEMO_FALLBACK_MS (Platzhalter-Stille)

Die zwei Puffer-Konstanten sind identisch zu
frontend/src/lib/tour.svelte.js (DEMO_AUDIO_BUFFER_MS = 2500,
DEMO_FALLBACK_MS = 4500).

Benutzung:
    ./tools/build_tour_audio.py [ausgabe.wav]

Default-Ausgabe: notes/tour-audio.wav
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOUR_AUDIO_DIR = ROOT / "frontend" / "public" / "tour-audio"
DEFAULT_OUTPUT = ROOT / "notes" / "tour-audio.wav"

# Reihenfolge wie im "Kompletter Rundgang" -- siehe
# frontend/src/lib/tours.js (SKELETONS-Insertion-Order).
TOUR_ORDER = [
    "erste-schritte",
    "bibliothek",
    "renderer",
    "tastenkuerzel",
    "ki-untertitel",
]

# Puffer, muss mit frontend/src/lib/tour.svelte.js uebereinstimmen.
DEMO_AUDIO_BUFFER_MS = 2500
DEMO_FALLBACK_MS = 4500

SAMPLE_RATE = 48_000
# Obergrenze fuer einen Schritt-Index, ab dem wir aufhoeren zu suchen
# (in der Praxis <=15 Schritte pro Tour).
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


def collect_segments() -> tuple[list[tuple[int, Path, int]], int]:
    """Iteriert durch TOUR_ORDER + Step-Indizes, ermittelt pro Schritt
    einen (start_ms, mp3, duration_ms)-Eintrag. Liefert zusaetzlich die
    Gesamtdauer in Millisekunden."""
    segments: list[tuple[int, Path, int]] = []
    t = 0
    for tour_id in TOUR_ORDER:
        # Wie viele Schritte hat diese Tour? -- durch Probieren bestimmt,
        # solange <tour-id>-<i>.mp3 ODER ein wahrscheinlicher demo_ms-
        # Platzhalter existiert.
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
                try:
                    dur = media_duration_ms(mp3)
                except Exception as e:
                    log(f"[warn] ffprobe fuer {mp3.name}: {e}")
                    continue
                segments.append((t, mp3, dur))
                t += dur + DEMO_AUDIO_BUFFER_MS
            else:
                # Schritt ohne Audio (demo_ms-Only). Platzhalter-Stille.
                t += DEMO_FALLBACK_MS

    return segments, t


def build(output_path: Path) -> None:
    if not TOUR_AUDIO_DIR.exists():
        log(f"[fehler] Tour-Audio-Ordner fehlt: {TOUR_AUDIO_DIR}")
        log("         tools/generate_tour_audio.py einmal laufen lassen.")
        sys.exit(1)

    segments, total_ms = collect_segments()
    if not segments:
        log("[fehler] Keine Segmente gefunden.")
        sys.exit(1)

    # Am Ende den letzten Audio-Buffer nicht zum Gesamtstand zaehlen --
    # die Audio-Spur darf am Ende direkt abschliessen.
    total_ms = max(total_ms, segments[-1][0] + segments[-1][2])

    log(f"[info] {len(segments)} Audio-Segmente, "
        f"{total_ms/1000:.2f} s ({total_ms/60000:.1f} min)")

    # ffmpeg: anullsrc als Stille-Basis + pro MP3 ein Input mit adelay.
    args: list[str] = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi",
        "-t", f"{total_ms / 1000:.3f}",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate={SAMPLE_RATE}",
    ]
    for _start, path, _dur in segments:
        args += ["-i", str(path)]

    filter_parts = []
    labels = ["[0:a]"]
    for idx, (start, _path, _dur) in enumerate(segments, start=1):
        filter_parts.append(
            f"[{idx}:a]aresample={SAMPLE_RATE},"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"adelay={start}|{start}[a{idx}]"
        )
        labels.append(f"[a{idx}]")
    # normalize=0: ffmpeg-amix teilt sonst stumpf durch die Anzahl der
    # Inputs (hier 33) -- jedes Segment waere dann ~-30 dB leiser. Da
    # unsere Segmente zeitlich nicht ueberlappen, ist stumpfes Addieren
    # (normalize=0) korrekt und liefert den originalen Pegel.
    filter_parts.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:"
        f"duration=longest:dropout_transition=0:normalize=0[out]"
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
    log(f"[info] ffmpeg -> {output_path}")
    try:
        subprocess.check_call(args)
    except subprocess.CalledProcessError as e:
        log(f"[fehler] ffmpeg: {e}")
        sys.exit(2)

    size_mb = output_path.stat().st_size / 1024 / 1024
    log(f"[fertig] {output_path}  ({size_mb:.1f} MB, {total_ms/1000:.1f} s)")


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    build(out)


if __name__ == "__main__":
    main()
