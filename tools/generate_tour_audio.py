#!/usr/bin/env python3
"""
Generiert die Tour-Audio-Dateien einmalig über die txt2voice-API.

Quelle der Texte: frontend/src/lib/tour-texts.json (Feld audio_text).
Ziel der MP3s:    frontend/public/tour-audio/<tour-id>-<step-idx>.mp3

Cache-Mechanik: Neben jeder MP3 landet ein .hash-File mit dem SHA-256
des Quelltextes. Bei erneutem Aufruf wird die Synthese übersprungen,
wenn MP3 und Hash vorhanden sind und der Hash zum aktuellen Text
passt. So kann das Script gefahrlos mehrfach laufen -- es generiert
nur geänderte oder fehlende Schritte neu.

Voraussetzung: txt2voice-Backend läuft auf http://127.0.0.1:10031
mit einer Stimme, die im Feld 'name' den Teilstring "Zeit" trägt
(Default: "Zeit Stimme"). Andere Stimme kann über --voice
übergeben werden.

Benutzung:
    python3 tools/generate_tour_audio.py
    python3 tools/generate_tour_audio.py --force        # alles neu
    python3 tools/generate_tour_audio.py --tour renderer
    python3 tools/generate_tour_audio.py --voice "Mario"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests


ROOT = Path(__file__).resolve().parent.parent
TEXTS_PATH = ROOT / "frontend" / "src" / "lib" / "tour-texts.json"
AUDIO_DIR = ROOT / "frontend" / "public" / "tour-audio"
TXT2VOICE_BASE = "http://127.0.0.1:10031"


def log(msg: str, level: str = "info") -> None:
    colors = {
        "info":  "\033[0;36m",
        "ok":    "\033[0;32m",
        "warn":  "\033[0;33m",
        "err":   "\033[0;31m",
        "skip":  "\033[0;90m",
    }
    reset = "\033[0m"
    c = colors.get(level, "")
    print(f"{c}{msg}{reset}", flush=True)


def find_voice_id(name_fragment: str) -> str | None:
    """Holt die Voices-Liste und findet die ID zu einem Namens-Fragment."""
    try:
        r = requests.get(f"{TXT2VOICE_BASE}/api/voices", timeout=5)
        r.raise_for_status()
        voices = r.json()
    except Exception as e:
        log(f"[err] Kann Voices nicht laden: {e}", "err")
        return None
    fragment_lower = name_fragment.lower()
    for v in voices:
        name = (v.get("name") or "").lower()
        if fragment_lower in name:
            return v.get("id")
    log(
        f"[warn] Stimme mit '{name_fragment}' nicht gefunden. "
        f"Verfügbar: {', '.join(v.get('name', '?') for v in voices[:8])}",
        "warn",
    )
    return None


def synthesize(
    text: str, voice_id: str,
    language: str = "german", speed: float = 1.0,
) -> bytes | None:
    """Schickt den Text an txt2voice und liefert die MP3-Bytes.

    Nutzt den Clone-Endpunkt, weil unsere "Zeit Stimme" eine
    individuelle, geklonte Stimme aus der DB ist (kein Built-in-
    Speaker wie aiden oder serena).
    """
    form = {
        "text": text,
        "voice_id": voice_id,
        "language": language,
        "speed": str(speed),
        "persist": "false",
    }
    try:
        r = requests.post(
            f"{TXT2VOICE_BASE}/api/synthesize/clone",
            data=form, timeout=300,
        )
        r.raise_for_status()
        result = r.json()
    except Exception as e:
        log(f"[err] Synthese fehlgeschlagen: {e}", "err")
        return None

    audio_url = result.get("audio_url") or ""
    if not audio_url:
        log(f"[err] Kein audio_url in Response: {result}", "err")
        return None

    full_url = urljoin(TXT2VOICE_BASE, audio_url)
    try:
        r = requests.get(full_url, timeout=60)
        r.raise_for_status()
        return r.content
    except Exception as e:
        log(f"[err] Audio-Download fehlgeschlagen: {e}", "err")
        return None


def text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="Alle MP3s neu generieren, auch wenn Hash matcht")
    parser.add_argument("--tour", default=None,
                        help="Nur eine bestimmte Tour generieren (ID)")
    parser.add_argument("--voice", default="Zeit",
                        help="Teilstring des gewünschten Stimmen-Namens (Default: 'Zeit')")
    args = parser.parse_args()

    if not TEXTS_PATH.exists():
        log(f"[err] {TEXTS_PATH} fehlt", "err")
        return 1

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # Health-Check txt2voice
    try:
        requests.get(f"{TXT2VOICE_BASE}/api/system/health", timeout=3).raise_for_status()
    except Exception as e:
        log(
            f"[err] txt2voice-Backend nicht erreichbar auf {TXT2VOICE_BASE}.\n"
            f"     Start: cd ~/Entwicklung/03_KI_Erstellung/txt2voice && ./start.sh\n"
            f"     Detail: {e}",
            "err",
        )
        return 1

    voice_id = find_voice_id(args.voice)
    if not voice_id:
        return 1
    log(f"Verwende Stimme '{args.voice}' -> ID {voice_id}", "info")

    data = json.loads(TEXTS_PATH.read_text(encoding="utf-8"))
    totals = {"done": 0, "skipped": 0, "failed": 0}
    t_start = time.time()

    for tour_id, steps in data.items():
        if tour_id.startswith("_"):
            continue
        if args.tour and args.tour != tour_id:
            continue
        log(f"\n=== Tour: {tour_id} ({len(steps)} Schritte) ===", "info")
        for idx, step in enumerate(steps):
            audio_text = (step.get("audio_text") or "").strip()
            if not audio_text:
                log(f"  [{idx}] kein audio_text, übersprungen", "skip")
                continue
            mp3_path = AUDIO_DIR / f"{tour_id}-{idx}.mp3"
            hash_path = AUDIO_DIR / f"{tour_id}-{idx}.hash"
            h = text_hash(audio_text)

            if (not args.force
                    and mp3_path.exists()
                    and hash_path.exists()
                    and hash_path.read_text().strip() == h):
                log(f"  [{idx}] cache-hit ({mp3_path.name})", "skip")
                totals["skipped"] += 1
                continue

            short = audio_text[:60].replace("\n", " ")
            log(f"  [{idx}] synthetisiere: {short}...", "info")
            t0 = time.time()
            mp3 = synthesize(audio_text, voice_id)
            dt = time.time() - t0
            if not mp3:
                totals["failed"] += 1
                continue
            mp3_path.write_bytes(mp3)
            hash_path.write_text(h)
            size_kb = len(mp3) / 1024
            log(
                f"       -> {mp3_path.name} ({size_kb:.0f} KB, {dt:.1f}s)",
                "ok",
            )
            totals["done"] += 1

    dt_total = time.time() - t_start
    log(
        f"\nFertig in {dt_total:.1f}s: "
        f"{totals['done']} neu, {totals['skipped']} cached, "
        f"{totals['failed']} fehlgeschlagen",
        "ok" if totals["failed"] == 0 else "warn",
    )
    return 0 if totals["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
