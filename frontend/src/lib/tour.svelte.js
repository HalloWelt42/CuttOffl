// Tour-System -- interaktive Rundgänge durch die App.
//
// Zwei Modi pro Tour:
//   - guided : der User klickt selbst; die Tour wartet in jedem
//              Schritt auf eine Interaktion und führt mit
//              Spotlight + Hinweisbox.
//   - demo   : "Zeig es mir" -- die Tour läuft automatisch weiter.
//              Der Advance zum nächsten Schritt wird extern vom
//              TourOverlay ausgelöst: entweder nach Ende der
//              vorgelesenen Audio (+ Puffer zum Nachlesen) oder,
//              wenn kein Audio verfügbar ist, nach einer festen
//              Zeit (step.demo_ms). Während des Wartens läuft ein
//              Countdown, den der User per Play/Pause anhalten kann.
//
// Wichtig: Keine destruktiven Aktionen. Die Tour navigiert (go),
// öffnet Dialoge/Panels und hebt Elemente hervor, aber sie legt
// nichts an, löscht nichts und startet keine Renders.

import { persisted, persist } from './persist.svelte.js';
import { go } from './nav.svelte.js';
import { closeInfo, closeAbout } from './panels.svelte.js';
import { markTourStart, markTourEnd } from './tourRecorder.js';

export const tour = $state({
  activeId: null,        // id der laufenden Tour oder null
  mode: 'guided',        // 'guided' | 'demo'
  stepIndex: 0,          // aktueller Schritt (0-based)
  target: null,          // DOM-Element des aktuellen Schrittes
  targetRect: null,      // DOMRect für Spotlight-Position
  running: false,        // true wenn Tour gerade läuft
  // Pause-/Countdown-Steuerung (nur im Demo-Modus relevant):
  paused: false,
  advanceAt: 0,          // epoch-ms, wann der nächste Schritt kommt (0 = kein Timer)
  advanceTotal: 0,       // ursprüngliche Gesamtdauer dieses Countdowns
  // Komplett-Durchlauf: Queue weiterer Touren, die nach dem Ende der
  // aktuellen Tour automatisch gestartet werden (für das "Alles-in-
  // einem"-Präsentations-Programm).
  queue: [],
});

// Persistiert: welche Touren hat der User schon einmal begonnen?
// Ermöglicht es dem Dashboard, die Tour erstmalig vorzuschlagen.
const COMPLETED_KEY = 'tour.completed';
export const tourCompleted = $state({
  set: new Set(persisted(COMPLETED_KEY, [])),
});

// Einmalig beim allerersten App-Start: dürfen wir die Einsteiger-Tour
// automatisch anbieten? Danach nie wieder ungefragt.
const OFFERED_KEY = 'tour.firstRunOffered';
export function shouldOfferFirstTour() {
  return !persisted(OFFERED_KEY, false);
}
export function markFirstTourOffered() {
  persist(OFFERED_KEY, true);
}

// Audio-Begleitung: vorgelesene Erklärungen während der Tour. Default
// an, der User kann pro App-Installation abschalten.
const AUDIO_KEY = 'tour.audioOn';
export const tourAudio = $state({
  enabled: persisted(AUDIO_KEY, true),
});
export function toggleTourAudio() {
  tourAudio.enabled = !tourAudio.enabled;
  persist(AUDIO_KEY, tourAudio.enabled);
}

// Puffer-Zeiten (millisekunden), einstellbar falls nötig:
//   Nachlese nach Audio-Ende -> nextStep
//   Fallback-Zeit pro Step ohne Audio (überschreibbar per step.demo_ms)
export const DEMO_AUDIO_BUFFER_MS = 2500;
export const DEMO_FALLBACK_MS = 4500;

// --- Tour-Registry -----------------------------------------------------

let TOURS = [];

export function registerTours(list) {
  TOURS = list;
}

export function listTours() {
  return TOURS;
}

export function getTour(id) {
  return TOURS.find((t) => t.id === id) ?? null;
}

// --- Ablaufsteuerung ---------------------------------------------------

let advanceTimer = null;
// Für pause/resume: wenn wir einen laufenden Timer stoppen, merken wir
// uns die verbleibende Zeit, um beim Resume mit der Rest-Zeit fort-
// zufahren.
let advanceRemainingMs = 0;

export async function startTour(id, mode = 'guided', queue = []) {
  const t = getTour(id);
  if (!t) {
    console.warn(`[tour] Tour unbekannt: ${id}`);
    return;
  }
  // vorherige Tour sauber beenden (ohne Zwischen-Nav auf Hilfe-Seite)
  stopTour({ navBack: false });
  // Panels beim Start immer schließen -- das schwebende Info-Fenster
  // aus einer früheren Sitzung liegt sonst über den Tour-Zielen und
  // blockiert die Sicht. Einzelne Tour-Schritte öffnen das Panel
  // explizit wieder (siehe Tastenkürzel-Tour).
  try { closeInfo(); closeAbout(); } catch {}
  tour.activeId = id;
  tour.mode = mode;
  tour.stepIndex = 0;
  tour.running = true;
  tour.paused = false;
  tour.queue = Array.isArray(queue) ? [...queue] : [];
  await runStep();
  // Im Demo-Modus löst der TourOverlay den Advance aus, sobald die
  // Audio-Dauer bekannt ist. Wenn kein Audio verfügbar ist, setzt er
  // scheduleAdvance(DEMO_FALLBACK_MS).
}

/** Startet den kompletten Präsentations-Durchlauf: erste Tour läuft,
 *  danach automatisch die nächsten aus der Queue. Pro Schritt der
 *  Warteschlange werden alle Schritte der jeweiligen Tour gespielt. */
export async function startAllTours(mode = 'demo') {
  if (!TOURS.length) return;
  // Tour-Recorder: markiert t_ms=0 und leert eine bestehende Aufnahme.
  // No-op ausserhalb des Aufnahme-Modus (?tour_record=1).
  await markTourStart();
  const ids = TOURS.map((t) => t.id);
  const first = ids[0];
  const rest = ids.slice(1);
  await startTour(first, mode, rest);
}

export function stopTour(opts = {}) {
  // Am Ende einer Tour (oder beim manuellen Abbruch) landet der User
  // wieder auf der Hilfe-Seite -- sonst bliebe er z. B. im Editor
  // mit offenem Info-Panel stehen, ohne klaren Kontext. Das Nav wird
  // nur ausgelöst, wenn vorher tatsächlich eine Tour lief; interne
  // Reset-Aufrufe (z. B. aus startTour) setzen navBack=false.
  const wasRunning = tour.running;
  const navBack = opts.navBack !== false;
  // Schritt-after sofern vorhanden ausführen (Cleanup). Im Queue-Fall
  // wird hier der aktuelle Schritt aufgeräumt, bevor die nächste Tour
  // startet.
  if (wasRunning) {
    const step = currentStep();
    if (step && typeof step.after === 'function') {
      try { step.after(); } catch {}
    }
  }
  clearAdvance();
  tour.activeId = null;
  tour.stepIndex = 0;
  tour.target = null;
  tour.targetRect = null;
  tour.running = false;
  tour.paused = false;
  tour.queue = [];
  if (wasRunning) {
    // Alle von der Tour eventuell geöffneten Panels sicher zumachen.
    // Ohne das hängt z. B. das Info-Panel aus der Tastenkürzel-Tour
    // weiter über der Hilfe-Seite und überdeckt die nächste Tour.
    try { closeInfo(); closeAbout(); } catch {}
  }
  if (wasRunning && navBack) {
    try { go('help'); } catch {}
  }
}

export async function nextStep() {
  const t = currentTour();
  if (!t) return;
  clearAdvance();
  // after-Callback des aktuell verlassenen Schrittes aufrufen, damit
  // Schritt-lokale Aufräumarbeit greift (z. B. Selektion zurücksetzen,
  // Demo-Filter entfernen, Panels schließen).
  await runAfter();
  if (tour.stepIndex >= t.steps.length - 1) {
    markCompleted(t.id);
    // Gibt es noch weitere Touren in der Queue? -> nahtlos weiter,
    // OHNE zwischendurch zur Hilfe-Seite zu navigieren.
    if (tour.queue.length > 0) {
      const nextId = tour.queue.shift();
      const rest = [...tour.queue];
      const keepMode = tour.mode;
      stopTour({ navBack: false });
      await startTour(nextId, keepMode, rest);
      return;
    }
    // Letzte Tour fertig -> stopTour navigiert standardmäßig auf die
    // Hilfe-Seite zurück, damit der User sieht, was er als nächstes tun
    // könnte.
    // Tour-Recorder: letzter Timestamp fuer die Aufnahme. No-op
    // ausserhalb des Aufnahme-Modus.
    await markTourEnd();
    stopTour();
    return;
  }
  tour.stepIndex++;
  await runStep();
}

export async function prevStep() {
  const t = currentTour();
  if (!t) return;
  clearAdvance();
  await runAfter();
  if (tour.stepIndex <= 0) return;
  tour.stepIndex--;
  await runStep();
}

async function runAfter() {
  const step = currentStep();
  if (step && typeof step.after === 'function') {
    try { await step.after(); } catch (e) { console.warn('[tour] after:', e); }
  }
}

export function toggleMode() {
  // Zwischen 'guided' und 'demo' schalten, laufende Tour behalten
  clearAdvance();
  tour.mode = tour.mode === 'demo' ? 'guided' : 'demo';
  tour.paused = false;
}

export function pauseTour() {
  if (!tour.running || tour.paused) return;
  tour.paused = true;
  // Restzeit des laufenden Countdowns merken
  if (tour.advanceAt > 0) {
    advanceRemainingMs = Math.max(0, tour.advanceAt - Date.now());
    if (advanceTimer) clearTimeout(advanceTimer);
    advanceTimer = null;
    tour.advanceAt = 0;
  } else {
    advanceRemainingMs = 0;
  }
}

export function resumeTour() {
  if (!tour.running || !tour.paused) return;
  tour.paused = false;
  if (advanceRemainingMs > 0) {
    scheduleAdvance(advanceRemainingMs, tour.advanceTotal || advanceRemainingMs);
    advanceRemainingMs = 0;
  }
  // Audio muss der Overlay selbst wieder anwerfen (spielt eigene Logik)
}

/** Timer für den Auto-Advance setzen. Wird vom TourOverlay aufgerufen:
 *  - Bei Audio-Ende  -> scheduleAdvance(DEMO_AUDIO_BUFFER_MS)
 *  - Bei fehlendem Audio -> scheduleAdvance(step.demo_ms ?? DEMO_FALLBACK_MS)
 *  Ist die Tour pausiert oder nicht im Demo-Modus, passiert nichts. */
export function scheduleAdvance(delayMs, totalMs = null) {
  clearAdvance();
  if (!tour.running || tour.mode !== 'demo' || tour.paused) return;
  const total = totalMs ?? delayMs;
  tour.advanceAt = Date.now() + delayMs;
  tour.advanceTotal = total;
  advanceTimer = setTimeout(() => {
    advanceTimer = null;
    tour.advanceAt = 0;
    tour.advanceTotal = 0;
    if (!tour.paused) void nextStep();
  }, delayMs);
}

export function clearAdvance() {
  if (advanceTimer) { clearTimeout(advanceTimer); advanceTimer = null; }
  tour.advanceAt = 0;
  tour.advanceTotal = 0;
  advanceRemainingMs = 0;
}

function currentTour() {
  return tour.activeId ? getTour(tour.activeId) : null;
}

export function currentStep() {
  const t = currentTour();
  if (!t) return null;
  return t.steps[tour.stepIndex] ?? null;
}

function markCompleted(id) {
  tourCompleted.set.add(id);
  persist(COMPLETED_KEY, Array.from(tourCompleted.set));
}

// --- Schritt ausführen -------------------------------------------------

async function runStep() {
  const step = currentStep();
  if (!step) return;

  // Vor-Navigation: manche Schritte leben in einer anderen View
  if (step.view) {
    go(step.view);
    // kurz warten bis Svelte gerendert hat
    await nextFrame();
    await nextFrame();
  }

  // Vor-Aktion (z. B. Panel/Dialog öffnen), damit das Ziel-Element
  // überhaupt existiert. Nie destruktiv. Danach genug Frames warten,
  // damit Svelte-Reactive-Updates (z. B. Filter-Chips, Bulk-Bar)
  // im DOM angekommen sind, bevor wir das Ziel-Rect messen.
  if (typeof step.before === 'function') {
    try { await step.before(); } catch (e) { console.warn('[tour] before:', e); }
    await nextFrame();
    await nextFrame();
    await wait(50);
  }

  // Ziel-Element finden und Bounding-Rect messen. Selektor kann ein
  // String sein (querySelector), ein Array (erster Treffer gewinnt)
  // oder eine Funktion, die ein Element oder null zurückgibt. Die
  // Array-Variante hilft bei Prioritäten: "wenn das Spezifische
  // (z. B. eine Ordner-Kachel) da ist, dort hervorheben; sonst
  // fallback auf die Breadcrumb."
  let el = null;
  if (typeof step.selector === 'function') {
    try { el = step.selector(); } catch {}
  } else if (Array.isArray(step.selector)) {
    for (const s of step.selector) {
      const found = s ? document.querySelector(s) : null;
      if (found) { el = found; break; }
    }
  } else if (step.selector) {
    el = document.querySelector(step.selector);
  }
  tour.target = el;
  tour.targetRect = el ? el.getBoundingClientRect() : null;

  // Ziel immer ins Zentrum scrollen, damit rund um den Spotlight
  // Platz für die Hinweisbox bleibt. isCentered prüft grob, ob sich
  // Zentrieren überhaupt lohnt -- bei kurzen Seiten würde ein harter
  // Scroll unnötig ruckeln.
  if (el && !isReasonablyCentered(el)) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    await wait(400);
    tour.targetRect = el.getBoundingClientRect();
  }
}

function isReasonablyCentered(el) {
  // "gut platziert" heißt: das Element liegt im mittleren Drittel des
  // Viewports (vertikal). Am oberen/unteren Rand scrollen wir neu.
  const r = el.getBoundingClientRect();
  const vh = window.innerHeight;
  const third = vh / 3;
  return r.top >= third * 0.5 && r.bottom <= vh - third * 0.5;
}

function nextFrame() {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isInViewport(el) {
  const r = el.getBoundingClientRect();
  return r.top >= 0 && r.left >= 0
      && r.bottom <= window.innerHeight
      && r.right <= window.innerWidth;
}

// Wenn ein targetRect existiert, aktualisieren wir es periodisch --
// z. B. bei Resize oder wenn das Zielelement sich durch Scroll bewegt.
if (typeof window !== 'undefined') {
  window.addEventListener('resize', () => {
    if (tour.target) tour.targetRect = tour.target.getBoundingClientRect();
  });
  window.addEventListener('scroll', () => {
    if (tour.target) tour.targetRect = tour.target.getBoundingClientRect();
  }, { capture: true, passive: true });
}
