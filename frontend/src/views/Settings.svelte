<script>
  import { onMount } from 'svelte';
  import PanelHeader from '../components/PanelHeader.svelte';
  import { api } from '../lib/api.js';
  import { toast } from '../lib/toast.svelte.js';

  let ping = $state(null);
  let counts = $state({ files: 0, projects: 0, exports: 0 });
  let paths = $state(null);

  // Formular
  let originalsInput = $state('');
  let exportsInput = $state('');
  let saving = $state(false);

  async function loadAll() {
    try {
      const [p, files, projects, exports, pp] = await Promise.all([
        api.ping(), api.listFiles(), api.listProjects(),
        api.listExports(), api.systemPaths(),
      ]);
      ping = p;
      counts = { files: files.length, projects: projects.length, exports: exports.length };
      paths = pp;
      originalsInput = pp.saved?.originals_dir ?? '';
      exportsInput   = pp.saved?.exports_dir   ?? '';
    } catch (e) { toast.error(e.message); }
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
  <PanelHeader icon="fa-gear" title="Einstellungen" subtitle="System & Pfade" />

  <div class="body">
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
