<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { wsOn, wsStart } from '../lib/ws.svelte.js';
  import { toast } from '../lib/toast.svelte.js';
  import { confirmDialog } from '../lib/dialog.svelte.js';
  import { go, openProjectInEditor } from '../lib/nav.svelte.js';
  import { openFolderPicker } from '../lib/folderPicker.svelte.js';
  import PanelHeader from '../components/PanelHeader.svelte';
  import VideoPreviewOverlay from '../components/VideoPreviewOverlay.svelte';

  let previewOpen = $state(false);
  let previewSrc = $state('');
  let previewTitle = $state('');

  function openPreview(ex) {
    if (!ex.exists) return;
    previewSrc = api.exportDownloadUrl(ex.job_id);
    previewTitle = ex.display_name;
    previewOpen = true;
  }

  let exports = $state([]);
  let loading = $state(true);

  async function refresh() {
    try {
      exports = await api.listExports();
    } catch (e) { toast.error(e.message); }
    finally { loading = false; }
  }

  onMount(() => {
    wsStart();
    refresh();
    return wsOn((m) => {
      // Re-fetch bei Render-Abschluss oder File-Ereignissen
      if (m.type === 'job_event' && m.job?.kind === 'render') refresh();
      if (m.type === 'file_event') refresh();
    });
  });

  async function onImportToLibrary(ex) {
    if (!ex.exists) return;
    const target = await openFolderPicker({
      title: 'In Bibliothek übernehmen: Zielordner wählen',
      current: '',
    });
    if (target === null) return;
    try {
      const res = await api.importExportToLibrary(ex.job_id, target);
      toast.info(`"${res.original_name}" in Bibliothek übernommen`);
    } catch (e) { toast.error(e.message); }
  }

  async function onDelete(ex) {
    const ok = await confirmDialog(
      `Gerenderte Datei "${ex.display_name}" endgültig löschen?`,
      { title: 'Fertiges Video löschen', okLabel: 'Löschen', okVariant: 'danger' },
    );
    if (!ok) return;
    try {
      await api.deleteExport(ex.job_id);
      toast.info('Export entfernt');
      refresh();
    } catch (e) { toast.error(e.message); }
  }

  function fmtSize(n) {
    if (!n) return '-';
    const u = ['B','KB','MB','GB','TB'];
    let i = 0; while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
  }

  function fmtDate(s) {
    if (!s) return '-';
    // '2026-04-17 00:32:23' -> '17.04.2026 00:32'
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
    return m ? `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}` : s;
  }

  const total = $derived(exports.reduce((sum, e) => sum + (e.size_bytes || 0), 0));
</script>

<section class="wrap">
  <PanelHeader icon="fa-box-archive" title="Fertige Videos"
               subtitle={loading ? 'Lade...' :
                         exports.length === 0 ? 'Noch keine gerenderten Schnitte' :
                         `${exports.length} Video(s) · Gesamt ${fmtSize(total)}`}>
    <button class="btn" onclick={refresh} title="Neu laden">
      <i class="fa-solid fa-rotate"></i>
    </button>
  </PanelHeader>

  <div class="body">
    {#if !loading && exports.length === 0}
      <div class="empty soft">
        <i class="fa-solid fa-box-archive"></i>
        <p>Noch keine fertigen Videos. Schneide im Editor einen oder mehrere Clips und klicke dann auf <b>Rendern</b>.</p>
        <button class="btn" onclick={() => go('library')}>
          <i class="fa-solid fa-folder-tree"></i> Zur Bibliothek
        </button>
      </div>
    {:else}
      <ul class="list">
        {#each exports as ex (ex.job_id)}
          <li class:disabled={!ex.exists}>
            <button class="left" onclick={() => openPreview(ex)}
                    disabled={!ex.exists}
                    title={ex.exists ? 'Vorschau öffnen' : 'Datei nicht vorhanden'}>
              <i class="fa-solid fa-film"></i>
              <div class="info">
                <div class="name" title={ex.display_name}>{ex.display_name}</div>
                <div class="meta mono">
                  {#if ex.project_name}<span class="project">{ex.project_name}</span>{/if}
                  <span>{fmtSize(ex.size_bytes)}</span>
                  <span class="dim">{fmtDate(ex.updated_at)}</span>
                  {#if !ex.exists}<span class="warn">Datei fehlt</span>{/if}
                </div>
              </div>
            </button>
            <div class="actions">
              <button class="btn" onclick={() => openPreview(ex)}
                      disabled={!ex.exists}
                      title="Video im Overlay abspielen">
                <i class="fa-solid fa-play"></i>
              </button>
              {#if ex.project_id}
                <button class="btn" onclick={() => openProjectInEditor(ex.project_id)}
                        title="Zurück in den Editor, um den Schnitt dieses Projekts weiter zu bearbeiten">
                  <i class="fa-solid fa-scissors"></i>
                </button>
              {/if}
              <button class="btn" onclick={() => onImportToLibrary(ex)}
                      disabled={!ex.exists}
                      title="Dieses Video als neue Quelle in die Bibliothek aufnehmen (kopiert die Datei)">
                <i class="fa-solid fa-right-to-bracket"></i>
              </button>
              {#if ex.has_transcript}
                <!-- CC-Direkt-Download: SRT (VTT-Variante als Title-Hint) -->
                <a class="btn" href={api.exportTranscriptSrtUrl(ex.job_id)} download
                   class:disabled={!ex.exists}
                   title="Nur Untertitel (SRT) für diesen Schnitt herunterladen -- mit neuer Zeitachse. Für WebVTT siehe bundle.zip.">
                  <i class="fa-solid fa-closed-captioning"></i>
                </a>
                <a class="btn btn-primary" href={api.exportBundleUrl(ex.job_id)} download
                   class:disabled={!ex.exists}
                   title="Video + Untertitel (SRT & VTT) als ZIP herunterladen -- Zeiten auf den Schnitt angepasst">
                  <i class="fa-solid fa-file-zipper"></i> Download
                </a>
              {:else}
                <a class="btn btn-primary" href={api.exportDownloadUrl(ex.job_id)} download
                   class:disabled={!ex.exists}
                   title="Dieses Video herunterladen">
                  <i class="fa-solid fa-download"></i> Download
                </a>
              {/if}
              <button class="btn btn-danger" onclick={() => onDelete(ex)}
                      title="Dieses gerenderte Video endgültig entfernen">
                <i class="fa-solid fa-trash"></i>
              </button>
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</section>

<VideoPreviewOverlay bind:open={previewOpen} src={previewSrc} title={previewTitle} />

<style>
  .wrap { display: flex; flex-direction: column; height: 100%; }
  .body { padding: 20px; overflow: auto; flex: 1; }

  .empty {
    height: 100%;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    color: var(--fg-faint);
    gap: 14px;
    text-align: center;
  }
  .empty i { font-size: 42px; }
  .empty p { max-width: 420px; line-height: 1.55; }
  .empty b { color: var(--fg-primary); }

  .list {
    list-style: none; padding: 0; margin: 0;
    display: flex; flex-direction: column; gap: 8px;
    max-width: 960px;
  }
  .list li {
    display: flex; align-items: center; gap: 16px;
    padding: 12px 14px;
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .list li.disabled { opacity: 0.55; }

  .left { display: flex; align-items: center; gap: 14px; flex: 1 1 auto; min-width: 0; }
  .left > i {
    width: 38px; height: 38px; border-radius: 8px;
    background: color-mix(in oklab, var(--accent) 18%, var(--bg-elev));
    color: var(--accent);
    display: grid; place-items: center;
    font-size: 16px;
    flex: 0 0 auto;
  }
  .info { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
  .name {
    font-weight: 600; font-size: 14px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .meta { font-size: 12px; color: var(--fg-muted); display: flex; gap: 12px; flex-wrap: wrap; }
  .meta .project {
    background: var(--bg-elev);
    padding: 1px 8px;
    border-radius: 10px;
    color: var(--fg-primary);
  }
  .meta .dim { color: var(--fg-faint); }
  .meta .warn { color: var(--danger); }

  .actions { display: flex; gap: 6px; flex: 0 0 auto; }
  .btn-primary.disabled { pointer-events: none; opacity: 0.4; }
</style>
