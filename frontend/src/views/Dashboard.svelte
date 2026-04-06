<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { go, openInEditor } from '../lib/nav.svelte.js';
  import PanelHeader from '../components/PanelHeader.svelte';
  import { wsOn, wsStart } from '../lib/ws.svelte.js';

  let overview = $state(null);
  let storage = $state(null);
  let files = $state([]);
  let err = $state(null);

  async function refresh() {
    try {
      [overview, storage, files] = await Promise.all([
        api.systemOverview(),
        api.systemStorage(),
        api.listFiles(),
      ]);
    } catch (e) {
      err = e.message;
    }
  }

  onMount(() => {
    wsStart();
    refresh();
    return wsOn((m) => {
      if (m.type === 'file_event' || m.type === 'job_event') refresh();
    });
  });

  function fmtSize(n) {
    if (!n) return '0 B';
    const u = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
  }
  function fmtDur(s) {
    if (!s) return '0:00';
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const r = Math.floor(s % 60);
    if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(r).padStart(2,'0')}`;
    return `${m}:${String(r).padStart(2,'0')}`;
  }
  function pct(part, total) {
    if (!total) return 0;
    return Math.min(100, Math.max(0, (part / total) * 100));
  }

  const defaultCodec = $derived(() =>
    overview?.codecs?.recommendations?.find((r) => r.default) ??
    overview?.codecs?.recommendations?.[0] ?? null
  );

  const bucketRows = $derived(() => {
    if (!storage) return [];
    const b = storage.buckets;
    return [
      { k: 'originals',  label: 'Originale',      icon: 'fa-video',         color: '#58a6ff' },
      { k: 'proxies',    label: 'Proxy-Vorschau', icon: 'fa-film',          color: '#0d9488' },
      { k: 'exports',    label: 'Fertige Videos', icon: 'fa-box-archive',   color: '#6366f1' },
      { k: 'sprites',    label: 'Thumbnail-Streifen', icon: 'fa-images',    color: '#cfa06b' },
      { k: 'waveforms',  label: 'Wellenformen',   icon: 'fa-wave-square',   color: '#f59e0b' },
      { k: 'thumbs',     label: 'Thumbnails',     icon: 'fa-image',         color: '#9ca3af' },
      { k: 'tmp',        label: 'Temporär',       icon: 'fa-hourglass-half', color: '#6b7280' },
    ].map((r) => ({ ...r, bytes: b[r.k] || 0 }))
     .sort((a, b) => b.bytes - a.bytes);
  });
</script>

<section class="wrap">
  <PanelHeader icon="fa-gauge-high" title="Dashboard" subtitle="Übersicht und Speicher" />

  <div class="body">
    {#if err}
      <div class="card block err mono">Backend nicht erreichbar: {err}</div>
    {:else}

    <!-- Kennzahlen-Leiste -->
    <div class="kpis">
      <button class="kpi" onclick={() => go('library')} title="Zur Bibliothek">
        <i class="fa-solid fa-video"></i>
        <div class="kpi-value mono">{overview?.counts?.files ?? '...'}</div>
        <div class="kpi-label soft">Videos</div>
        <div class="kpi-sub mono">{fmtDur(overview?.total_duration_s ?? 0)} gesamt</div>
      </button>
      <button class="kpi" onclick={() => go('library')}
              title="Bibliothek öffnen">
        <i class="fa-solid fa-film"></i>
        <div class="kpi-value mono">
          {files.filter((f) => f.has_proxy).length}
          <span class="dim">/ {files.length}</span>
        </div>
        <div class="kpi-label soft">Vorschau fertig</div>
        <div class="kpi-sub mono">Proxy-Videos bereit</div>
      </button>
      <button class="kpi" onclick={() => go('library')}
              title="Fertige Schnitt-Exports in der Bibliothek">
        <i class="fa-solid fa-box-archive"></i>
        <div class="kpi-value mono">{overview?.counts?.exports ?? '...'}</div>
        <div class="kpi-label soft">Fertige Schnitte</div>
        <div class="kpi-sub mono">gerendert und abrufbar</div>
      </button>
      <div class="kpi static" title={`${overview?.counts?.active_jobs ?? 0} aktiv, ${overview?.counts?.failed_jobs ?? 0} fehlgeschlagen`}>
        <i class="fa-solid fa-gears"></i>
        <div class="kpi-value mono">
          {overview?.counts?.active_jobs ?? 0}
          {#if overview?.counts?.failed_jobs}
            <span class="fail">· {overview.counts.failed_jobs} ✗</span>
          {/if}
        </div>
        <div class="kpi-label soft">Aktive Jobs</div>
        <div class="kpi-sub mono">{overview?.counts?.projects ?? 0} Projekte insgesamt</div>
      </div>
    </div>

    <!-- Speicher -->
    <div class="card block">
      <div class="block-head">
        <h3><i class="fa-solid fa-hard-drive"></i> Speicher</h3>
        {#if storage?.disk}
          <span class="soft head-info mono">
            {fmtSize(storage.disk.free_bytes)} frei von {fmtSize(storage.disk.total_bytes)}
          </span>
        {/if}
      </div>

      {#if storage?.disk}
        {@const used = storage.disk.total_bytes - storage.disk.free_bytes}
        {@const mine = storage.buckets.total}
        {@const other = Math.max(0, used - mine)}
        <div class="disk-bar" title="Blauer Anteil = CuttOffl-Daten, Grauer Anteil = übrige Dateien">
          <div class="seg mine" style:width="{pct(mine, storage.disk.total_bytes)}%"></div>
          <div class="seg other" style:width="{pct(other, storage.disk.total_bytes)}%"></div>
        </div>
        <div class="disk-legend mono">
          <span><span class="dot dot-mine"></span> CuttOffl: {fmtSize(mine)}</span>
          <span><span class="dot dot-other"></span> Anderes: {fmtSize(other)}</span>
          <span class="dim">Pfad: <code>{storage.data_dir}</code></span>
        </div>
      {/if}

      <div class="buckets">
        {#each bucketRows() as b (b.k)}
          <div class="bucket">
            <div class="bucket-ico" style:color={b.color}><i class="fa-solid {b.icon}"></i></div>
            <div class="bucket-label">{b.label}</div>
            <div class="bucket-bar">
              <div class="bucket-fill"
                   style:width="{pct(b.bytes, storage?.buckets?.total || 1)}%"
                   style:background={b.color}></div>
            </div>
            <div class="bucket-size mono">{fmtSize(b.bytes)}</div>
          </div>
        {/each}
      </div>
    </div>

    <!-- Codec-Empfehlung -->
    {#if overview?.codecs}
      <div class="card block">
        <div class="block-head">
          <h3><i class="fa-solid fa-microchip"></i> Codec-Empfehlung für dieses Gerät</h3>
          <span class="soft head-info">{overview.codecs.platform.env_label}</span>
        </div>
        <p class="soft hint">
          Die optimale Codec-Wahl hängt von der Umgebung ab. Beim Export kannst du
          aus allen verfügbaren Optionen wählen -- der Vorschlag hier ist jeweils
          die beste Mischung aus Geschwindigkeit, Qualität und Dateigröße.
        </p>

        {#if defaultCodec()}
          <div class="codec-hero">
            <div class="codec-badge"><i class="fa-solid fa-bolt"></i> Empfohlen</div>
            <div class="codec-title mono">{defaultCodec().label}</div>
            <div class="codec-tag">{defaultCodec().tag}</div>
            <p class="codec-note soft">{defaultCodec().note}</p>
          </div>
        {/if}

        {#if (overview.codecs.recommendations?.length ?? 0) > 1}
          <details class="more">
            <summary class="soft">Weitere Optionen anzeigen</summary>
            <ul>
              {#each overview.codecs.recommendations.filter((r) => !r.default) as r}
                <li>
                  <div class="r-head">
                    <span class="mono">{r.label}</span>
                    <span class="r-tag">{r.tag}</span>
                  </div>
                  <p class="soft">{r.note}</p>
                </li>
              {/each}
            </ul>
          </details>
        {/if}
      </div>
    {/if}

    <!-- Neueste Videos -->
    {#if files.length}
      <div class="card block">
        <div class="block-head">
          <h3><i class="fa-solid fa-clock"></i> Neueste Videos</h3>
          <button class="btn btn-sm" onclick={() => go('library')}
                  title="Zur vollständigen Bibliothek">
            Alle anzeigen <i class="fa-solid fa-arrow-right"></i>
          </button>
        </div>
        <ul class="files">
          {#each files.slice(0, 5) as f (f.id)}
            <li>
              <button class="file" disabled={!f.has_proxy}
                      onclick={() => openInEditor(f.id)}
                      title={f.has_proxy
                        ? 'Im Editor öffnen'
                        : 'Proxy-Vorschau noch nicht fertig'}>
                {#if f.has_thumb}
                  <img src={api.thumbUrl(f.id)} alt="" />
                {:else}
                  <div class="thumb-fallback"><i class="fa-solid fa-image"></i></div>
                {/if}
                <div class="file-info">
                  <div class="name">{f.original_name}</div>
                  <div class="meta mono">
                    <span>{fmtDur(f.duration_s)}</span>
                    <span>{f.width}×{f.height}</span>
                    <span>{fmtSize(f.size_bytes)}</span>
                    {#if !f.has_proxy}<span class="dim">Proxy läuft …</span>{/if}
                  </div>
                </div>
              </button>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    {/if}
  </div>
</section>

<style>
  .wrap { display: flex; flex-direction: column; height: 100%; }
  .body { padding: 20px; overflow: auto; display: flex; flex-direction: column; gap: 16px; max-width: 1200px; }
  .err { color: var(--danger); }

  /* KPIs */
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 12px;
  }
  .kpi {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    cursor: pointer;
    text-align: left;
    font: inherit;
    color: inherit;
    transition: border-color 120ms, transform 120ms;
    display: flex; flex-direction: column; gap: 2px;
    position: relative;
  }
  .kpi:not(.static):hover { border-color: var(--accent); transform: translateY(-1px); }
  .kpi.static { cursor: default; }
  .kpi > i {
    position: absolute; top: 14px; right: 14px;
    color: var(--fg-faint);
    font-size: 16px;
  }
  .kpi-value { font-size: 24px; font-weight: 700; line-height: 1.1; }
  .kpi-value .dim { color: var(--fg-faint); font-weight: 400; }
  .kpi-value .fail { color: var(--danger); font-size: 14px; margin-left: 4px; }
  .kpi-label { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--fg-muted); }
  .kpi-sub { font-size: 11px; color: var(--fg-faint); margin-top: 4px; }

  /* Block */
  .block { padding: 16px; }
  .block-head {
    display: flex; align-items: center; justify-content: space-between;
    gap: 10px;
    margin-bottom: 10px;
  }
  .block h3 {
    display: flex; align-items: center; gap: 8px;
    margin: 0; font-size: 14px;
  }
  .block h3 i { color: var(--accent); }
  .head-info { font-size: 11px; color: var(--fg-muted); }
  .hint { font-size: 12px; color: var(--fg-muted); margin: 4px 0 12px; line-height: 1.5; }

  /* Disk-Bar */
  .disk-bar {
    display: flex; height: 10px; width: 100%;
    background: var(--bg-sink);
    border-radius: 5px;
    overflow: hidden;
    margin: 8px 0 6px;
    border: 1px solid var(--border);
  }
  .seg.mine  { background: var(--accent); }
  .seg.other { background: var(--border-strong); }
  .disk-legend {
    display: flex; gap: 14px; flex-wrap: wrap;
    font-size: 11px; color: var(--fg-muted);
    margin-bottom: 12px;
  }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: middle; }
  .dot-mine { background: var(--accent); }
  .dot-other { background: var(--border-strong); }
  .disk-legend code { font-size: 10px; }

  /* Bucket-Rows */
  .buckets { display: flex; flex-direction: column; gap: 6px; margin-top: 4px; }
  .bucket {
    display: grid;
    grid-template-columns: 24px 170px 1fr 80px;
    align-items: center;
    gap: 10px;
    font-size: 12px;
  }
  .bucket-ico { text-align: center; }
  .bucket-label { color: var(--fg-muted); }
  .bucket-bar {
    height: 6px; background: var(--bg-sink); border-radius: 3px; overflow: hidden;
    border: 1px solid var(--border);
  }
  .bucket-fill { height: 100%; }
  .bucket-size { text-align: right; color: var(--fg-primary); }

  /* Codec */
  .codec-hero {
    background: var(--accent-soft);
    border: 1px solid var(--accent);
    border-radius: 8px;
    padding: 12px 14px;
    display: flex; flex-direction: column; gap: 4px;
  }
  .codec-badge {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 10px; font-weight: 700; letter-spacing: 1px;
    color: var(--accent);
    text-transform: uppercase;
  }
  .codec-title { font-size: 15px; font-weight: 700; }
  .codec-tag { font-size: 11px; color: var(--fg-muted); text-transform: lowercase; }
  .codec-note { font-size: 12px; line-height: 1.5; margin: 2px 0 0; }

  .more { margin-top: 10px; font-size: 12px; }
  .more summary { cursor: pointer; padding: 4px 0; color: var(--fg-muted); }
  .more ul { list-style: none; padding: 0; margin: 8px 0 0; display: flex; flex-direction: column; gap: 10px; }
  .more li {
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px 12px;
  }
  .r-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
  .r-head span:first-child { font-size: 13px; color: var(--fg-primary); }
  .r-tag { font-size: 10px; color: var(--fg-muted); text-transform: lowercase; }
  .more p { margin: 6px 0 0; font-size: 11px; line-height: 1.5; color: var(--fg-muted); }

  /* Files */
  .files { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
  .file {
    width: 100%;
    display: grid; grid-template-columns: 80px 1fr;
    gap: 12px;
    align-items: center;
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px;
    cursor: pointer;
    text-align: left; font: inherit;
    transition: border-color 120ms;
  }
  .file:hover:not(:disabled) { border-color: var(--accent); }
  .file:disabled { cursor: not-allowed; opacity: 0.55; }
  .file img { width: 80px; height: 45px; object-fit: cover; border-radius: 4px; }
  .thumb-fallback {
    width: 80px; height: 45px; display: grid; place-items: center;
    background: var(--bg-sink); border-radius: 4px; color: var(--fg-faint);
  }
  .file-info { min-width: 0; }
  .file .name { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .file .meta { display: flex; gap: 10px; font-size: 11px; color: var(--fg-muted); margin-top: 3px; }
</style>
