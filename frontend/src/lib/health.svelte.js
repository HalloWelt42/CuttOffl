// Zentraler Gesundheits-State: alle Dienste, die ausfallen koennen und
// im Footer als LED sichtbar sein sollen. Jeder Eintrag hat einen
// stabilen "key" (wird fuer die LED-Anzeige benutzt), einen Label-
// Namen und einen "level" aus {unknown, ok, warn, err}.
//
// Backend wird per HTTP-Ping abgefragt, Transkription per /status,
// WebSocket-Status liest direkt aus wsState. Alle Abfragen laufen
// defensiv: bei Netzfehler kein Crash, LED wird rot.

import { api } from './api.js';
import { wsState } from './ws.svelte.js';

const INTERVAL_MS = 15_000;     // 15 s reicht fuer Footer-Statusanzeige

export const health = $state({
  backend: {
    key: 'backend',
    label: 'Backend',
    level: 'unknown',
    detail: 'pruefe...',
  },
  ws: {
    key: 'ws',
    label: 'Live-Events',
    level: 'unknown',
    detail: 'pruefe...',
  },
  transcription: {
    key: 'transcription',
    label: 'Transkription',
    level: 'unknown',
    detail: 'pruefe...',
  },
});

let timer = null;
let started = false;

async function pollBackend() {
  try {
    const p = await api.ping();
    health.backend.level = 'ok';
    health.backend.detail = `${p.app} v${p.version} auf ${p.host}:${p.port}`
      + (p.ffmpeg_version ? ` · ffmpeg ok` : '')
      + (p.hw_encoder ? ` · HW ${p.hw_encoder}` : '');
  } catch (e) {
    health.backend.level = 'err';
    health.backend.detail = 'Nicht erreichbar -- laeuft das Backend?';
  }
}

async function pollTranscription() {
  try {
    const s = await api.transcriptionStatus();
    if (s.available) {
      health.transcription.level = 'ok';
      health.transcription.detail =
        `${s.active_engine} / ${s.active_model}`;
      return;
    }
    // Nicht verfuegbar -- unterscheide "gar nichts installiert"
    // (err/rot) von "installiert aber kein Modell ausgewaehlt" (warn)
    const anyInstalled = (s.engines || []).some((e) => e.installed);
    if (anyInstalled) {
      health.transcription.level = 'warn';
      health.transcription.detail =
        (s.notes && s.notes[0]) || 'Kein lokales Whisper-Modell ausgewaehlt';
    } else {
      health.transcription.level = 'err';
      health.transcription.detail =
        'Whisper ist nicht installiert -- siehe Einstellungen';
    }
  } catch {
    // Endpunkt nicht erreichbar: wenn Backend down, zeigt das ja schon
    // die Backend-LED; wir markieren hier "unknown".
    health.transcription.level = 'unknown';
    health.transcription.detail = 'Status unbekannt';
  }
}

function refreshWs() {
  if (wsState.connected) {
    health.ws.level = 'ok';
    health.ws.detail = 'Job-Progress live';
  } else {
    health.ws.level = 'warn';
    health.ws.detail = 'Verbindung wird hergestellt';
  }
}

async function pollAll() {
  refreshWs();
  await Promise.allSettled([pollBackend(), pollTranscription()]);
}

export function startHealth() {
  if (started) return;
  started = true;
  void pollAll();
  timer = setInterval(pollAll, INTERVAL_MS);
  // WebSocket-State aendert sich unabhaengig vom Timer -- kurzer Trigger
  // auf jeden Frame ist overkill, wir machen ein schlankes Reactive-Poll
  // per zweitem Intervall.
  setInterval(refreshWs, 1500);
}

export function refreshHealth() {
  return pollAll();
}
