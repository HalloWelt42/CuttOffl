// Separate Vitest-Konfiguration. Ohne das Svelte-Plugin -- die
// aktuellen Versionen von @sveltejs/vite-plugin-svelte und vitest
// kollidieren beim Startup. Unsere Unit-Tests decken reine
// JS-Module ab (kein Svelte-Component-Rendering), deshalb brauchen
// wir das Plugin hier nicht.

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
