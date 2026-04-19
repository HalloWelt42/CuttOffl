// Vitest-Konfiguration ohne Svelte-Plugin (Kollision mit aktuellem
// vite/vitest an configureServer). Tests importieren deshalb nur
// reine JS-Module aus src/lib -- keine .svelte-Komponenten und
// keine Files, die Runes ($state, $derived, $effect) direkt nutzen.

import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.js'],
    globals: false,
    environmentOptions: {
      // jsdom startet sonst mit about:blank -- history.replaceState
      // auf andere Origins (z. B. localhost) wirft dann SecurityError.
      // Wir setzen die Test-Origin auf die echte Frontend-URL.
      jsdom: { url: 'http://127.0.0.1:10037/' },
    },
  },
});
