<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { wsOn, wsStart } from '../lib/ws.svelte.js';
  import { toast } from '../lib/toast.svelte.js';
  import { openInEditor } from '../lib/nav.svelte.js';
  import { library, setCurrentFolder, parentOf, breadcrumbs } from '../lib/library.svelte.js';
  import PanelHeader from '../components/PanelHeader.svelte';

  let files = $state([]);
  let folderChildren = $state([]);
  let uploading = $state(false);
  let uploadPct = $state(0);
  let fileInput;

  const crumbs = $derived(breadcrumbs(library.currentFolder));

  async function refresh() {
    try {
      const [f, c] = await Promise.all([
        api.listFiles(library.currentFolder),
        api.folderChildren(library.currentFolder),
      ]);
      files = f;
      folderChildren = c.children ?? [];
    } catch (e) { toast.error(e.message); }
  }

  onMount(() => {
    wsStart();
    refresh();
    return wsOn((msg) => {
      if (msg.type === 'file_event') refresh();
    });
  });

  // Reagiere auf Wechsel des aktuellen Ordners
  $effect(() => { library.currentFolder; refresh(); });

  async function onUpload(ev) {
    const file = ev.target.files?.[0];
    if (!file) return;
    uploading = true;
    uploadPct = 0;
    try {
      await api.upload(file, (p) => (uploadPct = p), library.currentFolder);
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

  async function onCreateFolder() {
    const name = prompt('Neuen Ordner anlegen -- Name:');
    if (name == null) return;
    const clean = name.trim();
    if (!clean) return;
    if (/[\/\\:]/.test(clean)) {
      toast.error('Name darf kein / \\ oder : enthalten');
      return;
    }
    // Wir legen keinen leeren Ordner an (Ordner sind virtuell); wir wechseln
    // einfach in den gewuenschten Pfad, dort koennen dann Dateien hochgeladen
    // oder verschoben werden. Der Ordner wird sichtbar, sobald eine Datei
    // darin liegt. Zur Klarheit meldet ein Toast das.
    const target = library.currentFolder
      ? `${library.currentFolder}/${clean}`
      : clean;
    setCurrentFolder(target);
    toast.info('Ordner wird sichtbar, sobald du hier etwas hochlädst oder hierher verschiebst');
  }

  async function onRenameFolder(child) {
    const next = prompt('Ordner umbenennen:', child.name);
    if (next == null) return;
    const name = next.trim();
    if (!name || name === child.name) return;
    if (/[\/\\:]/.test(name)) {
      toast.error('Name darf kein / \\ oder : enthalten');
      return;
    }
    const parent = library.currentFolder;
    const newPath = parent ? `${parent}/${name}` : name;
    try {
      await api.renameFolder(child.path, newPath);
      toast.success('Ordner umbenannt');
      refresh();
    } catch (e) { toast.error(e.message); }
  }

  async function onDeleteFolder(child) {
    if (child.total_count > 0) {
      toast.warn('Ordner ist nicht leer -- bitte zuerst Dateien verschieben oder löschen');
      return;
    }
    if (!confirm(`Leeren Ordner "${child.name}" löschen?`)) return;
    try {
      await api.deleteFolder(child.path);
      toast.info('Ordner entfernt');
      refresh();
    } catch (e) { toast.error(e.message); }
  }

  function onMoveToParent(f) {
    const target = parentOf(library.currentFolder);
    doMove(f, target);
  }

  async function doMove(f, target) {
    try {
      await api.moveFile(f.id, target);
      toast.info(target ? `Verschoben nach ${target}` : 'In die Wurzel verschoben');
      refresh();
    } catch (e) { toast.error(e.message); }
  }

  async function onMoveTo(f) {
    const target = prompt(
      'Zielordner (leer = Wurzel, sonst z. B. "Urlaub/2026"):',
      f.folder_path || '',
    );
    if (target == null) return;
    doMove(f, target.trim());
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
  <PanelHeader icon="fa-folder-tree" title="Bibliothek"
               subtitle={`${files.length} Datei(en), ${folderChildren.length} Ordner`}>
    <button class="btn" onclick={onCreateFolder}
            title="Neuen Unterordner im aktuellen Ordner anlegen">
      <i class="fa-solid fa-folder-plus"></i>
      Ordner
    </button>
    <label class="btn btn-primary" class:busy={uploading}
           title="Eine Video-Datei vom Rechner hochladen. Unterstützte Formate: MP4, MOV, MKV, WebM, AVI, M4V.">
      <i class="fa-solid fa-upload"></i>
      <span>{uploading ? `Hochladen ${Math.round(uploadPct * 100)} %` : 'Video hochladen'}</span>
      <input bind:this={fileInput} type="file" accept="video/*"
             onchange={onUpload} disabled={uploading} />
    </label>
    <button class="btn" onclick={refresh} title="Liste neu vom Server laden">
      <i class="fa-solid fa-rotate"></i>
    </button>
  </PanelHeader>

  <!-- Breadcrumb -->
  <nav class="breadcrumb" aria-label="Ordner-Navigation">
    {#each crumbs as c, i (c.path)}
      {#if i > 0}<span class="sep">/</span>{/if}
      <button class="crumb" class:current={i === crumbs.length - 1}
              onclick={() => setCurrentFolder(c.path)}
              title={i === 0 ? 'Zur Wurzel' : `Zu ${c.path}`}>
        {#if i === 0}<i class="fa-solid fa-house"></i>{/if}
        {c.label}
      </button>
    {/each}
  </nav>

  <div class="body">
    {#if folderChildren.length === 0 && files.length === 0}
      <div class="empty soft">
        <i class="fa-solid fa-film"></i>
        <p>Hier ist nichts. Lade ein Video hoch oder lege einen Ordner an.</p>
      </div>
    {:else}
      {#if folderChildren.length > 0}
        <section>
          <h3 class="sec-title">Ordner</h3>
          <div class="grid">
            {#each folderChildren as child (child.path)}
              <article class="card folder">
                <button class="folder-btn" onclick={() => setCurrentFolder(child.path)}
                        title={`${child.path} öffnen`}>
                  <div class="folder-icon">
                    <i class="fa-solid fa-folder"></i>
                  </div>
                  <div class="folder-meta">
                    <div class="name" title={child.name}>{child.name}</div>
                    <div class="row mono subtle">
                      <span>{child.total_count} Datei{child.total_count === 1 ? '' : 'en'}</span>
                    </div>
                  </div>
                </button>
                <div class="actions">
                  <button class="btn btn-sm" onclick={() => onRenameFolder(child)}
                          title="Ordner umbenennen">
                    <i class="fa-solid fa-pen"></i>
                  </button>
                  <button class="btn btn-sm btn-danger" onclick={() => onDeleteFolder(child)}
                          disabled={child.total_count > 0}
                          title={child.total_count > 0
                            ? 'Ordner enthält noch Dateien'
                            : 'Leeren Ordner löschen'}>
                    <i class="fa-solid fa-trash"></i>
                  </button>
                </div>
              </article>
            {/each}
          </div>
        </section>
      {/if}

      {#if files.length > 0}
        <section class:with-gap={folderChildren.length > 0}>
          <h3 class="sec-title">Videos</h3>
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
                            title="Angezeigten Dateinamen ändern">
                      <i class="fa-solid fa-pen"></i>
                    </button>
                    <button class="btn" onclick={() => onMoveTo(f)}
                            title="Datei in einen anderen Ordner verschieben">
                      <i class="fa-solid fa-folder-tree"></i>
                    </button>
                    <a class="btn" href={api.fileDownloadUrl(f.id)} download
                       title="Original-Datei herunterladen">
                      <i class="fa-solid fa-download"></i>
                    </a>
                    <button class="btn" onclick={() => onRegenProxy(f)}
                            title="Proxy-Vorschau neu erzeugen">
                      <i class="fa-solid fa-arrows-rotate"></i>
                    </button>
                    <button class="btn btn-danger" onclick={() => onDelete(f)}
                            title="Datei samt Vorschau, Thumbnail, Sprite und Wellenform löschen">
                      <i class="fa-solid fa-trash"></i>
                    </button>
                  </div>
                </div>
              </article>
            {/each}
          </div>
        </section>
      {/if}
    {/if}
  </div>
</section>

<style>
  .panel { display: flex; flex-direction: column; height: 100%; }
  .body { padding: 16px; overflow: auto; flex: 1; }

  .breadcrumb {
    display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
    padding: 8px 16px;
    background: var(--bg-sink);
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    color: var(--fg-muted);
  }
  .crumb {
    background: transparent; border: none; color: var(--fg-muted); cursor: pointer;
    padding: 4px 8px; border-radius: 4px;
    font: inherit; display: inline-flex; align-items: center; gap: 6px;
  }
  .crumb:hover { background: var(--bg-elev); color: var(--fg-primary); }
  .crumb.current { color: var(--fg-primary); font-weight: 600; cursor: default; }
  .crumb.current:hover { background: transparent; }
  .sep { color: var(--fg-faint); }

  .sec-title {
    margin: 0 0 10px;
    font-size: 11px; letter-spacing: 1px; text-transform: uppercase;
    color: var(--fg-muted);
  }
  section.with-gap { margin-top: 20px; }

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

  /* Ordner-Kachel */
  .folder {
    display: flex; flex-direction: column;
    overflow: hidden;
  }
  .folder-btn {
    background: transparent; border: none; padding: 14px;
    color: inherit; cursor: pointer; text-align: left;
    display: flex; gap: 12px; align-items: center;
    font: inherit;
  }
  .folder-btn:hover { background: var(--bg-elev); }
  .folder-icon {
    width: 44px; height: 44px; border-radius: 8px;
    background: color-mix(in oklab, var(--accent) 18%, var(--bg-elev));
    display: grid; place-items: center;
    color: var(--accent);
    font-size: 20px;
    flex: 0 0 auto;
  }
  .folder-meta { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
  .folder .actions {
    padding: 0 12px 12px;
    display: flex; gap: 6px; justify-content: flex-end;
  }

  /* Datei-Kachel */
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
  .actions { display: flex; gap: 6px; margin-top: 4px; flex-wrap: wrap; }

  label.btn.busy { cursor: wait; filter: brightness(0.9); }
  label.btn input { display: none; }
</style>
