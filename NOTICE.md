# Lizenzen & Drittsoftware

CuttOffl selbst steht unter der **Nicht-kommerziellen Lizenz v2.0**
(`LicenseRef-CuttOffl-NC-2.0`, siehe `LICENSE`).

Diese Datei listet die verwendete Drittsoftware, Schriftarten und
optionalen KI-Modelle mit ihrer jeweiligen Lizenz auf -- alles ist
kompatibel mit unserer NC-Lizenz (permissive Lizenzen stehen der
NC-Bindung unserer eigenen Software nicht im Weg).

Stand: CuttOffl Backend 0.18.0 / Frontend 0.20.0.

---

## Backend (Python)

Pflicht-Abhängigkeiten (`backend/requirements.txt`):

| Paket                  | Lizenz             | Link |
|------------------------|--------------------|------|
| FastAPI                | MIT                | https://github.com/fastapi/fastapi |
| Uvicorn                | BSD-3-Clause       | https://github.com/encode/uvicorn |
| aiofiles               | Apache-2.0         | https://github.com/Tinche/aiofiles |
| aiosqlite              | MIT                | https://github.com/omnilib/aiosqlite |
| Pydantic               | MIT                | https://github.com/pydantic/pydantic |
| python-multipart       | Apache-2.0         | https://github.com/Kludex/python-multipart |
| websockets             | BSD-3-Clause       | https://github.com/python-websockets/websockets |
| httpx                  | BSD-3-Clause       | https://github.com/encode/httpx |

Optionale KI-Abhängigkeiten (`backend/requirements-transcription.txt`):

| Paket                  | Lizenz             | Link |
|------------------------|--------------------|------|
| mlx-whisper            | MIT                | https://github.com/ml-explore/mlx-examples |
| faster-whisper         | MIT                | https://github.com/SYSTRAN/faster-whisper |
| openai-whisper         | MIT                | https://github.com/openai/whisper |
| huggingface-hub        | Apache-2.0         | https://github.com/huggingface/huggingface_hub |
| CTranslate2            | MIT                | https://github.com/OpenNMT/CTranslate2 |

---

## Frontend (Node / Browser)

| Paket                  | Lizenz             | Link |
|------------------------|--------------------|------|
| Svelte 5               | MIT                | https://svelte.dev |
| Vite                   | MIT                | https://vitejs.dev |
| @sveltejs/vite-plugin-svelte | MIT          | https://github.com/sveltejs/vite-plugin-svelte |
| Tailwind CSS           | MIT                | https://tailwindcss.com |
| @tailwindcss/vite      | MIT                | https://tailwindcss.com |

Schriftarten & Icons:

| Asset                  | Lizenz             | Link |
|------------------------|--------------------|------|
| Chakra Petch (via @fontsource) | OFL-1.1    | https://fonts.google.com/specimen/Chakra+Petch |
| JetBrains Mono (via @fontsource) | OFL-1.1  | https://www.jetbrains.com/lp/mono |
| Font Awesome Free      | CC BY 4.0 · OFL-1.1 · MIT | https://fontawesome.com/license/free |

---

## Externe Binaries

| Binary                 | Lizenz             | Hinweis |
|------------------------|--------------------|---------|
| FFmpeg / FFprobe       | LGPL oder GPL (je nach Build) | CuttOffl ruft `ffmpeg`/`ffprobe` als eigenständige Prozesse auf -- kein Linking. Die LGPL-Anforderungen sind damit erfüllt. |

---

## Whisper-Modelle (optional, werden auf Nutzer-Wunsch heruntergeladen)

Die Modell-Gewichte werden nicht mit CuttOffl ausgeliefert, sondern
auf Wunsch aus dem jeweiligen HuggingFace-Repo in den Cache des
Nutzers gezogen.

| Modell-Familie         | Quelle                                                          | Lizenz |
|------------------------|-----------------------------------------------------------------|--------|
| OpenAI Whisper (.pt)   | `~/.cache/whisper/` (direkt von OpenAI)                         | MIT    |
| mlx-community/whisper-*-mlx | https://huggingface.co/mlx-community                       | MIT (auf OpenAI-Gewichten basierend) |
| Systran/faster-whisper-*    | https://huggingface.co/Systran                             | MIT    |

Alle Whisper-Gewichte sind MIT-lizenziert. Kommerzielle Nutzung ist
seitens der Modell-Lizenz erlaubt -- die Nicht-kommerziell-Klausel
bezieht sich ausschließlich auf CuttOffl selbst.

---

## Was CuttOffl nicht tut

- **Kein Telemetrie-Ping**, keine Nutzungsstatistik, kein Analytics.
- **Keine Cloud-Uploads**: Videos, Transkripte, Projekte bleiben auf
  dem eigenen Rechner.
- **Keine CDN-Aufrufe im Frontend**: Fonts, Icons und Assets sind
  lokal eingebunden (`@fontsource/*`, `@fortawesome/fontawesome-free`).
- **Keine Analytics-Badges** in der App -- die Shields-Badges in der
  README werden nur auf GitHub gerendert, nicht in der laufenden App.

## Offline-Betrieb

Nach dem einmaligen Einrichten läuft die komplette App ohne Internet:

- Frontend kommuniziert ausschließlich mit dem lokalen Backend
  (`/api`, `/ws`).
- Backend ruft selbst keine externen Dienste auf (außer beim Modell-
  Download in den Einstellungen, der bewusst vom Nutzer angestoßen
  wird).
- Transkriptions-Läufe setzen automatisch `HF_HUB_OFFLINE=1`, sobald
  ein lokales Modell zur aktiven Engine gefunden wurde -- damit gibt
  es auch keine "ist das Modell noch aktuell?"-HEAD-Checks an
  huggingface.co.
