"""
CuttOffl Backend - Virtuelle Ordner-Hierarchie für die Bibliothek.

Ordner sind rein logisch: sie werden als Pfad-String je Datei gespeichert
(Spalte files.folder_path), aber Dateien leben alle flach im
ORIGINALS_DIR. Damit vermeiden wir Filesystem-Verschachtelung, behalten
UUID-basierte Namen und machen Umbenennen / Verschieben zu reinen
DB-Updates.

Alle Helfer validieren den Pfad streng, um Path-Traversal, absolute
Pfade und aehnliche Missbraeuche auszuschliessen.

Format:
  - Leerstring ""         = Wurzel
  - "/"                   = Wurzel (intern auf "" normalisiert)
  - "Urlaub 2026"         = Ordner auf Wurzelebene
  - "Urlaub 2026/Tag 1"   = Unterordner
  - max. Tiefe: MAX_DEPTH
  - pro Segment: MAX_SEG_LEN Zeichen
"""

from __future__ import annotations

import re

MAX_DEPTH = 8
MAX_SEG_LEN = 80

# Unerlaubte Zeichen in Segmenten:
#   / \   Trenner / Windows-Trenner
#   :     Laufwerks-/Alt-Separator
#   \x00  NUL
#   < > | ? *  reservierte/unschoene Zeichen
_BAD = re.compile(r"[/\\:\x00<>|?*]")


class FolderError(ValueError):
    """Wird geworfen, wenn ein Ordnerpfad ungültig ist."""


def normalize(path: str | None) -> str:
    """Normalisiert einen Ordnerpfad. Leerstring = Wurzel.
    Entfernt fuehrende/abschliessende Slashes und leere Segmente,
    wirft FolderError bei Verstoessen gegen die Regeln.
    """
    if path is None:
        return ""
    p = str(path).strip()
    if p in ("", "/"):
        return ""

    # fuehrende/abschliessende Slashes abwerfen
    p = p.strip("/")

    segments = [s for s in p.split("/") if s != ""]
    if len(segments) > MAX_DEPTH:
        raise FolderError(f"Pfad tiefer als {MAX_DEPTH} Ebenen")

    cleaned: list[str] = []
    for seg in segments:
        s = seg.strip()
        if s in ("", ".", ".."):
            raise FolderError("Ungültiges Pfadsegment (., .., leer)")
        if len(s) > MAX_SEG_LEN:
            raise FolderError(f"Pfadsegment länger als {MAX_SEG_LEN} Zeichen")
        if _BAD.search(s):
            raise FolderError("Pfadsegment enthaelt unerlaubte Zeichen")
        cleaned.append(s)

    return "/".join(cleaned)


def parent_of(path: str) -> str:
    """Gibt den Eltern-Ordner zurück, '' für die Wurzel."""
    p = normalize(path)
    if not p:
        return ""
    parts = p.split("/")
    return "/".join(parts[:-1])


def is_descendant(child: str, ancestor: str) -> bool:
    """True, wenn child gleich ancestor oder darin enthalten ist."""
    c = normalize(child)
    a = normalize(ancestor)
    if a == "":
        return True
    if c == a:
        return True
    return c.startswith(a + "/")


def rename_prefix(path: str, old_prefix: str, new_prefix: str) -> str:
    """Für Rename/Move: ersetzt den Ordner-Prefix in einem Pfad.
    Pfade, die nicht unter old_prefix liegen, bleiben unveraendert.
    """
    p = normalize(path)
    o = normalize(old_prefix)
    n = normalize(new_prefix)
    if o == "":
        return n if p == "" else (f"{n}/{p}" if n else p)
    if p == o:
        return n
    if p.startswith(o + "/"):
        rest = p[len(o) + 1:]
        return f"{n}/{rest}" if n else rest
    return p
