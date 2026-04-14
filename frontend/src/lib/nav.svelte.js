// View-Navigation mit echten Pfaden statt Hash-URLs (History API).
//
// URL-Schema (alles relativ zur Basis-URL der App):
//   /                               Dashboard
//   /dashboard                      Dashboard
//   /library                        Bibliothek, Basis-Ordner
//   /library/Urlaub/2026            Bibliothek, Ordnerpfad (beliebig tief)
//   /editor                         Editor (leer)
//   /editor/file/<id>               Editor mit Quelldatei
//   /editor/project/<id>            Editor mit gespeichertem Projekt
//   /exports                        Fertige Videos
//   /settings                       Einstellungen
//
// Back/Forward-Buttons des Browsers funktionieren ueber popstate.
// Fuer die Ordner-Tiefe in der Bibliothek wird der folder_path aus
// dem library-Store direkt an die URL gehaengt.

import { persisted, persist } from './persist.svelte.js';
import { library } from './library.svelte.js';

export const VIEWS = ['dashboard', 'library', 'editor', 'exports', 'settings'];

// --- URL <-> Route -------------------------------------------------------

/**
 * Zerlegt einen Pfad wie "/library/Urlaub/2026" in eine Route.
 * Unbekannte View -> Dashboard als Fallback.
 *
 * Returns: {
 *   view: 'library'|'editor'|...,
 *   folder: string,           // nur fuer library, sonst ''
 *   fileId: string|null,      // nur fuer editor
 *   projectId: string|null,   // nur fuer editor
 * }
 */
export function parsePath(pathname) {
  const clean = (pathname || '/').replace(/\/+$/, '') || '/';
  if (clean === '/' || clean === '') {
    return { view: 'dashboard', folder: '', fileId: null, projectId: null };
  }
  // Erstes Segment = View
  const parts = clean.split('/').filter(Boolean);
  const head = parts[0];
  if (!VIEWS.includes(head)) {
    // Legacy-Hash-URL -- beim ersten Laden einmal migrieren:
    // wenn es einen Hash gibt und der eine bekannte View ist, uebernehmen.
    const h = (location.hash || '').replace(/^#/, '');
    if (VIEWS.includes(h)) {
      return { view: h, folder: '', fileId: null, projectId: null };
    }
    return { view: 'dashboard', folder: '', fileId: null, projectId: null };
  }

  const rest = parts.slice(1);
  if (head === 'library') {
    // alle restlichen Segmente bilden den Ordnerpfad
    const folder = rest.map(decodeURIComponent).join('/');
    return { view: 'library', folder, fileId: null, projectId: null };
  }
  if (head === 'editor') {
    if (rest[0] === 'file' && rest[1]) {
      return { view: 'editor', folder: '', fileId: rest[1], projectId: null };
    }
    if (rest[0] === 'project' && rest[1]) {
      return { view: 'editor', folder: '', fileId: null, projectId: rest[1] };
    }
    return { view: 'editor', folder: '', fileId: null, projectId: null };
  }
  return { view: head, folder: '', fileId: null, projectId: null };
}

/** Baut aus einer Route den URL-Pfad. */
export function routeToPath(route) {
  const v = VIEWS.includes(route?.view) ? route.view : 'dashboard';
  if (v === 'dashboard') return '/';
  if (v === 'library') {
    const seg = (route.folder || '')
      .split('/').filter(Boolean).map(encodeURIComponent).join('/');
    return seg ? `/library/${seg}` : '/library';
  }
  if (v === 'editor') {
    if (route.fileId)    return `/editor/file/${encodeURIComponent(route.fileId)}`;
    if (route.projectId) return `/editor/project/${encodeURIComponent(route.projectId)}`;
    return '/editor';
  }
  return `/${v}`;
}

// --- State ---------------------------------------------------------------

const initialRoute = parsePath(location.pathname);

export const nav = $state({
  view: initialRoute.view,
  activeFileId: initialRoute.fileId,
  activeProjectId: initialRoute.projectId,
  // folder ist der "Einstiegs-Ordner" aus der URL beim Seitenaufruf.
  // Die eigentliche Wahrheit fuer den aktuellen Ordner steht im
  // library-Store; dieser sync ueber ein effect in Library.svelte.
  initialFolder: initialRoute.folder,
});

// Persistiere beim ersten Aufruf die Default-View (fuer Fallbacks).
persist('app.view', nav.view);

// Initial einmal den sauberen Pfad in der History ablegen, damit
// /library/Foo auch nach Reload gleich bleibt.
(() => {
  const clean = routeToPath(initialRoute);
  if (location.pathname !== clean) {
    history.replaceState({}, '', clean + location.search);
  }
  // Library-Ordner aus der URL sticht den persistierten Wert aus dem
  // localStorage, wenn wir direkt auf /library/Foo kommen.
  if (initialRoute.view === 'library'
      && library.currentFolder !== initialRoute.folder) {
    library.currentFolder = initialRoute.folder;
    persist('library.currentFolder', initialRoute.folder);
  }
})();

// --- Navigation ---------------------------------------------------------

/**
 * Wechselt die View (und optional Ordner/Datei/Projekt).
 * Schreibt eine neue History-Position.
 */
export function go(view, opts = {}) {
  if (!VIEWS.includes(view)) return;
  nav.view = view;
  persist('app.view', view);
  // Editor-State zuruecksetzen, wenn wir aus dem Editor rauswechseln
  if (view !== 'editor') {
    nav.activeFileId = null;
    nav.activeProjectId = null;
  }
  // Fuer library ohne expliziten Ordner-Opt nehmen wir den aktuell im
  // Store eingestellten Ordner, damit URL und Anzeige konsistent bleiben.
  const folderFromStore = view === 'library' ? (library.currentFolder || '') : '';
  const route = {
    view,
    folder:    opts.folder    ?? folderFromStore,
    fileId:    opts.fileId    ?? null,
    projectId: opts.projectId ?? null,
  };
  const path = routeToPath(route);
  if (location.pathname !== path) {
    history.pushState({}, '', path + location.search);
  }
}

/** Aktualisiert nur den Ordnerpfad in der URL (ohne History-Eintrag), z. B.
 *  wenn der User in der Bibliothek durch Ordner navigiert. */
export function syncLibraryFolderUrl(folderPath) {
  if (nav.view !== 'library') return;
  const path = routeToPath({ view: 'library', folder: folderPath });
  if (location.pathname !== path) {
    history.pushState({}, '', path + location.search);
  }
}

export function openInEditor(fileId) {
  nav.activeFileId = fileId;
  nav.activeProjectId = null;
  go('editor', { fileId });
}

export function openProjectInEditor(projectId) {
  nav.activeProjectId = projectId;
  nav.activeFileId = null;
  go('editor', { projectId });
}

// Back/Forward des Browsers wieder in den State spiegeln
window.addEventListener('popstate', () => {
  const r = parsePath(location.pathname);
  nav.view = r.view;
  nav.activeFileId = r.fileId;
  nav.activeProjectId = r.projectId;
  nav.initialFolder = r.folder;
  persist('app.view', r.view);
  // Library-Ordner direkt setzen (ohne setCurrentFolder, sonst
  // wuerde der die URL wieder schreiben und popstate-Kette erzeugen)
  if (r.view === 'library' && library.currentFolder !== r.folder) {
    library.currentFolder = r.folder;
    persist('library.currentFolder', r.folder);
  }
});

// Legacy: falls jemand noch mit einem #hash reinkommt, einmal rendern
// mit dem Hash-Ziel und gleich einen sauberen Pfad schreiben.
(() => {
  const h = (location.hash || '').replace(/^#/, '');
  if (VIEWS.includes(h) && location.pathname === '/') {
    history.replaceState({}, '', `/${h}`);
    nav.view = h;
  }
})();
