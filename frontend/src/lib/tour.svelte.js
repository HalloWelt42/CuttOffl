// Tour-System -- interaktive Rundgänge durch die App.
//
// Zwei Modi pro Tour:
//   - guided : der User klickt selbst; die Tour wartet in jedem
//              Schritt auf eine Interaktion und führt mit
//              Spotlight + Hinweisbox.
//   - demo   : "Zeig es mir" -- die Tour läuft automatisch weiter,
//              ohne dass wirklich geklickt werden muss. Jeder Schritt
//              bleibt eine bestimmte Anzeigezeit stehen, dann geht
//              es zum nächsten.
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

let demoTimer = null;

export async function startTour(id, mode = 'guided') {
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
  await runStep();
  if (mode === 'demo') scheduleDemoAdvance();
}

export function stopTour() {
  if (demoTimer) { clearTimeout(demoTimer); demoTimer = null; }
  tour.activeId = null;
  tour.stepIndex = 0;
  tour.target = null;
  tour.targetRect = null;
  tour.running = false;
}

export async function nextStep() {
  const t = currentTour();
  if (!t) return;
  if (tour.stepIndex >= t.steps.length - 1) {
    markCompleted(t.id);
    stopTour();
    return;
  }
  tour.stepIndex++;
  await runStep();
  if (tour.mode === 'demo') scheduleDemoAdvance();
}

export async function prevStep() {
  const t = currentTour();
  if (!t) return;
  if (tour.stepIndex <= 0) return;
  tour.stepIndex--;
  await runStep();
  if (tour.mode === 'demo') scheduleDemoAdvance();
}

export function toggleMode() {
  // Zwischen 'guided' und 'demo' schalten, laufende Tour behalten
  tour.mode = tour.mode === 'demo' ? 'guided' : 'demo';
  if (demoTimer) { clearTimeout(demoTimer); demoTimer = null; }
  if (tour.mode === 'demo') scheduleDemoAdvance();
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

function scheduleDemoAdvance() {
  if (demoTimer) clearTimeout(demoTimer);
  const step = currentStep();
  if (!step) return;
  const ms = step.demo_ms ?? 3500;
  demoTimer = setTimeout(() => { void nextStep(); }, ms);
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
