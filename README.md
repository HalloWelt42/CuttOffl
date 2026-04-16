<p align="center">
  <img src="docs/logo.png" alt="CuttOffl - Video Studio" width="260">
</p>

# CuttOffl

Video schneiden -- lokal, ohne Cloud, ohne Konto.

<p align="center">
  <img src="https://img.shields.io/badge/license-NC--2.0-blue" alt="Lizenz">
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Svelte-5-FF3E00?logo=svelte&logoColor=white" alt="Svelte 5">
  <img src="https://img.shields.io/badge/FFmpeg-6+-007808?logo=ffmpeg&logoColor=white" alt="FFmpeg 6+">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20RPi%205-lightgrey" alt="Plattformen">
</p>

CuttOffl ist ein Web-Interface für FFmpeg, das auf dem eigenen Rechner läuft.
Du lädst ein Video hoch, schneidest es in einer Timeline mit Keyframes,
Thumbnails und Wellenform, und exportierst das Ergebnis. Die Originaldateien
verlassen den Rechner nicht.

## Das Konzept in einem Absatz

Beim Upload wird ein kleiner **Proxy** (480p) erzeugt -- den lässt sich flüssig
scrubben, auch bei großen Quellen. Schnitte werden als **EDL** (Edit Decision
List) gespeichert, nicht als neue Datei. Beim Export entscheidet CuttOffl
segmentweise, ob **keyframe-genau ohne Neu-Kodierung** kopiert werden kann
(schnell, verlustfrei) oder ob ein Segment **frame-genau neu kodiert** werden
muss. Hardware-Encoder werden erkannt: VideoToolbox auf dem Mac, V4L2 auf dem
Pi, Software-Fallback sonst.

## Was es kann

- Timeline mit Keyframe-Magnet (copy/reencode wird live angezeigt)
- Schneiden per In/Out, Split, Trim-Drag -- Undo/Redo, Auto-Save
- Vorschau für Auswahl, einzelne Clips oder die ganze EDL
- Virtuelle Ordner in der Bibliothek, Verschieben per Ordner-Picker
- Hybrid-Render: so viel wie möglich kopieren, nur nötige Schnitte neu kodieren
- Fertige Videos wieder in die Bibliothek übernehmen für weiteren Schnitt
- Export mit Codec-Empfehlung für die erkannte Hardware
- Optional: KI-Transkription mit Whisper (mlx/faster/openai) und
  SRT-Untertitel samt klickbarem Transkript-Panel im Editor
- Live-Fortschritt aller Jobs per WebSocket

## Stack

- **Backend:** FastAPI, SQLite via `aiosqlite`, natives SQL
- **Frontend:** Svelte 5 (Runes) + Vite 8 + Tailwind 4, kein SvelteKit
- **Rendering:** FFmpeg mit Concat-Demuxer
- **Hardware:** VideoToolbox (Mac), V4L2 (Pi), libx264-Fallback

## Voraussetzungen

- macOS (Apple Silicon empfohlen) oder Linux inkl. Raspberry Pi 5
- Python 3.11+, Node.js 20+
- FFmpeg 6+ im `PATH` (`brew install ffmpeg` bzw. `apt install ffmpeg`)

## Installation & Start

```bash
./setup.sh                         # backend venv + pip install + ffmpeg-Check
./setup.sh --with-transcription    # optional: zusätzlich Whisper für SRT-Untertitel
cd frontend && npm install         # frontend deps
cd ..
./start.sh                         # startet beide Prozesse
```

Weitere Befehle: `status`, `logs`, `stop`, `restart`, `backend`, `frontend`.

- Frontend: <http://127.0.0.1:10037>
- Backend: <http://127.0.0.1:10036/docs>

Logs unter `logs/backend.log` und `logs/frontend.log`, PIDs in `logs/*.pid`.

## Ports

| Port  | Dienst           |
|-------|------------------|
| 10036 | Backend (FastAPI) |
| 10037 | Frontend (Vite)   |
| 10038 | Reserve           |

## API-Übersicht

Vollständig interaktiv in Swagger unter `/docs`. Die wichtigsten Pfade:

| Methode | Endpunkt                                  | Zweck                          |
|---------|-------------------------------------------|--------------------------------|
| POST    | `/api/upload`                             | Video hochladen                |
| GET     | `/api/files`                              | Originale listen               |
| GET     | `/api/proxy/{id}`                         | Proxy-Stream (Range-Support)   |
| GET     | `/api/proxy/{id}/keyframes`               | Keyframe-Zeitstempel           |
| GET     | `/api/sprite/{id}` / `/meta`              | Timeline-Tile-JPEG             |
| GET     | `/api/waveform/{id}`                      | Audio-Peaks                    |
| GET/POST/PUT/DELETE | `/api/projects`                 | EDL-Projekte                   |
| POST    | `/api/projects/{id}/render`               | Render-Job starten             |
| GET     | `/api/exports`                            | Fertige Renderings             |
| POST    | `/api/exports/{id}/import-to-library`     | Export als neue Quelle         |
| WS      | `/ws/jobs`                                | Live-Fortschritt aller Jobs    |

## Verzeichnisse

```
CuttOffl/
├── backend/app/          FastAPI, Services, Router, Schemas
├── frontend/src/         Svelte-App (Views, Components, lib)
├── data/                 originals, proxies, exports, thumbs, sprites,
│                         waveforms, tmp, db
├── logs/                 Laufzeit-Logs + PIDs
├── setup.sh
└── start.sh
```

## Lizenz

Nicht-kommerzielle Lizenz v2.0 (`LicenseRef-CuttOffl-NC-2.0`), basierend auf
[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.de)
mit Ergänzungen. Copyright 2026 HalloWelt42. Private Nutzung erlaubt,
kommerzielle Nutzung und Veröffentlichung modifizierter Versionen nicht.
Vollständig in [`LICENSE`](LICENSE) und in der App unter **Über**.

## Unterstuetzung

Wenn es nuetzlich ist und du die Weiterentwicklung unterstuetzen moechtest --
rein freiwillig:

<p>
  <a href="https://ko-fi.com/HalloWelt42">
    <img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Ko-fi">
  </a>
</p>

<p>
  <img src="https://img.shields.io/badge/Bitcoin-F7931A?style=for-the-badge&logo=bitcoin&logoColor=white" alt="Bitcoin">
  <code>bc1qnd599khdkv3v3npmj9ufxzf6h4fzanny2acwqr</code>
</p>
<p>
  <img src="https://img.shields.io/badge/Dogecoin-C2A633?style=for-the-badge&logo=dogecoin&logoColor=white" alt="Dogecoin">
  <code>DL7tuiYCqm3xQjMDXChdxeQxqUGMACn1ZV</code>
</p>
<p>
  <img src="https://img.shields.io/badge/Ethereum-3C3C3D?style=for-the-badge&logo=ethereum&logoColor=white" alt="Ethereum">
  <code>0x8A28fc47bFFFA03C8f685fa0836E2dBe1CA14F27</code>
</p>
