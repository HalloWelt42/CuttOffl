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
  // vorherige Tour sauber beenden
  stopTour();
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
  const ids = TOURS.map((t) => t.id);
  const first = ids[0];
  const rest = ids.slice(1);
  await startTour(first, mode, rest);
}

export function stopTour() {
  clearAdvance();
  tour.activeId = null;
  tour.stepIndex = 0;
  tour.target = null;
  tour.targetRect = null;
  tour.running = false;
  tour.paused = false;
  tour.queue = [];
}

export async function nextStep() {
  const t = currentTour();
  if (!t) return;
  clearAdvance();
  if (tour.stepIndex >= t.steps.length - 1) {
    markCompleted(t.id);
    // Gibt es noch weitere Touren in der Queue? -> nahtlos weiter.
    if (tour.queue.length > 0) {
      const nextId = tour.queue.shift();
      const rest = [...tour.queue];
      const keepMode = tour.mode;
      stopTour();
      await startTour(nextId, keepMode, rest);
      return;
    }
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
  if (tour.stepIndex <= 0) return;
  tour.stepIndex--;
  await runStep();
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
  // überhaupt existiert. Nie destruktiv.
  if (typeof step.before === 'function') {
    try { await step.before(); } catch (e) { console.warn('[tour] before:', e); }
    await nextFrame();
  }

  // Ziel-Element finden und Bounding-Rect messen
  const el = step.selector ? document.querySelector(step.selector) : null;
  tour.target = el;
  tour.targetRect = el ? el.getBoundingClientRect() : null;

  // Ins Blickfeld scrollen, falls nötig
  if (el && !isInViewport(el)) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    await wait(350);
    tour.targetRect = el.getBoundingClientRect();
  }
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
