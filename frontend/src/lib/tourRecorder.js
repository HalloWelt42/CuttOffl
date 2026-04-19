// Tour-Recorder (Frontend-Minimal-Hook).
//
// Architektur: die Intelligenz liegt im Backend. Sobald der Recorder
// aktiv ist, loggt die Backend-Middleware alle relevanten HTTP-Calls
// (Tour-Audios, TTS, Proxy-Video) automatisch mit Zeitstempel.
//
// Das Frontend muss nur:
//   - beim Tour-Start  POST /api/_recorder/start  rufen
//   - beim Tour-Ende   POST /api/_recorder/stop   rufen
//
// Keine Hooks mehr in speak.svelte.js oder Player.svelte. Damit
// kann der Recorder auch keine Nebenwirkungen auf die Tour-Logik
// haben -- die Aufnahme laeuft ausschliesslich serverseitig.
//
// Aktiviert per URL-Param ?tour_record=1. Ohne den Param sind alle
// Funktionen no-op.

const ENABLED = (() => {
  try {
    return new URLSearchParams(window.location.search).get('tour_record') === '1';
  } catch {
    return false;
  }
})();

async function post(path) {
  if (!ENABLED) return;
  try {
    await fetch(path, { method: 'POST' });
  } catch (e) {
    console.warn('[tour-recorder] request failed:', e);
  }
}

export function recorderActive() { return ENABLED; }

/** Startet die Recorder-Session. Wird beim "Kompletter Rundgang"
 *  ausgeloest. Das Backend leert die vorige Session automatisch. */
export async function markTourStart() {
  if (!ENABLED) return;
  await post('/api/_recorder/start');
  console.info('[tour-recorder] Aufnahme begonnen');
}

/** Beendet die Recorder-Session. */
export async function markTourEnd() {
  if (!ENABLED) return;
  await post('/api/_recorder/stop');
  console.info('[tour-recorder] Aufnahme beendet');
}
