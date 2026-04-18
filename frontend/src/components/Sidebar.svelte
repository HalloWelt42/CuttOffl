<script>
  import { nav, go } from '../lib/nav.svelte.js';
  import { toggleTheme, theme } from '../lib/theme.svelte.js';
  import { openThanks } from '../lib/ui.svelte.js';
  import {
    infoPanel, aboutPanel, toggleInfo, toggleAbout,
    infoLabelFor, hasSpecificInfo,
  } from '../lib/panels.svelte.js';

  // Kontext-abhaengiges Info-Label: steht je nach aktiver View fuer
  // "Tastenkuerzel" (Editor), "Bibliothek-Tipps", etc. Wenn es fuer den
  // View keine spezifische Hilfe gibt, bleibt der Eintrag grau als
  // generisches "Info".
  const infoLabel = $derived(infoLabelFor(nav.view));
  const infoIsSpecific = $derived(hasSpecificInfo(nav.view));

  let {
    collapsed = $bindable(),
    frontendVersion = '',
    backendVersion = '',
    REPO_URL = '',
  } = $props();

  // Einträge für reguläre Views (werden über go() aufgerufen)
  const GROUPS = [
    { label: null, items: [
      { id: 'dashboard', icon: 'fa-gauge-high',  label: 'Dashboard' },
      { id: 'library',   icon: 'fa-folder-tree', label: 'Bibliothek' },
    ]},
    { label: 'Arbeitsplatz', items: [
      { id: 'editor',    icon: 'fa-scissors',     label: 'Editor' },
      { id: 'exports',   icon: 'fa-box-archive',  label: 'Fertige Videos' },
    ]},
    { label: 'System', items: [
      { id: 'settings',  icon: 'fa-gear',         label: 'Einstellungen' },
    ]},
  ];

  // Panel-Einträge: keine View-Navigation, sondern Toggle eines
  // verschiebbaren Fensters. Der Info-Eintrag wird im Template direkt
  // gerendert, weil sein Label kontextabhaengig ist (siehe infoLabel).
</script>

<aside class="sidebar" class:collapsed>
  <div class="brand">
    <img class="logo" src="/favicon.svg" alt="CuttOffl" />
    {#if !collapsed}
      <div class="brand-text">
        <span class="name">CuttOffl</span>
        <span class="soft tag">Video Studio</span>
      </div>
    {/if}
  </div>

  <nav>
    {#each GROUPS as g (g.label ?? 'root')}
      {#if g.label && !collapsed}
        <div class="group-label soft">{g.label}</div>
      {/if}
      {#each g.items as it (it.id)}
        <button
          class="item"
          class:active={nav.view === it.id}
          onclick={() => go(it.id)}
          title={collapsed ? it.label : ''}
        >
          <i class="fa-solid {it.icon}"></i>
          {#if !collapsed}<span>{it.label}</span>{/if}
        </button>
      {/each}
    {/each}

    <!-- Hilfe-Panels: akzentfarbige Einträge, die ein verschiebbares
         Fenster öffnen statt eine View zu wechseln. -->
    {#if !collapsed}
      <div class="group-label soft">Hilfe</div>
    {/if}
    <!-- Info: Label wechselt je nach aktiver View. Wenn es fuer den
         Kontext keine spezifische Hilfe gibt, bleibt der Eintrag grau
         und heisst generisch "Info". -->
    <button
      class="item item-panel"
      class:active={infoPanel.open}
      class:item-panel-muted={!infoIsSpecific}
      onclick={toggleInfo}
      title={collapsed ? infoLabel : ''}
    >
      <i class="fa-solid fa-circle-info"></i>
      {#if !collapsed}<span>{infoLabel}</span>{/if}
    </button>

    <button
      class="item item-panel"
      class:active={aboutPanel.open}
      onclick={toggleAbout}
      title={collapsed ? 'Über' : ''}
    >
      <i class="fa-solid fa-circle-question"></i>
      {#if !collapsed}<span>Über</span>{/if}
    </button>
  </nav>

  <div class="foot">
    <button class="item" onclick={toggleTheme}
            title={theme.mode === 'dark'
              ? 'Zum hellen Erscheinungsbild wechseln'
              : 'Zum dunklen Erscheinungsbild wechseln'}>
      <i class="fa-solid {theme.mode === 'dark' ? 'fa-moon' : 'fa-sun'}"></i>
      {#if !collapsed}<span>{theme.mode === 'dark' ? 'Dunkel' : 'Hell'}</span>{/if}
    </button>

    <button class="item" onclick={openThanks}
            title="Unterstützungs-Möglichkeiten anzeigen (Ko-fi und Kryptowährungen)">
      <i class="fa-solid fa-heart danke"></i>
      {#if !collapsed}<span>Danke</span>{/if}
    </button>

    {#if !collapsed}
      <div class="info mono">
        <div class="info-row">
          <span class="k">App</span>
          <a href={REPO_URL} target="_blank" rel="noopener"
             class="repo-link"
             title="CuttOffl-Repository auf GitHub öffnen">
            CuttOffl <i class="fa-brands fa-github"></i>
          </a>
        </div>
        <div class="info-row">
          <span class="k">Frontend</span>
          <span>v{frontendVersion}</span>
        </div>
        <div class="info-row">
          <span class="k">Backend</span>
          <span>v{backendVersion || '...'}</span>
        </div>
      </div>
    {/if}

    <button class="item collapse-toggle" onclick={() => (collapsed = !collapsed)}
            title={collapsed ? 'Seitenleiste ausklappen' : 'Seitenleiste einklappen'}>
      <i class="fa-solid {collapsed ? 'fa-angles-right' : 'fa-angles-left'}"></i>
      {#if !collapsed}<span>Einklappen</span>{/if}
    </button>
  </div>
</aside>

<style>
  .sidebar {
    display: flex;
    flex-direction: column;
    background: var(--bg-panel);
    border-right: 1px solid var(--border);
    height: 100%;
    min-width: 56px;
    overflow: hidden;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 12px;
    border-bottom: 1px solid var(--border);
  }
  .logo {
    width: 36px;
    height: 36px;
    flex: 0 0 36px;
    display: block;
    /* transparenter Hintergrund: die Kartoffel bleibt freigestellt */
  }
  .brand-text { display: flex; flex-direction: column; line-height: 1.1; gap: 3px; }
  .name { font-weight: 700; font-size: 21px; letter-spacing: 0.4px; }
  .tag  { font-size: 12px; color: var(--fg-muted); letter-spacing: 0.3px; }

  nav {
    flex: 1;
    padding: 10px 8px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow-y: auto;
  }
  .group-label {
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--fg-faint);
    padding: 10px 8px 4px;
  }
  .item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    background: transparent;
    color: var(--fg-muted);
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font: inherit;
    text-align: left;
    transition: background 120ms, color 120ms;
  }
  .item:hover { background: var(--bg-elev); color: var(--fg-primary); }
  .item.active { background: var(--bg-elev); color: var(--accent); }
  .item i { width: 18px; text-align: center; font-size: 14px; }

  /* Hilfe-Panel-Eintraege: Icon dauerhaft in Akzent-Blau, damit sie
     klar als "Info-Ebene" erkennbar sind. Beim Hover wird auch der Text
     blau. Aktiver Zustand (Fenster offen) zusaetzlich mit Akzent-Soft
     Hintergrund. */
  .item-panel i { color: var(--accent); }
  .item-panel:hover { color: var(--accent); }
  .item-panel.active { background: var(--accent-soft); color: var(--accent); }

  /* Info-Fallback: wenn es fuer den aktuellen Kontext keinen spezifischen
     Hilfetext gibt, Eintrag dezenter darstellen (Icon + Text grau). */
  .item-panel.item-panel-muted i { color: var(--fg-faint); }
  .item-panel.item-panel-muted:hover { color: var(--fg-primary); }
  .item-panel.item-panel-muted:hover i { color: var(--fg-primary); }
  .foot {
    border-top: 1px solid var(--border);
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .info {
    padding: 10px 4px 4px;
    display: flex; flex-direction: column;
    gap: 2px;
    font-size: 10px;
    color: var(--fg-faint);
    border-top: 1px solid var(--border);
    margin-top: 6px;
  }
  .info-row { display: flex; justify-content: space-between; gap: 8px; }
  .info-row .k { color: var(--fg-faint); letter-spacing: 0.5px; text-transform: uppercase; font-size: 9px; }
  .danke { color: var(--danger); }
  .repo-link {
    color: var(--fg-primary);
    text-decoration: none;
    display: inline-flex; align-items: center; gap: 6px;
  }
  .repo-link i { color: var(--fg-muted); font-size: 11px; }
  .repo-link:hover { color: var(--accent); }
  .repo-link:hover i { color: var(--accent); }
</style>
