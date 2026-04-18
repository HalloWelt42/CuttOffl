"""
CuttOffl Backend - SQLite-Zugriff (natives SQL, kein ORM).

Migrations werden beim Startup idempotent ausgeführt.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional, Sequence

import aiosqlite

from app.config import DB_PATH


logger = logging.getLogger(__name__)


SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS files (
        id              TEXT PRIMARY KEY,
        original_name   TEXT NOT NULL,
        stored_name     TEXT NOT NULL,
        path            TEXT NOT NULL,
        size_bytes      INTEGER NOT NULL,
        mime_type       TEXT,
        duration_s      REAL,
        width           INTEGER,
        height          INTEGER,
        fps             REAL,
        video_codec     TEXT,
        audio_codec     TEXT,
        has_proxy       INTEGER NOT NULL DEFAULT 0,
        proxy_path      TEXT,
        proxy_status    TEXT NOT NULL DEFAULT 'none',
        thumb_path      TEXT,
        keyframes_json  TEXT,
        keyframe_count  INTEGER,
        sprite_path     TEXT,
        sprite_interval REAL,
        sprite_tile_w   INTEGER,
        sprite_tile_h   INTEGER,
        sprite_cols     INTEGER,
        sprite_rows     INTEGER,
        sprite_count    INTEGER,
        waveform_path   TEXT,
        waveform_samples INTEGER,
        waveform_rate    REAL,
        folder_path     TEXT NOT NULL DEFAULT '',
        tags_json       TEXT NOT NULL DEFAULT '[]',
        sha256          TEXT,
        transcript_path  TEXT,
        transcript_lang  TEXT,
        transcript_model TEXT,
        probe_json      TEXT,
        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_files_proxy_status ON files(proxy_status)",
    # Schema-Migrations (idempotent) für bestehende DBs
    "ALTER TABLE files ADD COLUMN sprite_path TEXT",
    "ALTER TABLE files ADD COLUMN sprite_interval REAL",
    "ALTER TABLE files ADD COLUMN sprite_tile_w INTEGER",
    "ALTER TABLE files ADD COLUMN sprite_tile_h INTEGER",
    "ALTER TABLE files ADD COLUMN sprite_cols INTEGER",
    "ALTER TABLE files ADD COLUMN sprite_rows INTEGER",
    "ALTER TABLE files ADD COLUMN sprite_count INTEGER",
    "ALTER TABLE files ADD COLUMN waveform_path TEXT",
    "ALTER TABLE files ADD COLUMN waveform_samples INTEGER",
    "ALTER TABLE files ADD COLUMN waveform_rate REAL",
    # Virtueller Ordnerpfad (leer = Wurzel, sonst 'A/B/C')
    "ALTER TABLE files ADD COLUMN folder_path TEXT NOT NULL DEFAULT ''",
    "CREATE INDEX IF NOT EXISTS idx_files_folder_path ON files(folder_path)",
    # Tags: JSON-Array normierter Tag-Strings. Leerer Array = '[]'.
    "ALTER TABLE files ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'",
    # SHA-256 der Originaldatei (Hex, 64 Zeichen). Für Duplikat-Erkennung.
    "ALTER TABLE files ADD COLUMN sha256 TEXT",
    "CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files(sha256)",
    # Transkription: Pfad zur SRT-Datei, erkannte Sprache, verwendetes
    # Modell. Wenn transcript_path NULL oder Datei fehlt, gilt das Video
    # als "ohne Transkript".
    "ALTER TABLE files ADD COLUMN transcript_path TEXT",
    "ALTER TABLE files ADD COLUMN transcript_lang TEXT",
    "ALTER TABLE files ADD COLUMN transcript_model TEXT",
    # Geschütztes Video: blockt keine API-Operationen, signalisiert
    # dem Frontend aber, dass dieses File besonders ist (aktuell nur
    # das Demo-Video). Die UI zeigt dann ein Schloss-Icon und einen
    # extra Warn-Dialog beim Löschen.
    "ALTER TABLE files ADD COLUMN protected INTEGER NOT NULL DEFAULT 0",
    """
    CREATE TABLE IF NOT EXISTS projects (
        id              TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        source_file_id  TEXT,
        edl_json        TEXT NOT NULL DEFAULT '{}',
        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY(source_file_id) REFERENCES files(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id              TEXT PRIMARY KEY,
        kind            TEXT NOT NULL,
        status          TEXT NOT NULL DEFAULT 'pending',
        progress        REAL NOT NULL DEFAULT 0.0,
        message         TEXT,
        file_id         TEXT,
        project_id      TEXT,
        result_path     TEXT,
        error           TEXT,
        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
)


class Database:
    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        for stmt in SCHEMA:
            try:
                await self._conn.execute(stmt)
            except Exception as e:
                # ALTER TABLE ADD COLUMN wirft "duplicate column name" bei
                # bereits migrierter DB -- das ist idempotent ok.
                msg = str(e).lower()
                if "duplicate column" in msg or "already exists" in msg:
                    continue
                raise
        await self._conn.commit()
        logger.info(f"Datenbank verbunden: {self._path}")

    async def disconnect(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Datenbank nicht verbunden")
        return self._conn

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        await self.conn.execute(sql, params)
        await self.conn.commit()

    async def executemany(self, sql: str, params_iter: Iterable[Sequence[Any]]) -> None:
        await self.conn.executemany(sql, params_iter)
        await self.conn.commit()

    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[aiosqlite.Row]:
        async with self.conn.execute(sql, params) as cur:
            return await cur.fetchone()

    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[aiosqlite.Row]:
        async with self.conn.execute(sql, params) as cur:
            return list(await cur.fetchall())


db = Database(str(DB_PATH))
