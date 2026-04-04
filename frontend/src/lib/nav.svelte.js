// Leichtgewichtige View-Navigation, kein Router. Hash-synchron fuer Back/Forward.

import { persisted, persist } from './persist.svelte.js';

export const VIEWS = ['dashboard', 'library', 'editor', 'settings', 'about'];

const initial = () => {
  const hash = location.hash.replace(/^#/, '');
  if (VIEWS.includes(hash)) return hash;
  return persisted('app.view', 'dashboard');
};

export const nav = $state({ view: initial(), activeFileId: null });

export function go(view) {
  if (!VIEWS.includes(view)) return;
  nav.view = view;
  persist('app.view', view);
  if (location.hash !== `#${view}`) history.pushState(null, '', `#${view}`);
}

export function openInEditor(fileId) {
  nav.activeFileId = fileId;
  go('editor');
}

window.addEventListener('hashchange', () => {
  const h = location.hash.replace(/^#/, '');
  if (VIEWS.includes(h) && h !== nav.view) nav.view = h;
});
