// Tour-Definitionen für CuttOffl.
//
// Die eigentlichen Texte (title, body, hint, audio_text) stehen in
// der JSON-Datei tour-texts.json -- so kann das Python-Script für die
// Audio-Synthese dieselbe Quelle nutzen und wir vermeiden Doppelpflege.
//
// Hier drin bleibt nur das Strukturelle: View-Navigation,
// CSS-Selector fürs Spotlight, optionale before-Callbacks (z. B.
// Dialog öffnen), demo_ms. Beim Zusammensetzen werden die Texte
// aus der JSON an den jeweiligen Schritt gemerged.

import { openInfo } from './panels.svelte.js';
import { editor } from './editor.svelte.js';
import { openInEditor } from './nav.svelte.js';
import { api } from './api.js';
import texts from './tour-texts.json';

// Skelett je Tour: alles Strukturelle, aber keine Texte.
const SKELETONS = {
  'erste-schritte': {
    title: 'Erste Schritte',
    icon: 'fa-flag-checkered',
    color: '#58a6ff',
    description:
      'Upload, Bibliothek, Editor, erster Schnitt und Rendern -- '
      + 'die komplette Kette einmal durch.',
    duration: '2-3 Min',
    runnable: true,
    steps: [
      { view: 'dashboard', demo_ms: 6500 },
      { view: 'dashboard', selector: '[data-tour="nav-library"]',
        hint: 'Klick auf "Bibliothek" im Menü.' },
      { view: 'library', selector: '[data-tour="lib-search"]' },
      { view: 'library', selector: '[data-tour="lib-view-switch"]' },
      { view: 'library', selector: '[data-tour="lib-file-open"]',
        hint: 'Der Button ist erst aktiv, wenn die Proxy-Vorschau fertig ist.' },
      { view: 'editor', selector: '[data-tour="editor-timeline"]',
        before: ensureEditorHasVideo },
      { view: 'editor', selector: '[data-tour="editor-addclip"]',
        hint: 'Frame-genau schneiden: Keyframe-Magnet aus -- dann reencode, kostet Rechenzeit, ist dafür exakt.' },
      { view: 'editor', selector: '[data-tour="editor-render"]',
        hint: 'Keine Sorge -- der Dialog öffnet sich nur, er startet nichts.' },
      { view: 'exports' },
      { view: 'dashboard',
        hint: 'Klick auf "Beenden" oder Escape, um die Tour zu schließen.',
        demo_ms: 6500 },
    ],
  },

  'bibliothek': {
    title: 'Bibliothek meistern',
    icon: 'fa-folder-tree',
    color: '#10B981',
    description:
      'Ordner, Tags, Suche, Bulk-Aktionen, Hover-Scrub. '
      + 'Der komfortable Umgang mit vielen Videos.',
    duration: '1-2 Min',
    runnable: true,
    steps: [
      { view: 'library' },
      { view: 'library', selector: '[data-tour="lib-folders"]' },
      { view: 'library', selector: '[data-tour="lib-search"]' },
      { view: 'library', selector: '[data-tour="lib-filters"]' },
      { view: 'library', selector: '[data-tour="lib-bulk-bar"]' },
      { demo_ms: 6000 },
    ],
  },

  'renderer': {
    title: 'Renderer-Tiefenblick',
    icon: 'fa-sliders',
    color: '#FF7043',
    description:
      'Profile, Zielgröße, Live-Abschätzung, Prozess-Transparenz. '
      + 'Alles, was der Export-Dialog kann.',
    duration: '2 Min',
    runnable: true,
    steps: [
      { view: 'editor', selector: '[data-tour="editor-render"]',
        before: ensureEditorHasVideo,
        hint: 'Der Dialog wird gleich für dich geöffnet -- nichts wird gerendert.' },
      { view: 'editor',
        before: () => clickIfExists('[data-tour="editor-render"]'),
        selector: '.modal [data-tour="render-tab-profile"]' },
      { view: 'editor', selector: '.modal [data-tour="render-tab-video"]' },
      { view: 'editor', selector: '.modal [data-tour="render-tab-audio"]' },
      { view: 'editor', selector: '.modal [data-tour="render-estimate"]' },
      { view: 'editor', demo_ms: 7000 },
    ],
  },

  'tastenkuerzel': {
    title: 'Tastenkürzel',
    icon: 'fa-keyboard',
    color: '#C8A2FF',
    description:
      'Der schnellste Weg durch den Editor ist die Tastatur. '
      + 'Die wichtigsten Kürzel im Überblick.',
    duration: '1 Min',
    runnable: true,
    steps: [
      { view: 'editor',
        before: async () => { await ensureEditorHasVideo(); openInfo(); } },
      { view: 'editor', selector: '[data-panel="info"]' },
      { view: 'editor', selector: '[data-panel="info"]' },
      { view: 'editor', demo_ms: 5500 },
    ],
  },

  'ki-untertitel': {
    title: 'KI-Untertitel',
    icon: 'fa-closed-captioning',
    color: '#E4405F',
    description:
      'Wie Whisper lokal läuft, wie du Modelle wählst und was '
      + 'du mit dem Transkript machen kannst. (Nur Demo -- echte '
      + 'Transkription braucht Modelle und ein Video.)',
    duration: '1-2 Min',
    runnable: false,
    steps: [
      { view: 'settings', demo_ms: 6500 },
      { view: 'settings', demo_ms: 7000 },
      { view: 'settings', demo_ms: 7500 },
      { view: 'settings', demo_ms: 7000 },
      { view: 'editor', demo_ms: 7000 },
      { demo_ms: 7000 },
    ],
  },
};

// Merge: Skelett + Texte aus JSON. Pro Step die Felder title, body,
// hint (optional) und audio_text aus der JSON übernehmen, plus
// den berechneten Pfad zur MP3-Datei.
export const TOURS = Object.entries(SKELETONS).map(([id, tour]) => {
  const textSteps = texts[id] || [];
  const steps = tour.steps.map((s, i) => {
    const t = textSteps[i] || {};
    return {
      ...s,
      title: t.title ?? '(ohne Titel)',
      body: t.body ?? '',
      hint: s.hint ?? t.hint ?? null,
      audio_text: t.audio_text ?? t.body ?? '',
      // Relativer Pfad auf die einmalig synthetisierte MP3. Wird vom
      // TourOverlay als <audio src> gesetzt. Fehlt die Datei, läuft
      // die Tour einfach stumm weiter.
      audio_src: `/tour-audio/${id}-${i}.mp3`,
    };
  });
  return { id, ...tour, steps };
});

// --- Helfer für before-Callbacks --------------------------------------

function clickIfExists(selector) {
  const el = document.querySelector(selector);
  if (el && !el.disabled) el.click();
}

// Damit die Editor-Schritte der Tour etwas zu zeigen haben: wenn noch
// kein Video im Editor offen ist, wählen wir eins aus der Bibliothek
// aus. Bevorzugt das geschützte Demo-Video (protected=1), sonst die
// erste beste Datei mit fertiger Proxy-Vorschau. Ohne Proxy bleibt
// der Schritt ohne Spotlight -- kein Drama.
async function ensureEditorHasVideo() {
  if (editor.fileId) return;
  let files = [];
  try {
    files = await api.listFiles();
  } catch { return; }
  if (!files || files.length === 0) return;
  const demo = files.find((f) => f.protected && f.has_proxy);
  const fallback = files.find((f) => f.has_proxy);
  const target = demo || fallback;
  if (!target) return;
  openInEditor(target.id);
  // kurz warten, damit der Editor das Projekt und den Player lädt
  await new Promise((r) => setTimeout(r, 1500));
}
