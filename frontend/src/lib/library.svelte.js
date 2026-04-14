// Library-State: aktueller Ordner, Ansichts-Variante, Sortierung
// (alles persistent im localStorage), plus Pfad-Hilfen für die Basis-
// Navigation.

import { persisted, persist } from './persist.svelte.js';

// Erlaubte Werte für Ansicht und Sortierung
export const VIEWS = ['grid', 'list', 'compact'];
export const SORT_KEYS = ['name', 'date', 'size', 'duration'];
export const SORT_DIRS = ['asc', 'desc'];

function coerce(val, allowed, fallback) {
  return allowed.includes(val) ? val : fallback;
}

// Filterwerte
export const STATUS_VALUES = ['all', 'ready', 'processing', 'failed'];
// Aufloesung: Buckets -- 'all' oder '<=480' (SD), '<=720' (HD), '<=1080' (FHD),
// '<=2160' (4K UHD), '>2160' (mehr als 4K). Buckets by height.
export const RES_BUCKETS = ['all', 'sd', 'hd', 'fhd', 'uhd', 'above'];

export const library = $state({
  currentFolder: persisted('library.currentFolder', ''),
  view:    coerce(persisted('library.view', 'grid'), VIEWS, 'grid'),
  sortBy:  coerce(persisted('library.sortBy', 'date'), SORT_KEYS, 'date'),
  sortDir: coerce(persisted('library.sortDir', 'desc'), SORT_DIRS, 'desc'),
  // Filter + Suche -- NICHT persistent (Suche hält sich nicht über Reload)
  filterStatus: 'all',
  filterFormat: 'all',  // 'all' oder Codec-Name ('h264', 'hevc', ...)
  filterRes:    'all',
  filterTag:    '',     // '' = alle, sonst exakter Tag-Name
  search: '',
  // Mehrfachauswahl (nicht persistent) -- Array von file_ids
  selection: [],
});

export function setCurrentFolder(path) {
  const p = normalizePath(path);
  const changed = p !== library.currentFolder;
  library.currentFolder = p;
  persist('library.currentFolder', p);
  // URL mitziehen, wenn wir gerade in der Bibliothek sind. Dynamischer
  // Import, um eine zirkulaere Abhaengigkeit mit nav.svelte.js zu
  // vermeiden (library wird aus nav beim popstate ebenfalls gesetzt).
  if (changed) {
    import('./nav.svelte.js').then((m) => m.syncLibraryFolderUrl?.(p));
  }
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

export function setFilter(key, value) {
  if (key === 'status' && STATUS_VALUES.includes(value)) library.filterStatus = value;
  if (key === 'format') library.filterFormat = value || 'all';
  if (key === 'res'    && RES_BUCKETS.includes(value))    library.filterRes = value;
  if (key === 'tag')    library.filterTag = value || '';
}

export function setSearch(q) {
  library.search = q ?? '';
}

export function resetFilters() {
  library.filterStatus = 'all';
  library.filterFormat = 'all';
  library.filterRes    = 'all';
  library.filterTag    = '';
  library.search       = '';
}

// ---- Auswahl-Helpers -------------------------------------------------------
export function isSelected(id) {
  return library.selection.includes(id);
}

export function toggleSelect(id) {
  if (!id) return;
  const i = library.selection.indexOf(id);
  if (i >= 0) library.selection = library.selection.filter((x) => x !== id);
  else library.selection = [...library.selection, id];
}

export function selectAll(ids) {
  const next = new Set(library.selection);
  for (const id of ids) if (id) next.add(id);
  library.selection = [...next];
}

export function selectOnly(ids) {
  library.selection = [...new Set(ids.filter(Boolean))];
}

export function clearSelection() {
  library.selection = [];
}

function matchesStatus(f, status) {
  if (status === 'all') return true;
  const s = f.proxy_status || 'none';
  if (status === 'ready')      return s === 'ready';
  if (status === 'processing') return s === 'running' || s === 'pending' || s === 'none';
  if (status === 'failed')     return s === 'failed';
  return true;
}

function matchesRes(f, bucket) {
  if (bucket === 'all') return true;
  const h = f.height || 0;
  if (bucket === 'sd')    return h > 0 && h <= 576;
  if (bucket === 'hd')    return h > 576 && h <= 720;
  if (bucket === 'fhd')   return h > 720 && h <= 1080;
  if (bucket === 'uhd')   return h > 1080 && h <= 2160;
  if (bucket === 'above') return h > 2160;
  return true;
}

export function filterFiles(files) {
  const status = library.filterStatus;
  const format = library.filterFormat;
  const res    = library.filterRes;
  const tag    = library.filterTag;
  const q      = (library.search || '').trim().toLowerCase();
  return files.filter((f) => {
    if (!matchesStatus(f, status)) return false;
    if (format !== 'all' && (f.video_codec || '').toLowerCase() !== format) return false;
    if (!matchesRes(f, res)) return false;
    if (tag) {
      const tags = Array.isArray(f.tags) ? f.tags : [];
      const tagKey = tag.toLocaleLowerCase('de');
      if (!tags.some((t) => (t || '').toLocaleLowerCase('de') === tagKey)) return false;
    }
    if (q && !(f.original_name || '').toLowerCase().includes(q)) return false;
    return true;
  });
}

/** Extrahiert alle Codec-Namen aus den Dateien für das Format-Dropdown. */
export function codecOptions(files) {
  const set = new Set();
  for (const f of files) if (f.video_codec) set.add(f.video_codec);
  return [...set].sort((a, b) => a.localeCompare(b));
}

/** Extrahiert alle Tags für das Tag-Filter-Dropdown. */
export function tagOptions(files) {
  const set = new Set();
  for (const f of files) {
    for (const t of (f.tags || [])) if (t) set.add(t);
  }
  return [...set].sort((a, b) => a.localeCompare(b, 'de'));
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
