// Library-State: aktueller Ordner (persistent), kleine Hilfen fuer die Pfad-
// Arbeit auf der Frontend-Seite.

import { persisted, persist } from './persist.svelte.js';

export const library = $state({
  currentFolder: persisted('library.currentFolder', ''),
});

export function setCurrentFolder(path) {
  const p = normalizePath(path);
  library.currentFolder = p;
  persist('library.currentFolder', p);
}

export function normalizePath(p) {
  if (!p) return '';
  let s = String(p).trim();
  if (s === '/' || s === '') return '';
  s = s.replace(/^\/+|\/+$/g, '');
  return s.split('/').filter((x) => x && x !== '.' && x !== '..').join('/');
}

export function parentOf(p) {
  const n = normalizePath(p);
  if (!n) return '';
  const i = n.lastIndexOf('/');
  return i < 0 ? '' : n.slice(0, i);
}

export function breadcrumbs(path) {
  // [{label, path}] inklusive Basis (Wurzel-Ebene)
  const n = normalizePath(path);
  const parts = n ? n.split('/') : [];
  const out = [{ label: 'Basis', path: '' }];
  let acc = '';
  for (const seg of parts) {
    acc = acc ? `${acc}/${seg}` : seg;
    out.push({ label: seg, path: acc });
  }
  return out;
}
