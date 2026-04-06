# CuttOffl

Offline-first Video-Cutter/Editor mit EDL und Chunked Processing.
Teil der Vault-Familie. Fokus auf große Dateien, nicht auf Echtzeit-Preview.

## Status

**Backend v0.5.0**

- FastAPI läuft nativ auf Mac (kein Docker)
- SQLite via `aiosqlite`, natives SQL
- Multipart-Upload mit sofortiger `ffprobe`-Metadatenextraktion
- Auto-Proxy nach Upload (480p H.264, GOP = 1 s, `libx264 -preset veryfast`)
- Keyframe-Extraktion per `ffprobe -skip_frame nokey` (pro Datei in DB)
- Thumbnail-Generierung (JPEG, Frame aus 1/10 der Laufzeit)
- In-Process async Job-Queue mit Persistenz
- WebSocket `/ws/jobs` für Live-Progress
- Proxy-Streaming mit HTTP-Range (206 Partial Content)
- HW-Encoder-Detection (VideoToolbox auf Mac, V4L2 auf Pi, Software-Fallback)
- **EDL-CRUD** (Projects-Tabelle, Pydantic-Schemas, Timeline + OutputProfile)
- **Hybrid-Render:** `copy` (keyframe-genau, verlustfrei) + `reencode` (frame-genau) pro Clip
- **Concat-Demuxer** fügt Segmente lossless zusammen
- **Keyframe-Snap-Endpunkt** (`GET /api/proxy/{id}/snap?t=x&mode=nearest|prev|next`)
- **Exports-Liste + Download** (`GET /api/exports`, `GET /api/exports/{job_id}/download`)

**Frontend v0.2.0**

- Svelte 5 (Runes) + Vite 8 + Tailwind 4, kein SvelteKit
- Studio-Layout: Sidebar (kollabierbar, resizable) + Content + JobsBar + Footer
- Views: Dashboard, Bibliothek, Editor-Stub, Einstellungen
- Fonts lokal via `@fontsource` (Barlow, JetBrains Mono, Quicksand), FontAwesome
- Theme (Dark/Hell) + Schriftgröße (small/normal/large), persistiert in localStorage
- Upload mit Progress, Thumbnail/Proxy-Status in Library
- Toast-System, Error-Boundary
- Live-Jobs-Anzeige via WebSocket

Erweiterungsideen: tus.io-Chunked-Upload fuer sehr grosse Dateien,
zusaetzliche Effekte (Fade, Speed), Multi-File-Projekte.

## Ports

| Port  | Dienst                  |
|-------|-------------------------|
| 10036 | Backend (FastAPI)       |
| 10037 | Frontend (Vite Dev)     |
| 10038 | Reserve                 |

## Voraussetzungen

- macOS (Apple Silicon), ARM64
- Python 3.11+
- FFmpeg 6+ im PATH (`brew install ffmpeg`)

## Installation

**Backend:**
```bash
./setup.sh
```
Legt `backend/.venv` an, installiert alle Python-Pakete und prüft `ffmpeg`.

**Frontend:**
```bash
cd frontend && npm install
```

## Start

**Ein-Befehl-Start (empfohlen):**
```bash
./start.sh          # beide Prozesse starten
./start.sh status   # zeigt, was läuft
./start.sh logs     # Logs live tailen
./start.sh stop     # beide beenden
./start.sh restart  # stop + start
./start.sh backend  # nur Backend starten
./start.sh frontend # nur Frontend starten
```

Logs landen in `logs/backend.log` und `logs/frontend.log`, PIDs in `logs/*.pid`.

- Frontend:  http://127.0.0.1:10037
- Backend:   http://127.0.0.1:10036/docs
- Health:    http://127.0.0.1:10036/api/ping
- WebSocket: ws://127.0.0.1:10036/ws/jobs

Frontend proxyt `/api` und `/ws` automatisch auf Port 10036.

## Verzeichnisstruktur

```
CuttOffl/
|-- backend/
|   |-- app/
|   |   |-- main.py          FastAPI-App, Lifespan, Router-Registrierung
|   |   |-- config.py        Pfade, Port, Umgebungsvariablen
|   |   |-- db.py            aiosqlite-Wrapper + Migrations
|   |   |-- routers/         system, upload, files, probe
|   |   |-- services/        ffmpeg, probe, hwaccel
|   |   \-- models/          Pydantic-Schemas
|   |-- requirements.txt
|   \-- .env.dev
|-- data/
|   |-- originals/           Hochgeladene Videos
|   |-- proxies/             Low-Res-Preview (später)
|   |-- exports/             Fertige Renderings (später)
|   |-- tmp/                 Chunks, Zwischenschritte
|   \-- db/                  SQLite-Datei
|-- setup.sh
|-- run.sh
\-- README.md
```

## API (v0.1.0)

| Methode | Endpunkt                | Zweck                                        |
|---------|-------------------------|----------------------------------------------|
| GET     | `/api/ping`             | Health + Version + erkannter HW-Encoder      |
| POST    | `/api/upload`           | Video hochladen (multipart, Feld `file`)     |
| GET     | `/api/files`            | Alle Originale auflisten                     |
| GET     | `/api/files/{id}`       | Metadaten einer Datei                        |
| DELETE  | `/api/files/{id}`       | Original + Proxy + DB-Eintrag löschen        |
| GET     | `/api/probe/{id}`       | Rohe `ffprobe`-Ausgabe (Cache oder live)     |

Alle Endpunkte sind in `/docs` testbar.

## Lizenz

CuttOffl steht unter der **Nicht-kommerziellen Lizenz v2.0**, basierend auf
Creative Commons CC BY-NC-ND 4.0 mit Zusatzbestimmungen des Rechteinhabers
(private Modifikation erlaubt, keine öffentliche Weiterverteilung).

- Volltext: siehe [`LICENSE`](LICENSE)
- SPDX-Identifier: `LicenseRef-CuttOffl-NC-2.0`
- Rechteinhaber: HalloWelt42

## Haftungsausschluss

**Privates, nicht-kommerzielles Projekt.**
CuttOffl ist ein privat entwickeltes Werkzeug und wird ohne jede Gewährleistung
bereitgestellt. Es besteht kein Anspruch auf Support, Fehlerbehebung, Updates
oder Weiterentwicklung. Die Nutzung erfolgt ausschließlich auf eigenes Risiko.

**Keine Gewährleistung.**
Die Software wird "wie sie ist" ohne Mängelgewähr zur Verfügung gestellt.
Es wird keine Garantie für Funktionsfähigkeit, Fehlerfreiheit, ununterbrochene
Verfügbarkeit, Sicherheit oder Eignung für einen bestimmten Zweck übernommen.

**Keine Haftung für Schäden.**
Der Rechteinhaber haftet in keinem Fall für direkte oder indirekte Schäden,
entgangene Gewinne, Datenverluste, Ausfallzeiten oder sonstige mittelbare
Schäden, die aus der Nutzung oder Nichtnutzbarkeit der Software entstehen,
soweit dies gesetzlich zulässig ist. Bitte regelmäßig eigene Sicherungskopien
der Originale und Projekte anlegen.

**Inhalte liegen in deiner Verantwortung.**
Du bist für alle Videos, Bilder, Tonspuren und sonstigen Inhalte, die du mit
CuttOffl verarbeitest, selbst verantwortlich. Das betrifft insbesondere
Urheberrechte, Persönlichkeitsrechte, Markenrechte und die Rechte der
dargestellten Personen. CuttOffl stellt nur ein Werkzeug bereit und prüft
keine Inhalte.

**Nicht für kommerziellen Einsatz.**
Die Lizenz gestattet ausschließlich private, nicht-kommerzielle Nutzung
(siehe Abschnitt Lizenz). Für den Einsatz in Unternehmen, Behörden oder im
Rahmen einer Erwerbstätigkeit ist eine gesonderte Vereinbarung erforderlich.

**Drittkomponenten.**
CuttOffl greift auf externe Programme zurück (insbesondere FFmpeg/FFprobe).
Für diese gelten die Lizenzen und Haftungsregelungen der jeweiligen Hersteller.

## Danke & Unterstützung

Wenn CuttOffl dir hilft und du die Weiterentwicklung unterstützen möchtest --
rein freiwillig:

- **Ko-fi:** <https://ko-fi.com/HalloWelt42>
- **Bitcoin:** `bc1qnd599khdkv3v3npmj9ufxzf6h4fzanny2acwqr`
- **Dogecoin:** `DL7tuiYCqm3xQjMDXChdxeQxqUGMACn1ZV`
- **Ethereum:** `0x8A28fc47bFFFA03C8f685fa0836E2dBe1CA14F27`

In der App findest du diese Infos unter **Danke & Über** (unten in der Seitenleiste).
