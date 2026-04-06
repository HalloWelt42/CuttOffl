// Theme (dunkel/hell) -- persistent im localStorage.
// Schriftgroesse bleibt dem Browser ueberlassen (Cmd/Ctrl + / - /  0).

import { persisted, persist } from './persist.svelte.js';

export const theme = $state({
  mode: persisted('app.theme', 'dark'),   // 'dark' | 'light'
});

export function applyTheme() {
  document.documentElement.setAttribute('data-theme', theme.mode);
  persist('app.theme', theme.mode);
}

export function toggleTheme() {
  theme.mode = theme.mode === 'dark' ? 'light' : 'dark';
  applyTheme();
}
