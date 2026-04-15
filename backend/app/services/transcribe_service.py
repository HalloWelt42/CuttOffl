"""
CuttOffl Backend - Transkriptions-Service.

Dieser Service ist bewusst so geschrieben, dass die App *immer* startet,
auch wenn weder mlx-whisper noch openai-whisper noch faster-whisper
installiert sind. capabilities() liefert dann einen klaren "nicht
verfuegbar"-Status an das Frontend, das dann entsprechend reagiert.

Drei moegliche Engines:
  * mlx-whisper       -- Apple-Silicon-optimiert (Metal), schnell
  * faster-whisper    -- CTranslate2-basiert, portabel (Pi, Intel, Linux)
  * openai-whisper    -- Referenz-Implementierung, langsamer, aber verbreitet

Pro Engine gibt es eine eigene Modell-Cache-Konvention:
  * mlx-whisper     -> HuggingFace-Hub-Cache (~/.cache/huggingface/hub/)
  * faster-whisper  -> HuggingFace-Hub-Cache (Systran/faster-whisper-*)
  * openai-whisper  -> eigener Cache (~/.cache/whisper/*.pt)

Wir scannen nicht blind, sondern konservativ: Wir zeigen nur Modelle an,
deren Ablage so aussieht, als koennten sie tatsaechlich geladen werden.
Ob sie wirklich funktionieren entscheidet der Lade-Versuch; Fehler
werden sauber nach oben gereicht, ohne die App zu crashen.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Engines und Modelle
# --------------------------------------------------------------------------

# Offizielle Whisper-Modellnamen (klein -> gross). "large-v3" ist das beste,
# "large-v3-turbo" ist schneller bei leicht geringerer Qualitaet. "medium"
# ist ein guter Kompromiss.
WHISPER_SIZES: tuple[str, ...] = (
    "tiny", "base", "small", "medium", "large-v2", "large-v3", "large-v3-turbo",
)

DEFAULT_MODEL = "large-v3"


@dataclass
class ModelLocation:
    """Eine konkret auf der Platte gefundene Modell-Instanz."""
    engine: str            # 'mlx-whisper' | 'openai-whisper' | 'faster-whisper'
    model: str             # 'large-v3' usw.
    path: str              # absoluter Pfad (Datei oder Ordner)
    size_bytes: int = 0    # ungefaehre Groesse auf der Platte


@dataclass
class EngineInfo:
    name: str              # 'mlx-whisper' | 'openai-whisper' | 'faster-whisper'
    installed: bool        # Paket importierbar?
    reason: str = ""       # Grund wenn not installed
    preferred: bool = False  # auf dieser Plattform bevorzugt?


@dataclass
class Capabilities:
    available: bool
    engines: list[EngineInfo] = field(default_factory=list)
    models_found: list[ModelLocation] = field(default_factory=list)
    suggested_engine: Optional[str] = None
    suggested_model: Optional[str] = None
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Engine-Detection (lazy, mit try/except)
# --------------------------------------------------------------------------

def _try_import(module_name: str) -> tuple[bool, str]:
    try:
        __import__(module_name)
        return True, ""
    except ImportError as e:
        return False, str(e)
    except Exception as e:
        # z. B. BinaryImportError auf inkompatibler Architektur
        return False, f"{type(e).__name__}: {e}"


def _is_apple_silicon() -> bool:
    if sys.platform != "darwin":
        return False
    import platform
    return platform.machine() in ("arm64", "aarch64")


def detect_engines() -> list[EngineInfo]:
    apple = _is_apple_silicon()

    # mlx-whisper nur auf Apple Silicon sinnvoll
    mlx_ok, mlx_reason = _try_import("mlx_whisper") if apple else (False, "nur Apple Silicon")
    faster_ok, faster_reason = _try_import("faster_whisper")
    openai_ok, openai_reason = _try_import("whisper")

    return [
        EngineInfo(
            name="mlx-whisper",
            installed=mlx_ok,
            reason=mlx_reason,
            preferred=apple and mlx_ok,
        ),
        EngineInfo(
            name="faster-whisper",
            installed=faster_ok,
            reason=faster_reason,
            preferred=(not apple) and faster_ok,
        ),
        EngineInfo(
            name="openai-whisper",
            installed=openai_ok,
            reason=openai_reason,
            preferred=False,
        ),
    ]


# --------------------------------------------------------------------------
# Modell-Scan auf der Platte
# --------------------------------------------------------------------------

# Bekannte Orte, an denen Whisper-Modelle liegen koennten.
# Kein blindes Systemsabsuchen -- wir beschraenken uns auf die ueblichen
# Cache-Konventionen der jeweiligen Libraries, plus einen Voice2Text-
# Schwesterpfad falls vorhanden.
def _default_scan_roots() -> list[Path]:
    home = Path.home()
    roots = [
        home / ".cache" / "huggingface" / "hub",          # mlx, faster
        home / ".cache" / "whisper",                       # openai
        home / "Library" / "Caches" / "huggingface" / "hub",
    ]
    # Voice2Text-Schwesterprojekt: wenn es da ist, koennen wir dessen Cache
    # mit benutzen, um Downloads zu sparen.
    voice2text = Path(
        "/Users/alpha/Entwicklung/03_KI_Erstellung/Python/Voice2Text/cache"
    )
    if voice2text.exists():
        roots.append(voice2text / "huggingface" / "hub")
        roots.append(voice2text / "audio_processor")
    return [r for r in roots if r.exists() and r.is_dir()]


def _dir_size(p: Path) -> int:
    try:
        total = 0
        for f in p.rglob("*"):
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                pass
        return total
    except OSError:
        return 0


def _scan_hf_hub(root: Path) -> list[ModelLocation]:
    """HF-Hub-Layout: models--<org>--<name>/snapshots/<hash>/..."""
    found: list[ModelLocation] = []
    for entry in root.iterdir():
        if not entry.is_dir() or not entry.name.startswith("models--"):
            continue
        name_lower = entry.name.lower()
        engine = None
        model = None
        if "whisper" not in name_lower:
            continue
        # mlx-community/whisper-<size>-mlx
        if "mlx-community" in name_lower or "-mlx" in name_lower:
            engine = "mlx-whisper"
            # versuche size aus dem Namen zu ziehen
            for s in WHISPER_SIZES:
                if s in name_lower:
                    model = s
                    break
        # Systran/faster-whisper-<size>
        elif "systran" in name_lower and "faster-whisper" in name_lower:
            engine = "faster-whisper"
            for s in WHISPER_SIZES:
                if name_lower.endswith(f"-{s}") or f"-{s}-" in name_lower:
                    model = s
                    break
        else:
            continue
        if not model:
            continue
        # Nur wenn snapshot/ existiert und nicht leer ist
        snap_dir = entry / "snapshots"
        if not snap_dir.exists():
            continue
        snapshots = [p for p in snap_dir.iterdir() if p.is_dir()]
        if not snapshots:
            continue
        # Groesstes Snapshot nehmen
        snap = max(snapshots, key=_dir_size)
        found.append(ModelLocation(
            engine=engine,
            model=model,
            path=str(snap),
            size_bytes=_dir_size(snap),
        ))
    return found


def _scan_openai_cache(root: Path) -> list[ModelLocation]:
    """openai-whisper-Cache: <size>.pt Dateien im Verzeichnis."""
    found: list[ModelLocation] = []
    for entry in root.iterdir():
        if not entry.is_file() or entry.suffix != ".pt":
            continue
        stem = entry.stem
        if stem in WHISPER_SIZES:
            found.append(ModelLocation(
                engine="openai-whisper",
                model=stem,
                path=str(entry),
                size_bytes=entry.stat().st_size,
            ))
    return found


def scan_models(extra_roots: Optional[list[str]] = None) -> list[ModelLocation]:
    """Sucht bekannte Modell-Ablagen auf der Platte ab. Gibt eine Liste von
    ModelLocation zurueck, die das Frontend dem Nutzer zur Auswahl anbieten
    kann."""
    roots = _default_scan_roots()
    for extra in extra_roots or []:
        p = Path(extra).expanduser().resolve()
        if p.exists() and p.is_dir() and p not in roots:
            roots.append(p)

    out: list[ModelLocation] = []
    for root in roots:
        name = root.name.lower()
        try:
            if name == "hub":
                out.extend(_scan_hf_hub(root))
            elif name == "whisper":
                out.extend(_scan_openai_cache(root))
            elif (root / "hub").exists():
                out.extend(_scan_hf_hub(root / "hub"))
            else:
                # generischer HF-Layout-Versuch
                out.extend(_scan_hf_hub(root))
        except Exception as e:
            logger.warning(f"Scan-Fehler in {root}: {e}")
    # Duplikate anhand (engine, model, path) entfernen
    seen: set[tuple[str, str, str]] = set()
    unique: list[ModelLocation] = []
    for m in out:
        key = (m.engine, m.model, m.path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(m)
    return unique


# --------------------------------------------------------------------------
# Capabilities-Zusammenfassung
# --------------------------------------------------------------------------

def capabilities(scan: bool = True) -> Capabilities:
    """Fasst Engine-Verfuegbarkeit und gefundene Modelle zu einer Antwort
    fuer das Frontend zusammen."""
    engines = detect_engines()
    any_installed = any(e.installed for e in engines)

    caps = Capabilities(available=False, engines=engines)

    if not any_installed:
        caps.notes.append(
            "Kein Whisper-Paket installiert. Installiere `mlx-whisper` "
            "(Apple Silicon) oder `faster-whisper` (Pi/Linux/Intel)."
        )
        return caps

    if scan:
        try:
            caps.models_found = scan_models()
        except Exception as e:
            logger.warning(f"Modell-Scan fehlgeschlagen: {e}")
            caps.notes.append(f"Modell-Scan fehlgeschlagen: {e}")

    # Vorschlag: bevorzugte Engine, die installiert ist
    preferred = next(
        (e for e in engines if e.preferred and e.installed),
        next((e for e in engines if e.installed), None),
    )
    if preferred:
        caps.suggested_engine = preferred.name
        # Modell: wenn zur Engine passend was lokal da ist, das groesste
        # vorhandene -- sonst Default
        local = [m for m in caps.models_found if m.engine == preferred.name]
        if local:
            # Praeferenz-Reihenfolge: large-v3 > large-v3-turbo > large-v2 > ...
            order = {s: i for i, s in enumerate(reversed(WHISPER_SIZES))}
            local.sort(key=lambda m: order.get(m.model, -1), reverse=True)
            caps.suggested_model = local[0].model
        else:
            caps.suggested_model = DEFAULT_MODEL

    caps.available = bool(caps.suggested_engine and caps.models_found)
    if caps.suggested_engine and not caps.models_found:
        caps.notes.append(
            f"Engine '{caps.suggested_engine}' ist installiert, aber es "
            f"wurde kein lokales Whisper-Modell gefunden. Lade in den "
            f"Einstellungen ein Modell herunter oder scanne deine Platte."
        )
    return caps


# --------------------------------------------------------------------------
# SRT-Formatter
# --------------------------------------------------------------------------

def segments_to_srt(segments: list[dict]) -> str:
    """Erzeugt SRT-Text aus einer Segmente-Liste. Jedes Segment braucht
    `start` (sekunden, float), `end` (sekunden, float) und `text` (str)."""
    def fmt(t: float) -> str:
        if t < 0:
            t = 0.0
        ms = int(round(t * 1000))
        hh = ms // 3_600_000
        ms -= hh * 3_600_000
        mm = ms // 60_000
        ms -= mm * 60_000
        ss = ms // 1000
        ms -= ss * 1000
        return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"

    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        lines.append(str(i))
        lines.append(f"{fmt(start)} --> {fmt(end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def parse_srt(content: str) -> list[dict]:
    """Liest SRT zurueck in Segmente. Toleriert CRLF und leere Blocks."""
    segs: list[dict] = []
    if not content:
        return segs
    import re
    blocks = re.split(r"\r?\n\r?\n", content.strip())
    ts_re = re.compile(
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
    )

    def to_s(h, m, s, ms):
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    for b in blocks:
        lines = [ln.strip() for ln in b.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        ts_line = lines[1] if ts_re.search(lines[1]) else (
            lines[0] if ts_re.search(lines[0]) else None
        )
        if not ts_line:
            continue
        m = ts_re.search(ts_line)
        if not m:
            continue
        start = to_s(*m.group(1, 2, 3, 4))
        end = to_s(*m.group(5, 6, 7, 8))
        text_lines = lines[lines.index(ts_line) + 1:]
        text = " ".join(text_lines).strip()
        if text:
            segs.append({"start": start, "end": end, "text": text})
    return segs
