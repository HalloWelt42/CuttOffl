<script>
  import { onMount } from 'svelte';
  import Sidebar from './components/Sidebar.svelte';
  import Resizer from './components/Resizer.svelte';
  import JobsBar from './components/JobsBar.svelte';
  import ToastHost from './components/ToastHost.svelte';
  import ErrorBoundary from './components/ErrorBoundary.svelte';
  import Dashboard from './views/Dashboard.svelte';
  import Library from './views/Library.svelte';
  import Editor from './views/Editor.svelte';
  import Exports from './views/Exports.svelte';
  import Settings from './views/Settings.svelte';
  import Help from './views/Help.svelte';
  import ThanksOverlay from './components/ThanksOverlay.svelte';
  import DialogHost from './components/DialogHost.svelte';
  import FolderPickerOverlay from './components/FolderPickerOverlay.svelte';
  import InfoPanel from './components/InfoPanel.svelte';
  import AboutPanel from './components/AboutPanel.svelte';
  import TourOverlay from './components/TourOverlay.svelte';
  import { nav } from './lib/nav.svelte.js';
  import { applyTheme } from './lib/theme.svelte.js';
  import { persisted, persist } from './lib/persist.svelte.js';
  import { api } from './lib/api.js';
  import { version as frontendVersion } from '../package.json';
  import { REPO_URL } from './lib/meta.js';

  let sidebarCollapsed = $state(persisted('app.sidebarCollapsed', false));
  let sidebarWidth = $state(persisted('app.sidebarWidth', 200));

  $effect(() => persist('app.sidebarCollapsed', sidebarCollapsed));
  $effect(() => persist('app.sidebarWidth', sidebarWidth));

  let backendVersion = $state('...');

  onMount(async () => {
    applyTheme();
    try {
      const p = await api.ping();
      backendVersion = p.version;
    } catch {}
  });
</script>

<ErrorBoundary>
  <div class="app">
    <div class="main">
      <div
        class="sidebar-wrap"
        style:width={sidebarCollapsed ? '56px' : `${sidebarWidth}px`}
      >
        <Sidebar
          bind:collapsed={sidebarCollapsed}
          {frontendVersion}
          {backendVersion}
          {REPO_URL}
        />
      </div>

      {#if !sidebarCollapsed}
        <Resizer bind:value={sidebarWidth} min={160} max={360} side="left" />
      {/if}

      <main class="content">
        {#if nav.view === 'dashboard'}<Dashboard />
        {:else if nav.view === 'library'}<Library />
        {:else if nav.view === 'editor'}<Editor />
        {:else if nav.view === 'exports'}<Exports />
        {:else if nav.view === 'settings'}<Settings />
        {:else if nav.view === 'help'}<Help />
        {/if}
      </main>
    </div>

    <JobsBar />
    <ToastHost />
    <ThanksOverlay />
    <DialogHost />
    <FolderPickerOverlay />
    <InfoPanel />
    <AboutPanel />
    <TourOverlay />
  </div>
</ErrorBoundary>

<style>
  .app { display: flex; flex-direction: column; height: 100vh; }
  .main { flex: 1; display: flex; min-height: 0; }
  .sidebar-wrap {
    flex: 0 0 auto;
    min-width: 56px;
    transition: width 120ms ease;
  }
  .content {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
</style>
