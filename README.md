# CuttOffl

Offline-first Video-Cutter/Editor mit Edit Decision List (EDL) und
Hybrid-Render (keyframe-genau + frame-genau). Teil der Vault-Familie.
Fokus auf große Dateien, lokal, ohne Cloud, ohne Konto.

## Status

**Backend v0.7.0**

- FastAPI, läuft nativ auf Mac und Linux/Raspberry Pi
- SQLite via `aiosqlite`, natives SQL (kein ORM)
- Multipart-Upload mit sofortiger `ffprobe`-Metadatenextraktion
- Auto-Proxy nach Upload (480p H.264, GOP = 1 s, schnelles Scrubbing)
- Keyframe-Liste + Snap-Endpunkt (nächster/vorheriger/nearest)
- Thumbnail, Frame-Sprite (Tile-JPEG) und Audio-Wellenform aus dem Proxy
- In-Process async Job-Queue mit Persistenz und WebSocket-Progress
- EDL-CRUD: Projekte, Timeline, Output-Profil mit Input-Validierung
- Hybrid-Render: `copy` (keyframe-genau, verlustfrei) + `reencode`
  (frame-genau, neu kodiert); Segmente per `concat`-Demuxer verbunden
- HW-Encoder-Erkennung: VideoToolbox (Mac), V4L2 (Pi), libx264-Fallback
- Codec-Empfehlungen je nach Umgebung (Apple Silicon, Pi, Software)
- Proxy-Streaming mit HTTP-Range (206 Partial Content)
- Export-Liste und -Download, Original-Download
- System-Endpunkte für Disk-Usage und Dashboard-Overview
- Error-Sanitizer: absolute Pfade werden nicht nach außen gereicht

**Frontend v0.4.0**

- Svelte 5 (Runes) + Vite 8 + Tailwind 4, kein SvelteKit
- Studio-Layout: Sidebar (kollabierbar, resizable) + Content + JobsBar
- Views: **Dashboard**, **Bibliothek**, **Editor**, **Einstellungen**, **Über**
- Fonts lokal via `@fontsource`: **Chakra Petch** (UI), **JetBrains Mono** (Zahlen)
- FontAwesome-Icons lokal (kein CDN)
- Akzentfarbe GitHub-Blau, semantische Farben für Timeline-Elemente
- **Dashboard** mit KPIs, Speicher-Übersicht je Datenbereich,
  Codec-Empfehlung und Liste der neuesten Videos
- **Editor** mit HTML5-Proxy-Player und Canvas-Timeline
  (Keyframe-Marker, Thumbnail-Streifen, Audio-Wellenform, Clip-Modi)
- Schneiden: In/Out, Split, Trim per Drag, Undo/Redo, Auto-Save der EDL
- Keyframe-Magnet (Snap) mit sichtbarem Modus-Wechsel copy/reencode
- Smoothes Mitlaufen der Timeline ab dem letzten Drittel (toggle-bar)
- Vorschau für Auswahl, einen Clip oder die ganze Timeline
- Export-Dialog mit Codec-Empfehlung für das aktuelle Gerät
- **Danke-Overlay** (zentriertes Modal) mit Ko-fi-Link und QR-Codes für
  Bitcoin, Dogecoin, Ethereum
- **Über-Seite** mit Lizenz, Haftungsausschluss und GitHub-Link
- Alle UI-Präferenzen persistiert im localStorage

Erweiterungsideen: Sub-Ordner und Multi-Ansichten in der Bibliothek,
Bulk-Aktionen, ZIP-Download, optionale Token-Auth, Rate-Limiting,
tus.io-Chunked-Upload für sehr große Dateien.

## Ports

| Port  | Dienst                  |
|-------|-------------------------|
| 10036 | Backend (FastAPI)       |
| 10037 | Frontend (Vite Dev)     |
| 10038 | Reserve                 |

## Voraussetzungen

- macOS (Apple Silicon empfohlen) oder Linux (inkl. Raspberry Pi 5)
- Python 3.11+
- FFmpeg 6+ im PATH (`brew install ffmpeg` bzw. `apt install ffmpeg`)
- Node.js 20+ und npm

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
./start.sh           # beide Prozesse starten
./start.sh status    # zeigt, was läuft
./start.sh logs      # Logs live tailen
./start.sh stop      # beide beenden
./start.sh restart   # stop + start
./start.sh backend   # nur Backend
./start.sh frontend  # nur Frontend
```

Logs landen in `logs/backend.log` und `logs/frontend.log`, PIDs in
`logs/*.pid`.

- Frontend:  http://127.0.0.1:10037
- Backend:   http://127.0.0.1:10036/docs
- Health:    http://127.0.0.1:10036/api/ping
- WebSocket: ws://127.0.0.1:10036/ws/jobs

Das Frontend proxyt `/api` und `/ws` automatisch auf Port 10036.

## Verzeichnisstruktur

```
CuttOffl/
├── backend/
│   ├── app/
│   │   ├── main.py             FastAPI-App, Lifespan, Router-Registrierung
│   │   ├── config.py           Pfade, Port, Version, Umgebungsvariablen
│   │   ├── db.py               aiosqlite-Wrapper + Migrations
│   │   ├── routers/            system, upload, files, probe, proxy,
│   │   │                        thumbnail, sprite, projects, exports,
│   │   │                        jobs, ws
│   │   ├── services/           ffmpeg, probe, hwaccel, codec,
│   │   │                        proxy, thumbnail, sprite, waveform,
│   │   │                        keyframe, render, job, error_helper
│   │   └── models/             Pydantic-Schemas (schemas.py, edl.py)
│   ├── requirements.txt
│   └── .env.dev
├── frontend/
│   ├── src/
│   │   ├── App.svelte          Shell: Sidebar + Content + JobsBar + Overlays
│   │   ├── components/         Player, Timeline, Resizer, JobsBar,
│   │   │                        Sidebar, ExportDialog, ThanksOverlay,
│   │   │                        ToastHost, ErrorBoundary, PanelHeader
│   │   ├── views/              Dashboard, Library, Editor, Settings, About
│   │   └── lib/                api, editor, nav, persist, theme,
│   │                            toast, ws, ui, meta
│   ├── public/images/          QR-Codes für Krypto-Spenden
│   ├── package.json
│   └── vite.config.js
├── data/
│   ├── originals/              Hochgeladene Videos
│   ├── proxies/                Proxy-Vorschau (480p H.264)
│   ├── thumbs/                 Einzel-Thumbnails
│   ├── sprites/                Tile-JPEGs für Timeline-Streifen
│   ├── waveforms/              Audio-Peak-JSON je Datei
│   ├── exports/                Fertige Schnitte
│   ├── tmp/                    Render-Zwischenschritte
│   └── db/                     SQLite-Datei
├── logs/                       start.sh-Logs und PID-Dateien
├── LICENSE
├── README.md
├── setup.sh
└── start.sh
```

## API

Vollständige interaktive Dokumentation in Swagger UI: `/docs`.
Übersicht der wichtigsten Endpunkte:

| Methode | Endpunkt                                  | Zweck                                  |
|---------|-------------------------------------------|----------------------------------------|
| GET     | `/api/ping`                               | Health, Version, HW-Encoder            |
| GET     | `/api/system/overview`                    | Dashboard-Statistik                    |
| GET     | `/api/system/storage`                     | Disk-Nutzung je Datenbereich           |
| GET     | `/api/system/codecs`                      | Codec-Empfehlungen für diese Umgebung  |
| POST    | `/api/upload`                             | Video hochladen (Multipart)            |
| GET     | `/api/files`                              | Liste aller Originale                  |
| GET     | `/api/files/{id}`                         | Metadaten einer Datei                  |
| GET     | `/api/files/{id}/download`                | Original-Datei herunterladen           |
| DELETE  | `/api/files/{id}`                         | Original + Ableitungen löschen         |
| GET     | `/api/probe/{id}`                         | Rohe ffprobe-Ausgabe                   |
| GET     | `/api/proxy/{id}`                         | Proxy-Stream mit Range-Support         |
| GET     | `/api/proxy/{id}/keyframes`               | Keyframe-Zeitstempel                   |
| GET     | `/api/proxy/{id}/snap?t=…&mode=…`         | Keyframe-Snap                          |
| POST    | `/api/proxy/{id}/generate`                | Proxy-Job manuell                      |
| GET     | `/api/thumbnail/{id}`                     | Thumbnail-JPEG                         |
| GET     | `/api/sprite/{id}` / `/meta`              | Tile-Sprite + Raster-Metadaten         |
| GET     | `/api/waveform/{id}`                      | Peak-JSON für Timeline                 |
| GET/POST/PUT/DELETE | `/api/projects`                 | Projekte / EDL                         |
| POST    | `/api/projects/{id}/render`               | Render-Job starten                     |
| GET     | `/api/exports`                            | Fertige Renderings                     |
| GET     | `/api/exports/{id}/download`              | Fertiges Video mit lesbarem Namen      |
| DELETE  | `/api/exports/{id}`                       | Fertiges Video löschen                 |
| GET     | `/api/jobs` / `/active` / `/{id}`         | Job-Status                             |
| WS      | `/ws/jobs`                                | Live-Progress aller Jobs               |

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

In der App findest du den Spenden-Dialog als zentriertes Overlay
(Button **Danke** unten in der Seitenleiste) mit QR-Codes zum Scannen.
Projekt-Infos, Lizenz und Haftungsausschluss stehen auf der Seite
**Über**.
