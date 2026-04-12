// Library-State: aktueller Ordner, Ansichts-Variante, Sortierung
// (alles persistent im localStorage), plus Pfad-Hilfen fuer die Basis-
// Navigation.

import { persisted, persist } from './persist.svelte.js';

// Erlaubte Werte fuer Ansicht und Sortierung
export const VIEWS = ['grid', 'list', 'compact'];
export const SORT_KEYS = ['name', 'date', 'size', 'duration'];
export const SORT_DIRS = ['asc', 'desc'];

function coerce(val, allowed, fallback) {
  return allowed.includes(val) ? val : fallback;
}

export const library = $state({
  currentFolder: persisted('library.currentFolder', ''),
  view:    coerce(persisted('library.view', 'grid'), VIEWS, 'grid'),
  sortBy:  coerce(persisted('library.sortBy', 'date'), SORT_KEYS, 'date'),
  sortDir: coerce(persisted('library.sortDir', 'desc'), SORT_DIRS, 'desc'),
});

export function setCurrentFolder(path) {
  const p = normalizePath(path);
  library.currentFolder = p;
  persist('library.currentFolder', p);
}

export function setView(v) {
  if (!VIEWS.includes(v)) return;
  library.view = v;
  persist('library.view', v);
}

export function setSort(by, dir) {
  if (by && SORT_KEYS.includes(by)) {
    library.sortBy = by;
    persist('library.sortBy', by);
  }
  if (dir && SORT_DIRS.includes(dir)) {
    library.sortDir = dir;
    persist('library.sortDir', dir);
  }
}

export function toggleSortDir() {
  setSort(null, library.sortDir === 'asc' ? 'desc' : 'asc');
}

export function sortFiles(files) {
  const by  = library.sortBy;
  const dir = library.sortDir === 'asc' ? 1 : -1;
  const copy = [...files];
  copy.sort((a, b) => {
    let av, bv;
    switch (by) {
      case 'name':
        return dir * (a.original_name || '').localeCompare(b.original_name || '', 'de', { numeric: true });
      case 'size':
        av = a.size_bytes || 0; bv = b.size_bytes || 0; break;
      case 'duration':
        av = a.duration_s ?? 0; bv = b.duration_s ?? 0; break;
      case 'date':
      default:
        av = a.created_at || ''; bv = b.created_at || '';
        return dir * av.localeCompare(bv);
    }
    return dir * (av - bv);
  });
  return copy;
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
