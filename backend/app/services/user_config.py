"""
CuttOffl Backend - Nutzer-Konfiguration (persistent zwischen Starts).

Speichert veraenderbare Pfad-Einstellungen in einer JSON-Datei neben
der App (user_config.json). Das Format ist absichtlich trivial, damit
die Datei bei Bedarf auch per Texteditor oder Backup-Skript
bearbeitbar bleibt.

Aktuell gespeichert:
  - originals_dir: Verzeichnis für hochgeladene Videos
  - exports_dir:   Verzeichnis für gerenderte Schnitte

Wird beim Start ausgelesen und überschreibt die Default-Pfade aus
config.py. Aenderungen zur Laufzeit erfordern einen Backend-Neustart.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


CONFIG_FILENAME = "user_config.json"


def _config_path() -> Path:
    """Liegt im Projekt-Root (eine Ebene über backend/)."""
    return Path(__file__).resolve().parent.parent.parent.parent / CONFIG_FILENAME


def load() -> dict:
    p = _config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"user_config.json nicht lesbar: {e}")
        return {}


def save(data: dict) -> Path:
    p = _config_path()
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def get(key: str, default=None):
    return load().get(key, default)


def set_key(key: str, value) -> None:
    data = load()
    if value is None:
        data.pop(key, None)
    else:
        data[key] = value
    save(data)


def validate_directory(path_str: str) -> Optional[str]:
    """Prüft, ob der Pfad als Datenverzeichnis taugt.
    Gibt None bei OK zurück, sonst eine Fehlermeldung.
    """
    if not path_str or not path_str.strip():
        return "Pfad darf nicht leer sein"
    p = Path(path_str).expanduser()
    try:
        p = p.resolve()
    except Exception:
        return "Pfad konnte nicht aufgeloest werden"
    if not p.exists():
        return f"Verzeichnis existiert nicht: {p}"
    if not p.is_dir():
        return "Pfad ist kein Verzeichnis"
    # Schreibtest
    probe = p / ".cuttoffl_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as e:
        return f"Kein Schreibrecht: {e}"
    return None
