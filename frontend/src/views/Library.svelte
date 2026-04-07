<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { wsOn, wsStart } from '../lib/ws.svelte.js';
  import { toast } from '../lib/toast.svelte.js';
  import { openInEditor } from '../lib/nav.svelte.js';
  import PanelHeader from '../components/PanelHeader.svelte';

  let files = $state([]);
  let uploading = $state(false);
  let uploadPct = $state(0);
  let fileInput;

  async function refresh() {
    try { files = await api.listFiles(); }
    catch (e) { toast.error(e.message); }
  }

  onMount(() => {
    wsStart();
    refresh();
    return wsOn((msg) => {
      if (msg.type === 'file_event') refresh();
    });
  });

  async function onUpload(ev) {
    const file = ev.target.files?.[0];
    if (!file) return;
    uploading = true;
    uploadPct = 0;
    try {
      await api.upload(file, (p) => (uploadPct = p));
      toast.success(`${file.name} hochgeladen -- Proxy wird erzeugt`);
      refresh();
    } catch (e) {
      toast.error(e.message);
    } finally {
      uploading = false;
      fileInput.value = '';
    }
  }

  async function onDelete(f) {
    if (!confirm(`Datei "${f.original_name}" wirklich löschen?`)) return;
    try {
      await api.deleteFile(f.id);
      toast.info(`Gelöscht: ${f.original_name}`);
      refresh();
    } catch (e) { toast.error(e.message); }
  }

  async function onRegenProxy(f) {
    try {
      await api.regenerateProxy(f.id);
      toast.info('Proxy-Neugenerierung gestartet');
    } catch (e) { toast.error(e.message); }
  }

  async function onRename(f) {
    const next = prompt('Neuen Dateinamen eingeben:', f.original_name);
    if (next == null) return;
    const name = next.trim();
    if (!name || name === f.original_name) return;
    try {
      await api.renameFile(f.id, name);
      toast.success('Datei umbenannt');
      refresh();
    } catch (e) { toast.error(e.message); }
  }

  function fmtSize(n) {
    if (!n) return '-';
    const u = ['B','KB','MB','GB','TB'];
    let i = 0; while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
  }
  function fmtDur(s) {
    if (s == null) return '-';
    const m = Math.floor(s / 60);
    const r = Math.floor(s % 60);
    return `${m}:${String(r).padStart(2, '0')}`;
  }
  function statusBadge(f) {
    if (f.proxy_status === 'ready') return { c: 'ok',   t: 'bereit' };
    if (f.proxy_status === 'running') return { c: 'run', t: 'Proxy...' };
    if (f.proxy_status === 'failed') return { c: 'err', t: 'Fehler' };
    return { c: 'idle', t: 'wartend' };
  }
</script>

<section class="panel">
  <PanelHeader icon="fa-folder-tree" title="Bibliothek" subtitle={`${files.length} Datei(en)`}>
    <label class="btn btn-primary" class:busy={uploading}
           title="Eine Video-Datei vom Rechner hochladen. Unterstützte Formate: MP4, MOV, MKV, WebM, AVI, M4V.">
      <i class="fa-solid fa-upload"></i>
      <span>{uploading ? `Hochladen ${Math.round(uploadPct * 100)} %` : 'Video hochladen'}</span>
      <input
        bind:this={fileInput}
        type="file"
        accept="video/*"
        onchange={onUpload}
        disabled={uploading}
      />
    </label>
    <button class="btn" onclick={refresh} title="Liste der Videos neu vom Server laden">
      <i class="fa-solid fa-rotate"></i>
    </button>
  </PanelHeader>

  <div class="body">
    {#if files.length === 0}
      <div class="empty soft">
        <i class="fa-solid fa-film"></i>
        <p>Noch keine Dateien. Oben auf <b>Video hochladen</b> klicken, um zu starten.</p>
      </div>
    {:else}
      <div class="grid">
        {#each files as f (f.id)}
          {@const s = statusBadge(f)}
          <article class="card file">
            <button class="thumb-btn" onclick={() => f.has_proxy && openInEditor(f.id)}
                    disabled={!f.has_proxy}
                    title={f.has_proxy ? 'Im Editor öffnen' : 'Proxy noch nicht fertig'}>
              <div class="thumb">
                {#if f.has_thumb}
                  <img src={api.thumbUrl(f.id)} alt="" />
                {:else}
                  <i class="fa-solid fa-image"></i>
                {/if}
                <span class="badge {s.c}">{s.t}</span>
              </div>
            </button>
            <div class="meta">
              <div class="name" title={f.original_name}>{f.original_name}</div>
              <div class="row mono">
                <span>{fmtDur(f.duration_s)}</span>
                <span>{f.width}x{f.height}</span>
                <span>{f.video_codec ?? '-'}</span>
                <span>{fmtSize(f.size_bytes)}</span>
              </div>
              <div class="row mono subtle">
                <span>FPS {f.fps ?? '-'}</span>
                <span>KF {f.keyframe_count ?? '-'}</span>
              </div>
              <div class="actions">
                <button class="btn btn-primary" onclick={() => openInEditor(f.id)}
                        disabled={!f.has_proxy}
                        title={f.has_proxy
                          ? 'Dieses Video im Schnitt-Editor öffnen'
                          : 'Bitte warten bis die Proxy-Vorschau fertig ist'}>
                  <i class="fa-solid fa-scissors"></i> Öffnen
                </button>
                <button class="btn" onclick={() => onRename(f)}
                        title="Angezeigten Dateinamen ändern (die Datei selbst bleibt unverändert auf der Platte)">
                  <i class="fa-solid fa-pen"></i>
                </button>
                <a class="btn" href={api.fileDownloadUrl(f.id)} download
                   title="Original-Datei herunterladen (nicht die Proxy-Vorschau)">
                  <i class="fa-solid fa-download"></i>
                </a>
                <button class="btn" onclick={() => onRegenProxy(f)}
                        title="Proxy-Vorschau (480p-Streaming-Version) neu erzeugen">
                  <i class="fa-solid fa-arrows-rotate"></i>
                </button>
                <button class="btn btn-danger" onclick={() => onDelete(f)}
                        title="Dieses Video samt Vorschau, Thumbnail, Sprite und Wellenform endgültig löschen">
                  <i class="fa-solid fa-trash"></i>
                </button>
              </div>
            </div>
          </article>
        {/each}
      </div>
    {/if}
  </div>
</section>

<style>
  .panel { display: flex; flex-direction: column; height: 100%; }
  .body { padding: 16px; overflow: auto; flex: 1; }
  .empty {
    height: 100%;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    color: var(--fg-faint);
    gap: 12px;
  }
  .empty i { font-size: 42px; }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 14px;
  }
  .file { overflow: hidden; display: flex; flex-direction: column; }
  .thumb-btn {
    background: none; border: none; padding: 0; cursor: pointer;
    display: block; width: 100%;
  }
  .thumb-btn:disabled { cursor: default; opacity: 0.8; }
  .thumb {
    position: relative;
    aspect-ratio: 16 / 9;
    background: var(--bg-sink);
    display: grid; place-items: center;
    color: var(--fg-faint);
  }
  .thumb img { width: 100%; height: 100%; object-fit: cover; }
  .thumb-btn:not(:disabled):hover .thumb { outline: 2px solid var(--accent); outline-offset: -2px; }
  .badge {
    position: absolute; top: 8px; right: 8px;
    font-size: 10px; letter-spacing: 0.5px; text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 10px;
    background: var(--bg-elev);
    color: var(--fg-muted);
  }
  .badge.ok  { background: color-mix(in oklab, var(--success) 25%, var(--bg-elev)); color: var(--success); }
  .badge.run { background: color-mix(in oklab, var(--info) 25%, var(--bg-elev)); color: var(--info); }
  .badge.err { background: color-mix(in oklab, var(--danger) 25%, var(--bg-elev)); color: var(--danger); }
  .meta { padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; }
  .name {
    font-weight: 600;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .row { display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; color: var(--fg-muted); }
  .row.subtle { color: var(--fg-faint); font-size: 11px; }
  .actions { display: flex; gap: 6px; margin-top: 4px; }
  /* Die Buttons nutzen .btn/.btn-primary/.btn-danger aus app.css.
     Upload-Eingabefeld selbst ausblenden. */
  label.btn.busy { cursor: wait; filter: brightness(0.9); }
  label.btn input { display: none; }
</style>
