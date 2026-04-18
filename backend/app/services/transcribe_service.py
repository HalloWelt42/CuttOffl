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

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

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

@dataclass
class CapabilitiesFull(Capabilities):
    # Die Nutzer-Auswahl aus user_config.json (falls vorhanden und noch
    # zu den verfuegbaren Modellen passt). Hat Vorrang vor suggested_*.
    active_engine: Optional[str] = None
    active_model: Optional[str] = None


def _read_preference() -> tuple[Optional[str], Optional[str]]:
    """Liest die persistierte Nutzer-Praeferenz aus user_config.json.
    Beide Werte sind optional -- wenn eins fehlt, greift suggested_*."""
    try:
        from app.services.user_config import load as _load
        data = _load() or {}
        tx = data.get("transcription") or {}
        return tx.get("engine") or None, tx.get("model") or None
    except Exception:
        return None, None


def capabilities(scan: bool = True) -> CapabilitiesFull:
    """Fasst Engine-Verfuegbarkeit und gefundene Modelle zu einer Antwort
    fuer das Frontend zusammen."""
    engines = detect_engines()
    any_installed = any(e.installed for e in engines)

    caps = CapabilitiesFull(available=False, engines=engines)

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

    # Nutzer-Praeferenz anwenden, wenn sie noch zur Realitaet passt:
    # Die Engine muss installiert sein UND das Modell muss entweder
    # lokal gefunden sein oder es gibt ueberhaupt keine lokale
    # Praeferenz (dann lassen wir die Engine trotzdem ziehen).
    pref_engine, pref_model = _read_preference()
    installed_engines = {e.name for e in engines if e.installed}
    if pref_engine and pref_engine in installed_engines:
        caps.active_engine = pref_engine
        if pref_model:
            pref_available = any(
                m.engine == pref_engine and m.model == pref_model
                for m in caps.models_found
            )
            if pref_available:
                caps.active_model = pref_model
    # Fallback: wenn keine gueltige Praeferenz, aktiver = suggested
    if not caps.active_engine:
        caps.active_engine = caps.suggested_engine
    if not caps.active_model:
        caps.active_model = caps.suggested_model

    caps.available = bool(caps.active_engine and caps.models_found)
    if caps.active_engine and not caps.models_found:
        caps.notes.append(
            f"Engine '{caps.active_engine}' ist installiert, aber es "
            f"wurde kein lokales Whisper-Modell gefunden. Lade in den "
            f"Einstellungen ein Modell herunter oder scanne deine Platte."
        )
    return caps


def set_preference(engine: Optional[str], model: Optional[str]) -> None:
    """Persistiert die Nutzer-Wahl in user_config.json. Beide Werte
    duerfen None sein -- dann wird die gesamte Praeferenz entfernt
    (= zurueck zum Auto-Vorschlag)."""
    from app.services.user_config import load as _load, save as _save
    data = _load() or {}
    if not engine and not model:
        data.pop("transcription", None)
    else:
        tx = data.get("transcription") or {}
        if engine: tx["engine"] = engine
        else:      tx.pop("engine", None)
        if model:  tx["model"] = model
        else:      tx.pop("model", None)
        if tx:
            data["transcription"] = tx
        else:
            data.pop("transcription", None)
    _save(data)


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


# --------------------------------------------------------------------------
# Audio-Extraktion aus Video via ffmpeg
# --------------------------------------------------------------------------

async def extract_audio(
    source: Path,
    dest: Path,
    sample_rate: int = 16000,
) -> None:
    """Extrahiert den Audio-Track als Mono-WAV mit fester Samplingrate.
    Whisper arbeitet intern mit 16 kHz, daher gleich konvertieren."""
    from app.services.ffmpeg_service import ffmpeg_binary
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_binary(),
        "-y",
        "-i", str(source),
        "-vn",                          # kein Video
        "-ac", "1",                     # mono
        "-ar", str(sample_rate),        # 16 kHz
        "-sample_fmt", "s16",
        "-f", "wav",
        str(dest),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg Audio-Extraktion fehlgeschlagen: "
            f"{err.decode('utf-8', errors='replace')[-400:]}"
        )


# --------------------------------------------------------------------------
# Engine-Dispatcher -- ruft die jeweilige Whisper-Implementierung auf und
# normalisiert die Antwort auf segmente + erkannte Sprache.
# --------------------------------------------------------------------------

@dataclass
class TranscribeResult:
    segments: list[dict]     # [{start, end, text}]
    language: str
    engine: str
    model: str


def _find_local_model(engine: str, model: str) -> Optional[str]:
    """Sucht im lokalen Scan eine passende Modell-Instanz. Gibt den
    Pfad zurueck, der direkt an die Engine uebergeben werden kann,
    oder None wenn nichts passt (dann laedt die Engine selbst)."""
    try:
        for m in scan_models():
            if m.engine == engine and m.model == model:
                return m.path
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------
# Modell-Cache: jedes geladene Whisper-Modell bleibt im Speicher, damit
# wiederholte Transkriptionen nicht jedes Mal Sekunden mit Setup warten.
# Key ist (engine, model). mlx-whisper laedt intern im transcribe-Call
# selber eine Gewichte-Datei, deshalb gibt es dort nur einen Pfad-Cache,
# keine Modell-Instanz.
# --------------------------------------------------------------------------

_model_cache: dict[tuple[str, str], object] = {}


def _get_faster_model(model: str):
    key = ("faster-whisper", model)
    if key in _model_cache:
        return _model_cache[key]
    from faster_whisper import WhisperModel  # type: ignore
    local = _find_local_model("faster-whisper", model)
    wm = WhisperModel(local or model, device="auto", compute_type="auto")
    _model_cache[key] = wm
    return wm


def _get_openai_model(model: str):
    key = ("openai-whisper", model)
    if key in _model_cache:
        return _model_cache[key]
    import whisper  # type: ignore
    m = whisper.load_model(model)
    _model_cache[key] = m
    return m


def _mlx_repo_for(model: str) -> str:
    """mlx-whisper braucht keinen Modell-Handle, nur den Repo-Pfad."""
    local = _find_local_model("mlx-whisper", model)
    return local or f"mlx-community/whisper-{model}-mlx"


# --------------------------------------------------------------------------
# Chunking: Audio in ca. 25-Sekunden-Blöcke schneiden und jeden einzeln
# transkribieren. Vorteil: Wir koennen nach jedem Chunk Segmente an die UI
# pushen (Live-Text), einen sauberen Prozent-Fortschritt melden und bei
# Cancel direkt abbrechen.
# --------------------------------------------------------------------------

CHUNK_SECONDS = 25.0
CHUNK_OVERLAP = 0.5


async def _get_audio_duration(path: Path) -> float:
    from app.services.ffmpeg_service import ffprobe_binary
    proc = await asyncio.create_subprocess_exec(
        ffprobe_binary(),
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode().strip() or 0.0)
    except Exception:
        return 0.0


async def _extract_audio_chunk(
    src: Path, dest: Path, start: float, duration: float,
) -> None:
    from app.services.ffmpeg_service import ffmpeg_binary
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_binary(), "-y",
        "-ss", f"{start:.3f}",
        "-t", f"{duration:.3f}",
        "-i", str(src),
        "-vn", "-ac", "1", "-ar", "16000", "-sample_fmt", "s16",
        "-f", "wav",
        str(dest),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"Audio-Chunk fehlgeschlagen: "
            f"{err.decode('utf-8', errors='replace')[-200:]}"
        )


def _transcribe_file_once(engine: str, model: str, path: str) -> dict:
    """Synchrone Einzel-Transkription einer WAV-Datei mit der gewuenschten
    Engine. Gibt ein Dict mit 'segments' und 'language' zurueck.

    Offline-Zwang: Sobald wir den lokalen Modell-Pfad kennen, setzen wir
    HF_HUB_OFFLINE=1 fuer den Call. Damit unterdruecken wir auch jeden
    "ist das Cache aktuell?"-HEAD-Request an huggingface.co. Fuer den
    Nutzer heisst das: nach einmaligem Download laeuft die Transkription
    komplett ohne Internet -- Pflicht fuer den Offline-first-Anspruch."""
    local = _find_local_model(engine, model)
    prev_offline = os.environ.get("HF_HUB_OFFLINE")
    if local:
        os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        if engine == "mlx-whisper":
            import mlx_whisper  # type: ignore
            # Wenn wir einen lokalen Snapshot-Pfad haben, uebergeben wir
            # den direkt -- sonst wuerde mlx-whisper einen Repo-Check
            # machen. Nur wenn keiner da ist, nennen wir den HF-Repo.
            repo = local or f"mlx-community/whisper-{model}-mlx"
            result = mlx_whisper.transcribe(
                path, path_or_hf_repo=repo, verbose=False,
            )
            return {
                "segments": list(result.get("segments") or []),
                "language": str(result.get("language") or ""),
            }
        if engine == "faster-whisper":
            wm = _get_faster_model(model)
            seg_iter, info = wm.transcribe(path, beam_size=5, vad_filter=True)
            segs = []
            for s in seg_iter:
                segs.append({"start": float(s.start), "end": float(s.end),
                             "text": (s.text or "").strip()})
            return {"segments": segs, "language": str(getattr(info, "language", "") or "")}
        if engine == "openai-whisper":
            m = _get_openai_model(model)
            result = m.transcribe(path, verbose=False, fp16=False)
            return {
                "segments": list(result.get("segments") or []),
                "language": str(result.get("language") or ""),
            }
        raise RuntimeError(f"Unbekannte Engine: {engine}")
    finally:
        # Env-Var zurueckstellen, damit der Downloader weiterhin Online-
        # Zugriff hat.
        if prev_offline is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = prev_offline


# --------------------------------------------------------------------------
# Modell-Downloader
# --------------------------------------------------------------------------

# Geschaetzte Groesse pro Modell auf der Platte (in Bytes). Wird fuer die
# Progress-Abschaetzung beim Download verwendet. Zahlen sind grob, aber
# ausreichend fuer einen aussagekraeftigen Prozent-Balken.
MODEL_SIZE_ESTIMATE: dict[tuple[str, str], int] = {
    # mlx-whisper (HF-Repos mlx-community/whisper-<size>-mlx)
    ("mlx-whisper", "tiny"):            80_000_000,
    ("mlx-whisper", "base"):           150_000_000,
    ("mlx-whisper", "small"):          480_000_000,
    ("mlx-whisper", "medium"):       1_500_000_000,
    ("mlx-whisper", "large-v2"):     3_100_000_000,
    ("mlx-whisper", "large-v3"):     3_100_000_000,
    ("mlx-whisper", "large-v3-turbo"): 1_700_000_000,
    # faster-whisper (HF-Repos Systran/faster-whisper-<size>)
    ("faster-whisper", "tiny"):         75_000_000,
    ("faster-whisper", "base"):        145_000_000,
    ("faster-whisper", "small"):       490_000_000,
    ("faster-whisper", "medium"):    1_530_000_000,
    ("faster-whisper", "large-v2"):  3_100_000_000,
    ("faster-whisper", "large-v3"):  3_100_000_000,
    ("faster-whisper", "large-v3-turbo"): 1_600_000_000,
    # openai-whisper (direkt als .pt Datei in ~/.cache/whisper/)
    ("openai-whisper", "tiny"):         75_000_000,
    ("openai-whisper", "base"):        145_000_000,
    ("openai-whisper", "small"):       465_000_000,
    ("openai-whisper", "medium"):    1_500_000_000,
    ("openai-whisper", "large-v2"):  3_090_000_000,
    ("openai-whisper", "large-v3"):  3_090_000_000,
    ("openai-whisper", "large-v3-turbo"): 1_620_000_000,
}


def _hf_repo_for(engine: str, model: str) -> str:
    if engine == "mlx-whisper":
        return f"mlx-community/whisper-{model}-mlx"
    if engine == "faster-whisper":
        return f"Systran/faster-whisper-{model}"
    raise RuntimeError(f"HF-Download nur für mlx-whisper und faster-whisper")


def _hf_cache_dir_for(engine: str, model: str) -> Path:
    """Pfad zum HF-Cache-Ordner des Modells (auch waehrend Download
    existieren dort schon Partial-Files, die wir fuer Progress nutzen)."""
    home = Path.home() / ".cache" / "huggingface" / "hub"
    if engine == "mlx-whisper":
        return home / f"models--mlx-community--whisper-{model}-mlx"
    if engine == "faster-whisper":
        return home / f"models--Systran--faster-whisper-{model}"
    return home


def _openai_cache_file_for(model: str) -> Path:
    return Path.home() / ".cache" / "whisper" / f"{model}.pt"


def _dir_size_bytes(p: Path) -> int:
    if not p.exists():
        return 0
    total = 0
    for f in p.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass
    return total


async def download_model(
    engine: str,
    model: str,
    progress_cb: Optional[Callable[[float], None]] = None,
    cancel_event: Optional[asyncio.Event] = None,
) -> str:
    """Laedt das gewuenschte Modell in den Standard-Cache der jeweiligen
    Engine. Gibt den Ziel-Pfad zurueck. Progress wird aus der waehrend
    des Downloads wachsenden Dateigroesse geschaetzt (gegen
    MODEL_SIZE_ESTIMATE)."""
    from app.services.job_service import CancelledByUser

    if engine not in ("mlx-whisper", "faster-whisper", "openai-whisper"):
        raise RuntimeError(f"Unbekannte Engine: {engine}")
    if model not in WHISPER_SIZES:
        raise RuntimeError(f"Unbekannte Modellgröße: {model}")

    expected = MODEL_SIZE_ESTIMATE.get((engine, model), 1_000_000_000)

    if engine in ("mlx-whisper", "faster-whisper"):
        repo = _hf_repo_for(engine, model)
        target = _hf_cache_dir_for(engine, model)

        def _download_hf():
            # huggingface_hub ist eine transitive Abhaengigkeit beider
            # Whisper-Pakete -- kein zusaetzlicher Install noetig.
            from huggingface_hub import snapshot_download  # type: ignore
            snapshot_download(repo_id=repo)

        task = asyncio.create_task(asyncio.to_thread(_download_hf))

        # Progress-Polling: alle 500 ms die tatsaechliche Groesse checken
        last = 0.0
        while not task.done():
            if cancel_event and cancel_event.is_set():
                task.cancel()
                raise CancelledByUser()
            await asyncio.sleep(0.5)
            now = _dir_size_bytes(target)
            frac = min(0.99, now / expected) if expected > 0 else 0.0
            if progress_cb and (frac - last) > 0.01:
                last = frac
                progress_cb(frac)

        try:
            await task
        except asyncio.CancelledError:
            raise CancelledByUser()
        if progress_cb:
            progress_cb(1.0)
        return str(target)

    # openai-whisper
    target = _openai_cache_file_for(model)
    target.parent.mkdir(parents=True, exist_ok=True)

    def _download_openai():
        import whisper  # type: ignore
        # load_model() laedt auf den offiziellen Pfad in ~/.cache/whisper
        whisper.load_model(model)

    task = asyncio.create_task(asyncio.to_thread(_download_openai))
    last = 0.0
    while not task.done():
        if cancel_event and cancel_event.is_set():
            task.cancel()
            raise CancelledByUser()
        await asyncio.sleep(0.5)
        now = target.stat().st_size if target.exists() else 0
        frac = min(0.99, now / expected) if expected > 0 else 0.0
        if progress_cb and (frac - last) > 0.01:
            last = frac
            progress_cb(frac)
    try:
        await task
    except asyncio.CancelledError:
        raise CancelledByUser()
    if progress_cb:
        progress_cb(1.0)
    return str(target)


async def run_transcription(
    audio_path: Path,
    engine: str,
    model: str,
    progress_cb: Optional[Callable[[float], None]] = None,
    segment_cb: Optional[Callable[[dict], None]] = None,
    cancel_event: Optional[asyncio.Event] = None,
    chunk_seconds: float = CHUNK_SECONDS,
) -> TranscribeResult:
    """Transkribiert Stueck fuer Stueck. Nach jedem Chunk:
    - progress_cb(frac)       -> bisheriger Fortschritt [0..1]
    - segment_cb(segment)     -> einzelnes {start,end,text}-Dict (schon mit
                                  absolutem Zeitstempel relativ zum Gesamt-
                                  Audio, damit die UI es direkt anzeigen kann)
    - cancel_event            -> wird vor jedem Chunk geprueft; bei set()
                                  steigt die Funktion mit CancelledByUser aus.

    Wirft RuntimeError bei Setup-Problemen, ImportError wird in RuntimeError
    mit klarer Erklaerung umgebaut.
    """
    from app.services.job_service import CancelledByUser  # lazy wegen Zyklen

    if not audio_path.exists():
        raise RuntimeError(f"Audio-Datei fehlt: {audio_path}")

    duration = await _get_audio_duration(audio_path)
    if duration <= 0:
        raise RuntimeError("Dauer der Audio-Datei nicht ermittelbar")

    # Bei sehr kurzen Quellen (<1.5*chunk) machen wir es in einem Rutsch
    if duration <= chunk_seconds * 1.5:
        def _single():
            return _transcribe_file_once(engine, model, str(audio_path))
        try:
            res = await asyncio.to_thread(_single)
        except ImportError as e:
            raise RuntimeError(
                f"Engine '{engine}' ist nicht installiert: {e}"
            )
        segs: list[dict] = []
        for s in res["segments"]:
            seg = {
                "start": float(s.get("start", 0.0)),
                "end":   float(s.get("end", 0.0)),
                "text":  (s.get("text") or "").strip(),
            }
            if seg["text"]:
                segs.append(seg)
                if segment_cb:
                    segment_cb(seg)
        if progress_cb: progress_cb(1.0)
        return TranscribeResult(segments=segs, language=res.get("language", ""),
                                engine=engine, model=model)

    # Langere Quellen: Chunking mit kleinem Overlap, damit Worte nicht
    # an Chunk-Grenzen abgeschnitten werden.
    all_segs: list[dict] = []
    detected_lang = ""
    offset = 0.0
    stride = chunk_seconds - CHUNK_OVERLAP
    chunk_count = int((duration + stride - 1) // stride)
    chunk_idx = 0

    from app.config import TMP_DIR

    while offset < duration:
        if cancel_event and cancel_event.is_set():
            raise CancelledByUser()

        chunk_idx += 1
        length = min(chunk_seconds, duration - offset)
        chunk_wav = TMP_DIR / f"tx-{audio_path.stem}-{chunk_idx:04d}.wav"
        try:
            await _extract_audio_chunk(audio_path, chunk_wav, offset, length)
            try:
                chunk_res = await asyncio.to_thread(
                    _transcribe_file_once, engine, model, str(chunk_wav),
                )
            except ImportError as e:
                raise RuntimeError(
                    f"Engine '{engine}' ist nicht installiert: {e}"
                )
            if not detected_lang and chunk_res.get("language"):
                detected_lang = chunk_res["language"]
            # Segmente mit Offset verschieben
            for s in chunk_res["segments"]:
                text = (s.get("text") or "").strip()
                if not text:
                    continue
                start = float(s.get("start", 0.0)) + offset
                end   = float(s.get("end", 0.0)) + offset
                # Bei Overlap koennen doppelte Eintraege vorkommen: wenn
                # das letzte gespeicherte Segment denselben Text im selben
                # Zeitfenster hat, ueberspringen.
                if all_segs and all_segs[-1]["text"] == text \
                        and abs(all_segs[-1]["start"] - start) < 1.0:
                    continue
                seg = {"start": start, "end": end, "text": text}
                all_segs.append(seg)
                if segment_cb:
                    segment_cb(seg)
        finally:
            try: chunk_wav.unlink(missing_ok=True)
            except OSError: pass

        offset += stride
        if progress_cb:
            progress_cb(min(0.99, chunk_idx / max(1, chunk_count)))

    if progress_cb: progress_cb(1.0)
    return TranscribeResult(
        segments=all_segs, language=detected_lang, engine=engine, model=model,
    )


def segments_to_vtt(segments: list[dict]) -> str:
    """Wie segments_to_srt, aber als WebVTT (für HTML5 <track kind="captions">).
    Unterschiede zu SRT: Header "WEBVTT", Punkt statt Komma als Dezimal-
    Trenner, keine Cue-Nummern noetig."""
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
        return f"{hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}"

    lines: list[str] = ["WEBVTT", ""]
    for seg in segments:
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        lines.append(f"{fmt(start)} --> {fmt(end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def remap_segments_for_edl(
    segments: list[dict],
    edl_clips: list[dict],
    clip_id: Optional[str] = None,
) -> list[dict]:
    """Rechnet Original-Segmente auf die Zeitachse eines EDL-Exports um.

    edl_clips ist eine Liste mit Dicts oder Pydantic-Objekten, die die
    Felder ``src_start``, ``src_end`` und ``id`` haben. Wenn ``clip_id``
    gesetzt ist, werden nur die Segmente des entsprechenden Clips
    geliefert (Einzel-Clip-Export). Sonst werden alle Clips in Timeline-
    Reihenfolge aneinandergehaengt und die Segmente auf den jeweiligen
    Export-Offset gemapped.

    Segmente, die an Clip-Grenzen liegen, werden zugeschnitten -- das
    Start- oder End-Timing kann dadurch kuerzer werden als im Original.
    """
    def _get(clip, key, default=None):
        if isinstance(clip, dict):
            return clip.get(key, default)
        return getattr(clip, key, default)

    clips = list(edl_clips or [])
    if clip_id:
        clips = [c for c in clips if _get(c, "id") == clip_id]

    out: list[dict] = []
    offset = 0.0
    for clip in clips:
        c_start = float(_get(clip, "src_start", 0.0) or 0.0)
        c_end   = float(_get(clip, "src_end", 0.0) or 0.0)
        if c_end <= c_start:
            continue
        for s in segments:
            try:
                ss = float(s.get("start", 0.0))
                se = float(s.get("end", 0.0))
            except (TypeError, ValueError):
                continue
            if se <= c_start or ss >= c_end:
                continue
            eff_s = max(ss, c_start)
            eff_e = min(se, c_end)
            if eff_e <= eff_s:
                continue
            text = (s.get("text") or "").strip()
            if not text:
                continue
            out.append({
                "start": offset + (eff_s - c_start),
                "end":   offset + (eff_e - c_start),
                "text":  text,
            })
        offset += c_end - c_start
    return out


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
