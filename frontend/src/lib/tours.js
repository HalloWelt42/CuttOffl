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

import { openInfo, closeInfo } from './panels.svelte.js';
import {
  editor, addClipFromRange, startRangePreview, stopPreview, seek,
} from './editor.svelte.js';
import { openInEditor, setSettingsTab } from './nav.svelte.js';
import { api } from './api.js';
import { library, toggleSelect, clearSelection } from './library.svelte.js';
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
        // Während wir die Timeline erklären, läuft im Hintergrund ein
        // kleiner Range-Preview -- so sieht der Nutzer den Abspielkopf
        // sichtbar mitlaufen. Am Ende des Schrittes stoppen wir
        // wieder, damit die nächsten Schritte ruhig weiterlaufen.
        before: async () => {
          await ensureEditorHasVideo();
          // kurz warten, damit das Video geladen ist
          for (let i = 0; i < 30 && !(editor.duration > 0); i++) {
            await new Promise((r) => setTimeout(r, 150));
          }
          const dur = editor.duration || 0;
          if (dur > DEMO_CLIP_END) {
            // Range-Preview: spielt von DEMO_CLIP_START bis Ende der
            // Tour-Box-Anzeige, dann stoppt es automatisch.
            seek(DEMO_CLIP_START);
            startRangePreview(DEMO_CLIP_START, DEMO_CLIP_START + 20);
          }
        },
        after: () => { stopPreview(); },
      },
      { view: 'editor', selector: '[data-tour="editor-addclip"]',
        // Damit die Demonstration echt ist: Tour legt einen 5 s
        // langen Clip an, der sichtbar in der Timeline landet.
        // Nach diesem Schritt bleibt er noch, damit der folgende
        // Render-Button-Schritt klickbar ist; ganz am Ende der Tour
        // räumt resetDemoTimeline ihn wieder weg.
        before: ensureEditorHasClip,
        hint: 'Frame-genau schneiden: Keyframe-Magnet aus -- dann reencode, kostet Rechenzeit, ist dafür exakt.' },
      { view: 'editor', selector: '[data-tour="editor-render"]',
        // Clip ist durch den vorigen Schritt schon da -- der
        // Render-Button ist aktiv, der User sieht, wo der Export los geht.
        hint: 'Keine Sorge -- der Dialog öffnet sich nur, er startet nichts.' },
      { view: 'exports',
        // Spotlight auf die Liste der fertigen Videos (erster Eintrag
        // reicht), fallback auf den Panel-Header wenn leer.
        selector: ['.list li', '.body'] },
      { view: 'dashboard',
        hint: 'Klick auf "Beenden" oder Escape, um die Tour zu schließen.',
        demo_ms: 6500,
        // Demo-Clip aus der Timeline räumen, damit der Editor wieder
        // leer ist, wenn der User später selbst reinschaut.
        after: () => resetDemoTimeline(),
      },
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
      { view: 'library',
        // Bevorzugt auf einen sichtbaren Unterordner zeigen (Demo-
        // Ordner liegt immer in der Basis). Fällt das weg, nehmen wir
        // die Breadcrumb-Leiste. Array-Selektor = erste Option
        // gewinnt, nicht DOM-Reihenfolge.
        selector: ['.card.folder', '[data-tour="lib-folders"]'] },
      { view: 'library', selector: '[data-tour="lib-search"]' },
      { view: 'library',
        // Filter-Chips erscheinen nur, wenn tatsächlich ein Filter
        // aktiv ist. Für die Demo setzen wir deshalb einen sichtbaren
        // Beispielfilter und nehmen ihn am Ende wieder raus.
        before: () => { library.filterStatus = 'ready'; },
        after: () => { library.filterStatus = 'all'; },
        selector: '[data-tour="lib-filters"]' },
      { view: 'library',
        // Bulk-Bar erscheint nur bei Selection > 0. Wir selektieren die
        // erste Datei aus dem Backend programmatisch, damit der Tour-
        // Spotlight ein echtes Ziel hat; am Ende des Schrittes räumen
        // wir das wieder weg.
        before: async () => {
          try {
            const files = await api.listFiles();
            const first = (files || [])[0];
            if (first) toggleSelect(first.id);
          } catch {}
        },
        after: () => { clearSelection(); },
        selector: '[data-tour="lib-bulk-bar"]' },
      { view: 'library',
        // Hover-Scrub-Tipp -- Spotlight auf die erste Kachel, damit
        // der User sieht, wo er die Maus überfahren darf.
        selector: '[data-tour-first-tile] .thumb-btn, [data-tour-first-tile]',
        demo_ms: 6000 },
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
        // Damit der Render-Button klickbar ist, muss mindestens ein
        // Clip in der Timeline liegen. Für die Tour legen wir einen
        // kleinen Demo-Clip an (wird beim after wieder entfernt).
        before: ensureEditorHasClip,
        hint: 'Der Dialog wird gleich für dich geöffnet -- nichts wird gerendert.' },
      { view: 'editor',
        before: () => clickIfExists('[data-tour="editor-render"]'),
        selector: '.modal [data-tour="render-tab-profile"]' },
      { view: 'editor',
        before: () => clickIfExists('.modal [data-tour="render-tab-video"]'),
        selector: '.modal [data-tour="render-tab-video"]' },
      { view: 'editor',
        before: () => clickIfExists('.modal [data-tour="render-tab-audio"]'),
        selector: '.modal [data-tour="render-tab-audio"]' },
      { view: 'editor', selector: '.modal [data-tour="render-estimate"]' },
      { view: 'editor',
        selector: '.modal [data-tour="render-start-btn"]',
        demo_ms: 7000,
        // Am Ende der Tour den Dialog wieder schließen und die
        // Timeline auf den Ursprungsstand bringen.
        after: () => {
          closeExportDialog();
          resetDemoTimeline();
        },
      },
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
        // Das Info-Panel erst zu, dann frisch öffnen -- damit das
        // Panel beim Re-Start der Tour (z. B. im Komplett-Rundgang)
        // sichtbar "neu aufpoppt" und nicht von einer vorigen Tour
        // noch als Schatten im Hintergrund klebt.
        before: async () => {
          await ensureEditorHasVideo();
          closeInfo();
          await new Promise((r) => setTimeout(r, 120));
          openInfo();
        } },
      { view: 'editor', selector: '[data-panel="info"]' },
      { view: 'editor', selector: '[data-panel="info"]' },
      { view: 'editor', demo_ms: 5500,
        // Letzter Schritt: Info-Panel wieder zu, sonst bleibt es
        // nach dem Tour-Ende offen über der Help-Seite.
        after: () => closeInfo(),
      },
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
      { view: 'settings',
        before: () => setSettingsTab('transkription'),
        demo_ms: 6500 },
      { view: 'settings',
        before: () => setSettingsTab('transkription'),
        selector: '[data-tour="tx-engines"]',
        demo_ms: 7000 },
      { view: 'settings',
        before: () => setSettingsTab('transkription'),
        selector: '[data-tour="tx-models"]',
        demo_ms: 7500 },
      { view: 'settings',
        before: () => setSettingsTab('transkription'),
        selector: '[data-tour="tx-download"]',
        demo_ms: 7000 },
      { view: 'editor',
        before: ensureEditorHasVideo,
        selector: '[data-tour="editor-transcribe-btn"]',
        demo_ms: 7000 },
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

// Schließt den Export-Dialog (sofern offen) -- wird nach der Renderer-
// Tour aufgerufen, damit der Dialog nicht unbeabsichtigt offen bleibt.
// Wir klicken den X-Button im modalen Dialog, statt Render-Button
// oder einen echten Cancel -- so wird nichts gerendert und nichts
// gespeichert.
function closeExportDialog() {
  const x = document.querySelector('.modal .x');
  if (x) x.click();
}

// Demo-Clip aus der Timeline wieder entfernen, wenn er per
// ensureEditorHasClip angelegt wurde. Wir merken uns nicht extra,
// ob "wir" den Clip erzeugt haben -- stattdessen: wenn die Timeline
// aus exakt einem Clip mit src_start = 0 und src_end <= 3 besteht,
// war das unserer.
function resetDemoTimeline() {
  if (!editor.edl) return;
  const tl = editor.edl.timeline ?? [];
  // Einzelner Demo-Clip passend zu DEMO_CLIP_START/END -> weg.
  // Toleranz beim Vergleich, weil Keyframe-Snap die Grenzen leicht
  // verschiebt.
  if (tl.length === 1) {
    const c = tl[0];
    const plausibleDemo = (
      Math.abs(c.src_start - DEMO_CLIP_START) < 5
      && Math.abs(c.src_end - DEMO_CLIP_END) < 5
    );
    if (plausibleDemo) {
      editor.edl.timeline = [];
      editor.selectedClipId = null;
    }
  }
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

// Für die Renderer-Tour: Render-Button ist disabled solange die
// Timeline leer ist. Wir legen einen 5-Sekunden-Demo-Clip an einer
// visuell ergiebigen Stelle an (bei Big Buck Bunny verlässt der
// Hase um ~20s die Höhle -- das zeigt mehr als die schwarzen
// Anfangs-Sekunden). Non-destruktiv: EDL wird manipuliert, das
// Original-Video bleibt. Läuft nur, wenn die Timeline leer ist.
const DEMO_CLIP_START = 20;
const DEMO_CLIP_END = 25;
async function ensureEditorHasClip() {
  await ensureEditorHasVideo();
  // auf den Editor-Load warten, damit edl schon existiert
  for (let i = 0; i < 20 && !editor.edl; i++) {
    await new Promise((r) => setTimeout(r, 150));
  }
  if (!editor.edl) return;
  if ((editor.edl.timeline?.length ?? 0) > 0) return;
  // Wenn das Video kürzer als DEMO_CLIP_END ist, fallen wir auf einen
  // sicheren Bereich zurück (sollte nur bei exotischen Test-Videos
  // passieren).
  const dur = editor.duration || 0;
  const end = dur > 0 && dur < DEMO_CLIP_END ? Math.max(0.5, dur - 0.5) : DEMO_CLIP_END;
  const start = Math.max(0, Math.min(DEMO_CLIP_START, Math.max(0, end - 5)));
  addClipFromRange(start, end);
  await new Promise((r) => setTimeout(r, 300));
}
