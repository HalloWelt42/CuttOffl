<script>
  import { onMount } from 'svelte';
  import PanelHeader from '../components/PanelHeader.svelte';
  import { api } from '../lib/api.js';

  let ping = $state(null);
  let counts = $state({ files: 0, projects: 0, exports: 0 });

  onMount(async () => {
    try {
      const [p, files, projects, exports] = await Promise.all([
        api.ping(), api.listFiles(), api.listProjects(), api.listExports(),
      ]);
      ping = p;
      counts = { files: files.length, projects: projects.length, exports: exports.length };
    } catch {}
  });
</script>

<section class="wrap view-readable">
  <PanelHeader icon="fa-gear" title="Einstellungen" subtitle="Erscheinung & System" />

  <div class="body">
    <div class="card block">
      <h3>System</h3>
      <dl class="kv mono">
        <dt>Backend</dt><dd>{ping?.app ?? '-'} v{ping?.version ?? '-'}</dd>
        <dt>Host</dt><dd>{ping?.host ?? '-'}:{ping?.port ?? '-'}</dd>
        <dt>HW-Encoder</dt><dd>{ping?.hw_encoder ?? '-'}</dd>
        <dt>FFmpeg</dt><dd>{ping?.ffmpeg_version?.split(' ').slice(0,3).join(' ') ?? '-'}</dd>
        <dt>Dateien</dt><dd>{counts.files}</dd>
        <dt>Projekte</dt><dd>{counts.projects}</dd>
        <dt>Exporte</dt><dd>{counts.exports}</dd>
      </dl>
    </div>

    <div class="card block hint-block soft">
      <i class="fa-solid fa-keyboard"></i>
      <div>
        <h3>Tastaturkürzel im Editor</h3>
        <dl class="kv">
          <dt>Leertaste</dt><dd>Play / Pause</dd>
          <dt>Shift + Leertaste</dt><dd>Timeline abspielen (alle Clips) · erneut stoppt</dd>
          <dt>J / L</dt><dd>5 s zurück / vor</dd>
          <dt>← / →</dt><dd>1 Frame zurück / vor (+ Shift = 10 Frames)</dd>
          <dt>, / .</dt><dd>vorheriger / nächster Keyframe</dd>
          <dt>I / O</dt><dd>In- / Out-Punkt setzen (rastet auf Keyframe wenn Snap an)</dd>
          <dt>P</dt><dd>Auswahl oder Clip vorspielen</dd>
          <dt>Enter</dt><dd>Clip aus In/Out erzeugen</dd>
          <dt>S</dt><dd>Clip am Playhead teilen</dd>
          <dt>Esc</dt><dd>Vorschau stoppen</dd>
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
    max-width: 760px;
    overflow: auto;
  }
  .block { padding: 16px; }
  h3 { margin: 0 0 6px; font-size: 14px; color: var(--fg-primary); }
  .hint { font-size: 12px; margin: 0 0 10px; color: var(--fg-muted); }
  .kv {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 4px 16px;
    margin: 0;
    font-size: 12px;
  }
  .kv dt { color: var(--fg-muted); }
  .kv dd { margin: 0; color: var(--fg-primary); }
  .hint-block { display: flex; gap: 14px; }
  .hint-block > i { color: var(--accent); font-size: 22px; padding-top: 2px; }
</style>
