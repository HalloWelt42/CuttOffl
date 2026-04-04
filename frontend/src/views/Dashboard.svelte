<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import PanelHeader from '../components/PanelHeader.svelte';

  let ping = $state(null);
  let files = $state([]);
  let err = $state(null);

  onMount(async () => {
    try {
      [ping, files] = await Promise.all([api.ping(), api.listFiles()]);
    } catch (e) {
      err = e.message;
    }
  });

  function fmtSize(n) {
    if (!n) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
  }
</script>

<section class="panel">
  <PanelHeader icon="fa-gauge-high" title="Dashboard" subtitle="Übersicht" />

  <div class="body">
    {#if err}
      <div class="err mono">Backend nicht erreichbar: {err}</div>
    {:else}
      <div class="cards">
        <div class="card stat">
          <div class="label soft">Backend</div>
          <div class="value mono">{ping?.version ?? '...'}</div>
          <div class="meta">FFmpeg: <span class="mono">{ping?.ffmpeg_version?.split(' ')[2] ?? '-'}</span></div>
        </div>
        <div class="card stat">
          <div class="label soft">HW-Encoder</div>
          <div class="value mono">{ping?.hw_encoder ?? '-'}</div>
          <div class="meta">erkannt zur Laufzeit</div>
        </div>
        <div class="card stat">
          <div class="label soft">Dateien</div>
          <div class="value mono">{files.length}</div>
          <div class="meta">
            Summe: <span class="mono">{fmtSize(files.reduce((a, f) => a + (f.size_bytes || 0), 0))}</span>
          </div>
        </div>
        <div class="card stat">
          <div class="label soft">Proxies fertig</div>
          <div class="value mono">{files.filter((f) => f.has_proxy).length} / {files.length}</div>
          <div class="meta">Low-Res-Previews</div>
        </div>
      </div>
    {/if}
  </div>
</section>

<style>
  .panel { display: flex; flex-direction: column; height: 100%; }
  .body { padding: 16px; overflow: auto; }
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 14px;
  }
  .stat { padding: 14px 16px; }
  .label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--fg-muted);
  }
  .value { font-size: 22px; font-weight: 600; margin: 4px 0; }
  .meta { font-size: 12px; color: var(--fg-faint); }
  .err { padding: 12px; color: var(--danger); }
</style>
