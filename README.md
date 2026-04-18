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

**Schnitt & Timeline**
- Keyframe-Magnet in der Timeline (copy/reencode wird live angezeigt)
- Schneiden per In/Out, Split, Trim-Drag -- Undo/Redo, Auto-Save
- Vorschau für Auswahl, einzelne Clips oder die ganze EDL
- Smoothes Mitlaufen der Timeline beim Abspielen; Zoom-Presets
  (Übersicht / Standard / Genauer / Frame-nah / Frame-genau) und
  gleichmäßige Thumbnail-Verteilung unabhängig vom Zoom
- Hybrid-Render: so viel wie möglich kopieren, nur nötige Schnitte
  neu kodieren

**Bibliothek**
- Virtuelle Ordner mit Drag & Drop, Ordner-Picker, Bulk-Verschieben
- Mehrere Ansichten (Kacheln, Liste, Kompakt), Sortierung, Filter
  für Status/Codec/Auflösung/Tag und Volltext-Suche (inkl. Tags)
- Tag-Editor inline mit Farb-Chips und Autocomplete
- SHA-256-Duplikatprüfung beim Upload; ZIP-Download ganzer Ordner

**KI-Untertitel (optional)**
- Transkription mit Whisper: mlx-whisper (Apple Silicon), faster-
  whisper (portabel), openai-whisper (Referenz). Modelle werden
  lokal gesucht -- keine doppelten Downloads, wenn ein HuggingFace-
  oder openai-Cache schon existiert.
- Live-Anzeige: Segmente erscheinen im Panel, während transkribiert
  wird; abbrechbar ohne Neustart; auswählbares Modell.
- Mitlaufendes Transkript beim Abspielen (eigener Follow-Toggle),
  Inline-Suche mit Treffer-Navigation, Untertitel-Overlay im Player.
- Export als **SRT** und **WebVTT** -- auch für geschnittene Exports
  (Segmente werden aus der EDL auf die neue Zeitachse umgerechnet).

**Export & Download**
- Fertige Videos wieder in die Bibliothek übernehmen für weiteren Schnitt
- Bundle-ZIP je Datei und je Ordner: Video + passende SRT + VTT
- Codec-Empfehlung für die erkannte Hardware

**Session & UI**
- Status-LEDs im Footer für Backend, Live-Events und Transkription
- Verschiebbares Info-Panel mit kontextabhängigem Inhalt
  (Tastenkürzel im Editor, Tipps in der Bibliothek, usw.)
- Pfad-basierte Deeplinks (`/library/Urlaub/2026`, `/editor/file/…`,
  `/settings/transkription`) -- Browser-Back/Forward funktioniert
- Dark- und Light-Mode, alle UI-Präferenzen bleiben lokal

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

**Einmalig einrichten:**

```bash
./setup.sh                         # Backend-venv + pip install + ffmpeg-Check
./setup.sh --with-transcription    # optional: zusätzlich Whisper für KI-Untertitel
cd frontend && npm install         # Frontend-Dependencies
```

**Starten:**

```bash
./start.sh                         # beide Prozesse starten
```

Das Start-Script kennt folgende Befehle:

| Befehl                 | Was passiert                              |
|------------------------|-------------------------------------------|
| `./start.sh`           | Backend + Frontend hochfahren             |
| `./start.sh status`    | PIDs und Port-Status anzeigen             |
| `./start.sh logs`      | Logs beider Prozesse live mittailen       |
| `./start.sh stop`      | beide sauber stoppen                      |
| `./start.sh restart`   | beide neu starten                         |
| `./start.sh backend`   | nur Backend (nützlich nach pip install)   |
| `./start.sh frontend`  | nur Frontend                              |

Nach dem Start:

- Frontend: <http://127.0.0.1:10037>
- Backend-Docs: <http://127.0.0.1:10036/docs>
- Logs: `logs/backend.log`, `logs/frontend.log` (PIDs in `logs/*.pid`)

**Erste Schritte in der App:**

1. Bibliothek öffnen, ein Video per Drag & Drop ins Fenster ziehen
   oder den "Video hochladen"-Button nutzen.
2. Nach dem Upload wird automatisch ein Proxy (480p) erzeugt;
   während dieser Zeit läuft die Status-LED am unteren Rand.
3. Kachel anklicken → Editor öffnet sich mit Timeline. Mit `I` / `O`
   Anfang und Ende markieren, Enter übernimmt den Clip.
4. Rechts unten auf **Rendern** klicken für das fertige Video.
5. Unter **Einstellungen → Transkription** Whisper einrichten
   (Details unten), danach im Editor den Tab *Transkript* nutzen.

## KI-Transkription (optional)

CuttOffl kann Videos lokal per Whisper transkribieren und daraus
SRT- und WebVTT-Untertitel erzeugen -- sowohl für Originale als auch
für geschnittene Exports. Nichts geht dabei in die Cloud.

**Drei Engines werden unterstützt** (jeweils lazy geladen, die App
läuft auch ohne). Welche du installierst, hängt von deiner Hardware ab:

| Engine           | Empfohlen für               | Installation                     |
|------------------|-----------------------------|----------------------------------|
| `mlx-whisper`    | Apple Silicon (M1–M4)       | `pip install mlx-whisper`        |
| `faster-whisper` | Pi 5, Linux, Intel, Windows | `pip install faster-whisper`     |
| `openai-whisper` | Referenz / Fallback         | `pip install openai-whisper`     |

**Einrichten:**

```bash
./setup.sh --with-transcription      # plattformpasend mlx + faster
# oder in die bestehende venv
cd backend && source .venv/bin/activate
pip install -r requirements-transcription.txt
./start.sh restart backend
```

**Modelle finden / wählen:**

Unter **Einstellungen → Transkription** siehst du:

- Ampel: grün = einsatzbereit, gelb = Engine da aber kein Modell,
  rot = nichts installiert. Zusätzlich eine LED im Footer für den
  Gesamtzustand.
- Liste der **installierten Pakete** (mit empfohlener Engine für
  deine Plattform).
- Liste der **gefundenen Modelle** auf der Platte. CuttOffl scannt
  dafür die üblichen Caches:
  - `~/.cache/huggingface/hub/` (mlx- und faster-whisper)
  - `~/.cache/whisper/` (openai-whisper)
  - `~/Library/Caches/huggingface/hub/`
  - und den Cache eines Voice2Text-Schwesterprojekts, falls vorhanden
- Ein Klick auf **Auswählen** setzt ein Modell aktiv; die Wahl bleibt
  in `user_config.json` erhalten.
- **Festplatte scannen** findet nachträglich installierte Modelle.

**Transkribieren:**

Im Editor rechts auf den Tab **Transkript** klicken → **Transkribieren**.
Der Job läuft in 25-Sekunden-Blöcken; Segmente erscheinen sofort
im Panel, du kannst den Lauf jederzeit abbrechen. Während der
Wiedergabe wandert das Highlight durch die Liste mit
(Mitlaufen-Toggle oben rechts im Panel).

**Untertitel exportieren:**

- Im Transkript-Panel gibt es **SRT-** und **VTT-Download**.
- In der Bibliothek erscheint bei jedem Video mit Transkript ein
  **CC-Knopf** (nur SRT) und ein **ZIP-Knopf** (Video + SRT + VTT).
- Für fertige geschnittene Videos gilt dasselbe unter **Fertige
  Videos** -- die Zeitmarken werden dabei aus der EDL auf die
  geschnittene Timeline umgerechnet, damit sie zum Export passen.

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
| GET     | `/api/files/{id}/download`                | Nur Video                      |
| GET     | `/api/files/{id}/bundle.zip`              | Video + SRT + VTT              |
| GET     | `/api/proxy/{id}`                         | Proxy-Stream (Range-Support)   |
| GET     | `/api/proxy/{id}/keyframes`               | Keyframe-Zeitstempel           |
| GET     | `/api/sprite/{id}` / `/meta`              | Timeline-Tile-JPEG             |
| GET     | `/api/waveform/{id}`                      | Audio-Peaks                    |
| GET/POST/PUT/DELETE | `/api/projects`                 | EDL-Projekte                   |
| POST    | `/api/projects/{id}/render`               | Render-Job starten             |
| GET     | `/api/exports`                            | Fertige Renderings             |
| GET     | `/api/exports/{id}/bundle.zip`            | Export + passende SRT + VTT    |
| POST    | `/api/exports/{id}/import-to-library`     | Export als neue Quelle         |
| GET     | `/api/transcription/status`               | Engines + gefundene Modelle    |
| POST    | `/api/transcription/scan`                 | Platte nach Modellen scannen   |
| PUT     | `/api/transcription/preference`           | aktives Modell setzen          |
| POST    | `/api/transcript/{id}/generate`           | Transkription starten          |
| GET     | `/api/transcript/{id}`                    | Geparste Segmente              |
| GET     | `/api/transcript/{id}.srt` / `.vtt`       | Untertitel-Datei               |
| POST    | `/api/jobs/{id}/cancel`                   | Laufenden Job abbrechen        |
| WS      | `/ws/jobs`                                | Live-Fortschritt aller Jobs    |

## Verzeichnisse

```
CuttOffl/
├── backend/app/          FastAPI, Services, Router, Schemas
├── frontend/src/         Svelte-App (Views, Components, lib)
├── data/                 originals, proxies, exports, thumbs, sprites,
│                         waveforms, transcripts, tmp, db
├── logs/                 Laufzeit-Logs + PIDs
├── setup.sh
└── start.sh
```

## Lokal & Offline

Die App läuft nach dem einmaligen Einrichten vollständig offline:

- Frontend spricht ausschließlich mit dem lokalen Backend.
- Backend ruft selbst keine externen Dienste auf.
- **Whisper-Modelle** werden nur beim bewusst angestoßenen Download
  aus den Einstellungen gezogen. Danach setzt CuttOffl bei jedem
  Transkriptions-Lauf `HF_HUB_OFFLINE=1` -- es gibt auch keine
  Cache-Aktualitäts-Prüfung an huggingface.co mehr.
- **Keine Telemetrie, kein Analytics, keine CDN-Aufrufe**.

## Lizenz

Nicht-kommerzielle Lizenz v2.0 (`LicenseRef-CuttOffl-NC-2.0`), basierend auf
[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.de)
mit Ergänzungen. Copyright 2026 HalloWelt42. Private Nutzung erlaubt,
kommerzielle Nutzung und Veröffentlichung modifizierter Versionen nicht.
Vollständig in [`LICENSE`](LICENSE) und in der App unter **Über**.

Die verwendete Drittsoftware (alles MIT / Apache / BSD / OFL / LGPL)
und die Lizenzen der optionalen Whisper-Modelle stehen in
[`NOTICE.md`](NOTICE.md). Alle Lizenzen sind mit der NC-Lizenz unseres
Projekts kompatibel.

## Unterstützung

Wenn es nützlich ist und du die Weiterentwicklung unterstützen möchtest --
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
