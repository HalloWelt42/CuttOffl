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
      <p class="soft hint">
        Videos liegen standardmäßig im Projekt-Unterordner <code>data/</code>.
        Du kannst die Basis für <b>Originale</b> und <b>fertige Videos</b>
        auf einen beliebigen Ordner auf deinem Rechner legen -- zum Beispiel
        ein Verzeichnis auf einer größeren Festplatte oder einem Netzlaufwerk.
        Schreibrechte sind Pflicht. Der Pfad wird beim Speichern geprüft.
      </p>
      <p class="soft warn">
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
      <dl class="kv mono">
        <dt>Backend</dt><dd>{ping?.app ?? '-'} v{ping?.version ?? '-'}</dd>
        <dt>Host</dt><dd>{ping?.host ?? '-'}:{ping?.port ?? '-'}</dd>
        <dt>HW-Encoder</dt><dd>{ping?.hw_encoder ?? '-'}</dd>
        <dt>FFmpeg</dt><dd>{ping?.ffmpeg_version?.split(' ').slice(0,3).join(' ') ?? '-'}</dd>
        <dt>Dateien</dt><dd>{counts.files}</dd>
        <dt>Projekte</dt><dd>{counts.projects}</dd>
        <dt>Fertige Videos</dt><dd>{counts.exports}</dd>
      </dl>
    </div>

    <div class="card block hint-block soft">
      <i class="fa-solid fa-keyboard"></i>
      <div>
        <h3>Tastaturkürzel im Editor</h3>
        <dl class="kv">
          <dt>Leertaste</dt><dd>Play / Pause</dd>
          <dt>Shift + Leertaste</dt><dd>Timeline abspielen (alle Clips)</dd>
          <dt>J / L</dt><dd>5 s zurück / vor</dd>
          <dt>← / →</dt><dd>1 Frame zurück / vor (+ Shift = 10 Frames)</dd>
          <dt>, / .</dt><dd>vorheriger / nächster Keyframe</dd>
          <dt>I / O</dt><dd>In- / Out-Punkt setzen</dd>
          <dt>P</dt><dd>Auswahl oder Clip vorspielen</dd>
          <dt>Enter</dt><dd>Clip aus In/Out erzeugen</dd>
          <dt>S</dt><dd>Clip am Playhead teilen</dd>
          <dt>Esc</dt><dd>Vorschau / Dialog stoppen</dd>
          <dt>Entf / ⌫</dt><dd>ausgewählten Clip löschen</dd>
          <dt>⌘/Ctrl + Z</dt><dd>Undo · + Shift = Redo</dd>
          <dt>⌘/Ctrl + Mausrad</dt><dd>Timeline zoomen</dd>
        </dl>
      </div>
    </div>
  </div>
</section>

<style>
  .wrap { display: flex; flex-direction: column; height: 100%; }
  .body {
    padding: 20px; display: flex; flex-direction: column; gap: 16px;
    max-width: 820px;
    overflow: auto;
  }
  .block { padding: 18px; }
  h3 {
    display: flex; align-items: center; gap: 8px;
    margin: 0 0 8px; font-size: 15px; color: var(--fg-primary);
  }
  h3 i { color: var(--accent); }
  .hint { font-size: 13px; margin: 0 0 10px; color: var(--fg-muted); line-height: 1.6; }
  .warn { color: var(--warning); font-size: 13px; line-height: 1.6; display: flex; gap: 8px; align-items: flex-start; }
  .warn i { padding-top: 3px; flex: 0 0 auto; }

  .field { margin-top: 14px; }
  .field label {
    display: block; font-size: 12px; color: var(--fg-muted);
    letter-spacing: 0.5px; margin-bottom: 6px;
  }
  .field .row { display: flex; gap: 8px; }
  .field input {
    flex: 1 1 auto;
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--border-strong);
    border-radius: 6px;
    padding: 8px 10px;
    font: inherit;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
  }
  .field input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-soft);
  }
  .meta { margin-top: 4px; font-size: 11px; color: var(--fg-faint); }

  .actions { margin-top: 14px; display: flex; justify-content: flex-end; }

  .kv {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 6px 16px;
    margin: 0;
    font-size: 13px;
  }
  .kv dt { color: var(--fg-muted); }
  .kv dd { margin: 0; color: var(--fg-primary); }
  .hint-block { display: flex; gap: 14px; }
  .hint-block > i { color: var(--accent); font-size: 22px; padding-top: 2px; }

  code {
    background: var(--bg-elev);
    padding: 1px 5px;
    border-radius: 3px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
  }
</style>
