// State-Container fuer die beiden verschiebbaren Hilfe-Panels:
// - Info-Panel (kontextabhaengig, Tastatur- und Bedien-Hinweise)
// - Ueber-Panel (Projekt-Info, Lizenz, Haftung, Danke-Link)
//
// Position und Groesse werden im localStorage persistiert. Beim ersten
// Oeffnen wird eine sinnvolle Startposition rechts unten im Viewport
// berechnet, damit nichts neben dem sichtbaren Bereich landet.

import { persisted, persist } from './persist.svelte.js';

function initialGeometry(key, fallback) {
  const saved = persisted(key, null);
  if (saved && typeof saved === 'object') return saved;
  return { ...fallback };
}

export const infoPanel = $state({
  open: persisted('panel.info.open', false),
  ...initialGeometry('panel.info', {
    x: 120, y: 120, width: 480, height: 540,
  }),
});

export const aboutPanel = $state({
  open: persisted('panel.about.open', false),
  ...initialGeometry('panel.about', {
    x: 200, y: 160, width: 560, height: 600,
  }),
});

function savePanel(key, p) {
  persist(key, { x: p.x, y: p.y, width: p.width, height: p.height });
}

function saveOpen(key, value) { persist(key, !!value); }

export function openInfo()   { infoPanel.open = true;  saveOpen('panel.info.open', true); }
export function closeInfo()  { infoPanel.open = false; saveOpen('panel.info.open', false); }
export function toggleInfo() {
  infoPanel.open = !infoPanel.open;
  saveOpen('panel.info.open', infoPanel.open);
}

export function openAbout()   { aboutPanel.open = true;  saveOpen('panel.about.open', true); }
export function closeAbout()  { aboutPanel.open = false; saveOpen('panel.about.open', false); }
export function toggleAbout() {
  aboutPanel.open = !aboutPanel.open;
  saveOpen('panel.about.open', aboutPanel.open);
}

export function persistInfoGeometry()  { savePanel('panel.info',  infoPanel); }
export function persistAboutGeometry() { savePanel('panel.about', aboutPanel); }

/** Clampt die Panel-Position in den sichtbaren Viewport, damit nichts
 *  nach Resize "verloren" geht. */
export function clampToViewport(p) {
  const pad = 8;
  const maxX = Math.max(pad, window.innerWidth  - p.width  - pad);
  const maxY = Math.max(pad, window.innerHeight - p.height - pad);
  p.x = Math.max(pad, Math.min(p.x, maxX));
  p.y = Math.max(pad, Math.min(p.y, maxY));
}
