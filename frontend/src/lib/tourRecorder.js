// Tour-Recorder (einmaliger Helfer, kein Produkt-Feature).
//
// Aktiviert sich nur, wenn die URL ?tour_record=1 enthaelt. Sonst
// sind alle Funktionen no-ops -- das Programm merkt nichts davon.
//
// Nutzungs-Ablauf:
//   1. Browser mit http://127.0.0.1:10037/?tour_record=1 oeffnen
//   2. macOS-Bildschirmaufnahme starten
//   3. "Kompletter Rundgang" starten
//   4. Nach Ende laeuft tools/build_tour_audio.py ueber die gespeicherten
//      Events und baut daraus die Audio-Spur

const ENABLED = (() => {
  try {
    return new URLSearchParams(window.location.search).get('tour_record') === '1';
  } catch {
    return false;
  }
})();

let t0 = null;  // performance.now() beim tour_start

function now() { return performance.now(); }

async function post(body) {
  if (!ENABLED) return;
  try {
    await fetch('/api/_recorder/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (e) {
    // Recorder darf die Tour nicht stoeren -- Fehler werden stumm
    // geschluckt, im Tool sieht man dann ob alles drin ist.
    console.warn('[tour-recorder] event post failed:', e);
  }
}

export function recorderActive() { return ENABLED; }

/** Markiert t_ms=0 und leert die Aufnahme-Datei. Wird beim Start der
 *  "Kompletter Rundgang"-Tour gerufen. */
export async function markTourStart() {
  if (!ENABLED) return;
  t0 = now();
  await post({ t_ms: 0, kind: 'tour_start' });
  console.info('[tour-recorder] tour_start (Aufnahme begonnen)');
}

/** Audio-Start loggen. text = der urspruengliche (cleaned) Text.
 *  Das Tool findet ueber cache_path_for(text) die passende MP3. */
export async function markAudioStart(text) {
  if (!ENABLED) return;
  if (t0 == null) t0 = now();    // Fallback falls tour_start vergessen
  const t_ms = now() - t0;
  await post({ t_ms, kind: 'audio_start', text });
}

/** Optional: Tour-Ende loggen -- der User kann daraus ableiten, wie
 *  lang seine Bildschirmaufnahme insgesamt gehen muss. */
export async function markTourEnd() {
  if (!ENABLED) return;
  if (t0 == null) return;
  const t_ms = now() - t0;
  await post({ t_ms, kind: 'tour_end' });
  console.info('[tour-recorder] tour_end');
}
