// Theme + Font-Scale -- persistent in localStorage.

import { persisted, persist } from './persist.svelte.js';

export const theme = $state({
  mode: persisted('app.theme', 'dark'),           // 'dark' | 'light'
  scale: persisted('app.fontScale', 'normal'),    // 'small' | 'normal' | 'large'
});

const SCALE_MAP = { small: 0.875, normal: 1, large: 1.125 };

export function applyTheme() {
  document.documentElement.setAttribute('data-theme', theme.mode);
  document.documentElement.style.setProperty(
    '--font-scale',
    String(SCALE_MAP[theme.scale] ?? 1),
  );
  persist('app.theme', theme.mode);
  persist('app.fontScale', theme.scale);
}

export function toggleTheme() {
  theme.mode = theme.mode === 'dark' ? 'light' : 'dark';
  applyTheme();
}

export function setScale(s) {
  theme.scale = s;
  applyTheme();
}
