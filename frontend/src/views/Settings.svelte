<script>
  import { onMount } from 'svelte';
  import PanelHeader from '../components/PanelHeader.svelte';
  import { api } from '../lib/api.js';
  import { toast } from '../lib/toast.svelte.js';
  import { nav, setSettingsTab, SETTINGS_TABS } from '../lib/nav.svelte.js';
  import { persisted, persist } from '../lib/persist.svelte.js';

  // Aktiver Tab -- Quelle: URL (nav.settingsTab), sonst persistierter
  // Zuletzt-Tab, sonst Default.
  const DEFAULT_TAB = 'pfade';
  let activeTab = $state(
    nav.settingsTab || persisted('settings.tab', DEFAULT_TAB) || DEFAULT_TAB,
  );

  // Beim ersten Mount: URL-Tab ggf. ergaenzen, damit Deeplink bestehen
  // bleibt (z. B. /settings ohne Tab bekommt ?tab=pfade).
  onMount(() => {
    if (!nav.settingsTab) setSettingsTab(activeTab);
  });

  // Auf URL-Aenderungen reagieren (Back/Forward)
  $effect(() => {
    if (nav.settingsTab && nav.settingsTab !== activeTab) {
      activeTab = nav.settingsTab;
    }
  });

  function pickTab(t) {
    if (!SETTINGS_TABS.includes(t)) return;
    activeTab = t;
    persist('settings.tab', t);
    setSettingsTab(t);
  }

  const TABS = [
    { id: 'pfade',         label: 'Arbeits-Verzeichnisse', icon: 'fa-folder-tree' },
    { id: 'transkription', label: 'Transkription',         icon: 'fa-closed-captioning' },
    { id: 'system',        label: 'System-Info',           icon: 'fa-circle-info' },
  ];

  let ping = $state(null);
  let counts = $state({ files: 0, projects: 0, exports: 0 });
  let paths = $state(null);
  let txStatus = $state(null);
  let txScanning = $state(false);
  let txExtraPath = $state('');

  // Formular
  let originalsInput = $state('');
  let exportsInput = $state('');
  let saving = $state(false);

  async function loadAll() {
    try {
      const [p, files, projects, exports, pp, tx] = await Promise.all([
        api.ping(), api.listFiles(), api.listProjects(),
        api.listExports(), api.systemPaths(),
        api.transcriptionStatus().catch(() => null),
      ]);
      ping = p;
      counts = { files: files.length, projects: projects.length, exports: exports.length };
      paths = pp;
      originalsInput = pp.saved?.originals_dir ?? '';
      exportsInput   = pp.saved?.exports_dir   ?? '';
      txStatus = tx;
    } catch (e) { toast.error(e.message); }
  }

  async function useModel(m) {
    try {
      await api.setTranscriptionPreference(m.engine, m.model);
      txStatus = await api.transcriptionStatus();
      toast.success(`Aktiv: ${m.engine} / ${m.model}`);
    } catch (e) { toast.error(e.message); }
  }

  async function resetPreference() {
    try {
      await api.setTranscriptionPreference(null, null);
      txStatus = await api.transcriptionStatus();
      toast.info('Auswahl zurückgesetzt -- Auto-Vorschlag wird verwendet');
    } catch (e) { toast.error(e.message); }
  }

  async function scanModels() {
    txScanning = true;
    try {
      const res = await api.transcriptionScan(
        txExtraPath ? [txExtraPath.trim()] : [],
      );
      // Kompletten Status neu laden, damit suggested_* aktualisiert wird
      txStatus = await api.transcriptionStatus();
      const n = res.models_found?.length || 0;
      toast.success(n ? `${n} Modelle gefunden` : 'Kein Whisper-Modell gefunden');
    } catch (e) { toast.error(e.message); }
    finally { txScanning = false; }
  }

  function fmtSizeB(n) {
    if (!n) return '-';
    const u = ['B','KB','MB','GB','TB'];
    let i = 0; while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
  }

  onMount(loadAll);

  async function savePaths() {
    saving = true;
    try {
      const body = {
        originals_dir: originalsInput.trim(),
        exports_dir:   exportsInput.trim(),
      };
      const res = await api.setSystemPaths(body);
      toast.success('Pfade gespeichert. Bitte Backend neu starten, damit sie aktiv werden.');
      paths = await api.systemPaths();
    } catch (e) { toast.error(e.message); }
    finally { saving = false; }
  }

  function resetOriginals() { originalsInput = ''; }
  function resetExports()   { exportsInput = ''; }
</script>

<section class="wrap view-readable">
  <PanelHeader icon="fa-gear" title="Einstellungen"
               subtitle={TABS.find((t) => t.id === activeTab)?.label ?? ''} />

  <!-- Tab-Leiste direkt unter dem Header. Deeplinks: /settings/<tab> -->
  <div class="tabs" role="tablist" aria-label="Einstellungs-Bereiche">
    {#each TABS as t (t.id)}
      <button class="tab" role="tab" aria-selected={activeTab === t.id}
              class:active={activeTab === t.id}
              onclick={() => pickTab(t.id)}
              title="Zum Bereich {t.label} wechseln">
        <i class="fa-solid {t.icon}"></i>
        <span>{t.label}</span>
      </button>
    {/each}
  </div>

  <div class="body">
    {#if activeTab === 'pfade'}
    <div class="card block">
      <h3><i class="fa-solid fa-folder-tree"></i> Arbeits-Verzeichnisse</h3>
      <p class="hint">
        Videos liegen standardmäßig im Projekt-Unterordner <code>data/</code>.
        Du kannst die Basis für <b>Originale</b> und <b>fertige Videos</b>
        auf einen beliebigen Ordner auf deinem Rechner legen -- zum Beispiel
        ein Verzeichnis auf einer größeren Festplatte oder einem Netzlaufwerk.
        Schreibrechte sind Pflicht. Der Pfad wird beim Speichern geprüft.
      </p>
      <p class="warn">
        <i class="fa-solid fa-triangle-exclamation"></i>
        Änderungen werden erst nach einem Neustart des Backends wirksam.
        Bereits vorhandene Dateien bleiben am alten Ort -- bei Bedarf
        manuell in den neuen Ordner verschieben.
      </p>

      <div class="field">
        <label for="p-orig">Originale (hochgeladene Videos)</label>
        <div class="row">
          <input id="p-orig" type="text" bind:value={originalsInput}
                 placeholder={paths?.default?.originals_dir || ''} />
          <button class="btn" type="button" onclick={resetOriginals}
                  title="Eintrag leeren -- nach Speichern wird wieder der Default verwendet">
            <i class="fa-solid fa-rotate-left"></i>
          </button>
        </div>
        <div class="meta mono">
          <span>aktuell aktiv: {paths?.active?.originals_dir ?? '…'}</span>
        </div>
      </div>

      <div class="field">
        <label for="p-exp">Fertige Videos (gerenderte Exports)</label>
        <div class="row">
          <input id="p-exp" type="text" bind:value={exportsInput}
                 placeholder={paths?.default?.exports_dir || ''} />
          <button class="btn" type="button" onclick={resetExports}
                  title="Eintrag leeren -- nach Speichern wird wieder der Default verwendet">
            <i class="fa-solid fa-rotate-left"></i>
          </button>
        </div>
        <div class="meta mono">
          <span>aktuell aktiv: {paths?.active?.exports_dir ?? '…'}</span>
        </div>
      </div>

      <div class="actions">
        <button class="btn btn-primary" onclick={savePaths} disabled={saving}
                title="Pfade speichern. Werden nach Backend-Neustart aktiv.">
          <i class="fa-solid fa-floppy-disk"></i>
          {saving ? 'Speichert…' : 'Speichern'}
        </button>
      </div>
    </div>

    {:else if activeTab === 'system'}
    <div class="card block">
      <h3><i class="fa-solid fa-circle-info"></i> System</h3>
      <!-- Zwei Spalten fuer die kurzen Info-Paare; bricht auf schmalen
           Fenstern auf eine Spalte um. -->
      <dl class="kv kv-two">
        <div><dt>Backend</dt><dd class="mono">{ping?.app ?? '-'} v{ping?.version ?? '-'}</dd></div>
        <div><dt>Host</dt><dd class="mono">{ping?.host ?? '-'}:{ping?.port ?? '-'}</dd></div>
        <div><dt>HW-Encoder</dt><dd class="mono">{ping?.hw_encoder ?? '-'}</dd></div>
        <div><dt>FFmpeg</dt><dd class="mono">{ping?.ffmpeg_version?.split(' ').slice(0,3).join(' ') ?? '-'}</dd></div>
        <div><dt>Dateien</dt><dd class="mono">{counts.files}</dd></div>
        <div><dt>Projekte</dt><dd class="mono">{counts.projects}</dd></div>
        <div><dt>Fertige Videos</dt><dd class="mono">{counts.exports}</dd></div>
      </dl>
    </div>

    {:else if activeTab === 'transkription'}
    <div class="card block">
      <h3><i class="fa-solid fa-closed-captioning"></i> Transkription (KI-Untertitel)</h3>
      <p class="hint">
        CuttOffl kann Videos mit Whisper transkribieren und daraus SRT-
        Untertitel erzeugen. Die Transkription läuft komplett lokal. Die
        Whisper-Pakete und -Modelle musst du einmal selbst installieren --
        die App entdeckt Modelle, die schon auf deinem Rechner liegen
        (HuggingFace-Cache, openai-whisper-Cache, Voice2Text-Cache).
      </p>

      {#if !txStatus}
        <p class="meta">Lade Status …</p>
      {:else if !txStatus.available}
        <div class="tx-offline">
          <div class="tx-row">
            <span class="tx-dot off"></span>
            <b>Nicht einsatzbereit</b>
          </div>
          {#each txStatus.notes as n}
            <p class="note">{n}</p>
          {/each}
          <details class="install">
            <summary>Installationshinweise anzeigen</summary>
            <pre>{@html `# Variante A -- einmalig im Setup mitinstallieren:
./setup.sh --with-transcription

# Variante B -- in die bestehende Backend-venv nachinstallieren:
cd backend && source .venv/bin/activate
pip install -r requirements-transcription.txt

# Variante C -- einzelne Engine selbst waehlen:
#   Apple Silicon:   pip install mlx-whisper
#   Pi/Linux/Intel:  pip install faster-whisper
#   Referenz:        pip install openai-whisper

# Danach Backend einmal neu starten:
./start.sh restart backend`}</pre>
          </details>
        </div>
      {:else}
        <div class="tx-ready">
          <div class="tx-row">
            <span class="tx-dot on"></span>
            <b>Einsatzbereit</b>
          </div>
          <dl class="kv kv-two">
            <div><dt>Aktive Engine</dt><dd class="mono">{txStatus.active_engine}</dd></div>
            <div><dt>Aktives Modell</dt><dd class="mono">{txStatus.active_model}</dd></div>
          </dl>
          {#if (txStatus.active_engine !== txStatus.suggested_engine
                || txStatus.active_model !== txStatus.suggested_model)}
            <p class="meta">
              Auto-Vorschlag wäre: {txStatus.suggested_engine} / {txStatus.suggested_model}
              <button class="btn btn-sm" onclick={resetPreference}
                      title="Eigene Modellwahl verwerfen und wieder dem Vorschlag folgen">
                <i class="fa-solid fa-rotate-left"></i> Auf Vorschlag zurück
              </button>
            </p>
          {/if}
        </div>
      {/if}

      <h4 class="sub">Installierte Pakete</h4>
      <ul class="engines">
        {#each (txStatus?.engines || []) as e (e.name)}
          <li>
            <span class="tx-dot {e.installed ? 'on' : 'off'}"></span>
            <span class="name mono">{e.name}</span>
            {#if e.preferred}<span class="tag preferred">empfohlen</span>{/if}
            {#if !e.installed}<span class="reason">{e.reason}</span>{/if}
          </li>
        {/each}
      </ul>

      <h4 class="sub">Gefundene Modelle auf der Platte</h4>
      {#if (txStatus?.models_found?.length || 0) === 0}
        <p class="meta">Bisher keine Modelle gefunden. Scanne weiter unten.</p>
      {:else}
        <ul class="models">
          {#each txStatus.models_found as m (m.engine + m.path)}
            {@const isActive = m.engine === txStatus.active_engine
                               && m.model === txStatus.active_model}
            {@const engineInstalled = txStatus.engines.find(
              (e) => e.name === m.engine)?.installed}
            <li class:active={isActive}>
              <div class="m-head">
                <span class="name mono">{m.engine} / {m.model}</span>
                {#if isActive}
                  <span class="badge-active">
                    <i class="fa-solid fa-check"></i> Aktiv
                  </span>
                {:else}
                  <button class="btn btn-sm"
                          onclick={() => useModel(m)}
                          disabled={!engineInstalled}
                          title={engineInstalled
                            ? 'Dieses Modell für die Transkription verwenden'
                            : `Engine ${m.engine} ist nicht installiert -- siehe Installationshinweise oben`}>
                    <i class="fa-solid fa-check"></i>
                    Auswählen
                  </button>
                {/if}
                <span class="size mono">{fmtSizeB(m.size_bytes)}</span>
              </div>
              <div class="path mono" title={m.path}>{m.path}</div>
            </li>
          {/each}
        </ul>
      {/if}

      <div class="scan-row">
        <input type="text" class="scan-input"
               placeholder="Optional: zusätzlichen Ordner zum Scannen …"
               bind:value={txExtraPath} />
        <button class="btn" onclick={scanModels} disabled={txScanning}
                title="Bekannte Cache-Ordner und den angegebenen Pfad nach Whisper-Modellen absuchen">
          <i class="fa-solid fa-magnifying-glass"></i>
          {txScanning ? 'Scanne …' : 'Festplatte scannen'}
        </button>
      </div>
    </div>
    {/if}

    <!-- Tab-unabhaengiger Hinweis -- bleibt immer am unteren Rand -->
    <p class="hint-to-panel">
      <i class="fa-solid fa-circle-info"></i>
      Tastaturkürzel und kontextbezogene Hinweise findest du jetzt im
      <b>Info</b>-Fenster (linke Seitenleiste, Hilfe-Bereich). Der Inhalt
      passt sich automatisch an die aktive Ansicht an.
    </p>
  </div>
</section>

<style>
  .wrap { display: flex; flex-direction: column; height: 100%; }

  /* Tab-Leiste direkt unter dem Panel-Header. Layout wie die Info-/
     Exports-Tabs im Editor: Aktiver Tab akzent-eingefärbt mit unterer
     Linie. */
  .tabs {
    display: flex;
    gap: 2px;
    padding: 6px 20px 0;
    background: var(--bg-panel);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }
  .tab {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border: none;
    background: transparent;
    color: var(--fg-muted);
    font: inherit;
    font-size: 13px;
    cursor: pointer;
    border-radius: 6px 6px 0 0;
    border-bottom: 2px solid transparent;
  }
  .tab:hover { color: var(--fg-primary); background: var(--bg-elev); }
  .tab.active {
    color: var(--accent);
    background: var(--bg-elev);
    border-bottom-color: var(--accent);
  }
  .tab i { font-size: 13px; }

  .body {
    padding: 24px; display: flex; flex-direction: column; gap: 18px;
    max-width: 900px;
    overflow: auto;
  }
  .block { padding: 20px; }
  h3 {
    display: flex; align-items: center; gap: 8px;
    margin: 0 0 10px; font-size: 17px; color: var(--fg-primary);
    font-weight: 600;
  }
  h3 i { color: var(--accent); }

  /* Lesetexte bewusst groesser als die dichte Cutter-UI */
  .hint {
    font-size: 15px;
    margin: 0 0 12px;
    color: var(--fg-primary);
    line-height: 1.7;
  }
  .warn {
    color: var(--warning);
    font-size: 14px;
    line-height: 1.7;
    display: flex;
    gap: 10px;
    align-items: flex-start;
  }
  .warn i { padding-top: 3px; flex: 0 0 auto; }

  .field { margin-top: 16px; }
  .field label {
    display: block;
    font-size: 14px;
    color: var(--fg-primary);
    letter-spacing: 0.2px;
    margin-bottom: 6px;
    font-weight: 600;
  }
  .field .row { display: flex; gap: 8px; }
  .field input {
    flex: 1 1 auto;
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--border-strong);
    border-radius: 6px;
    padding: 10px 12px;
    /* Pfade profitieren trotzdem von Monospace, aber etwas groesser */
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 14px;
  }
  .field input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-soft);
  }
  .meta { margin-top: 6px; font-size: 12px; color: var(--fg-faint); }
  .meta.mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }

  .actions { margin-top: 16px; display: flex; justify-content: flex-end; }

  /* System-Info als Key-Value-Raster, standardmaessig zweispaltig. Label
     in Basis-Schrift, Werte in Mono (damit Versionen und IPs sauber
     ausgerichtet aussehen). */
  .kv {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 8px 16px;
    margin: 0;
    font-size: 14.5px;
  }
  .kv dt {
    color: var(--fg-muted);
    font-weight: 500;
  }
  .kv dd { margin: 0; color: var(--fg-primary); }
  .kv dd.mono {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 13.5px;
  }

  .kv-two {
    grid-template-columns: 1fr 1fr;
    gap: 10px 24px;
  }
  .kv-two > div {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 4px 12px;
    align-items: baseline;
  }
  @media (max-width: 640px) {
    .kv-two { grid-template-columns: 1fr; }
  }

  /* Transkriptions-Block */
  .sub {
    margin: 16px 0 8px;
    font-size: 12px;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: var(--fg-muted);
  }
  .note { margin: 4px 0; font-size: 14px; color: var(--fg-primary); line-height: 1.6; }
  .tx-row { display: flex; align-items: center; gap: 8px; font-size: 14px; }
  .tx-dot {
    width: 10px; height: 10px; border-radius: 50%;
    display: inline-block;
    background: var(--fg-faint);
  }
  .tx-dot.on  { background: var(--success); }
  .tx-dot.off { background: var(--danger); }
  .tx-ready, .tx-offline { padding: 4px 0 2px; }

  .engines {
    list-style: none; padding: 0; margin: 0;
    display: flex; flex-direction: column; gap: 6px;
    font-size: 13px;
  }
  .engines li {
    display: flex; align-items: center; gap: 8px;
    flex-wrap: wrap;
  }
  .engines .reason { color: var(--fg-muted); font-size: 12px; }
  .tag.preferred {
    background: var(--accent-soft);
    color: var(--accent);
    font-size: 10px; font-weight: 700;
    padding: 1px 6px; border-radius: 4px;
    text-transform: uppercase; letter-spacing: 0.5px;
  }

  .models {
    list-style: none; padding: 0; margin: 0;
    display: flex; flex-direction: column; gap: 6px;
  }
  .models li {
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 10px;
    transition: border-color 120ms, background 120ms;
  }
  .models li.active {
    background: var(--accent-soft);
    border-color: var(--accent);
  }
  .m-head {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
  }
  .m-head .name { font-weight: 600; flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
  .m-head .size { color: var(--fg-muted); font-size: 12px; flex: 0 0 auto; }
  .badge-active {
    display: inline-flex; align-items: center; gap: 4px;
    background: var(--accent);
    color: var(--accent-on);
    font-size: 11px; font-weight: 700;
    padding: 3px 8px; border-radius: 4px;
    text-transform: uppercase; letter-spacing: 0.5px;
  }
  .models .path {
    margin-top: 3px;
    font-size: 11px;
    color: var(--fg-faint);
    word-break: break-all;
    line-height: 1.4;
  }

  .scan-row {
    display: flex; gap: 8px; margin-top: 12px;
  }
  .scan-input {
    flex: 1 1 auto;
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--border-strong);
    border-radius: 6px;
    padding: 8px 10px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 13px;
  }
  .scan-input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-soft);
  }

  .install summary {
    cursor: pointer;
    color: var(--fg-muted);
    font-size: 13px;
    margin-top: 6px;
  }
  .install pre {
    margin: 8px 0 0;
    padding: 12px;
    background: var(--bg-sink);
    border: 1px solid var(--border);
    border-radius: 6px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 12px;
    color: var(--fg-primary);
    white-space: pre-wrap;
    line-height: 1.55;
  }

  .hint-to-panel {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    padding: 14px 18px;
    background: var(--accent-soft);
    border: 1px solid color-mix(in oklab, var(--accent) 40%, var(--border));
    border-radius: 8px;
    font-size: 15px;
    line-height: 1.7;
    color: var(--fg-primary);
  }
  .hint-to-panel i { color: var(--accent); padding-top: 4px; }
  .hint-to-panel b { color: var(--accent); }

  code {
    background: var(--bg-elev);
    padding: 1px 6px;
    border-radius: 3px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 13px;
  }
</style>
