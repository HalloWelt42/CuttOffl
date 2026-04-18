<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { wsOn, wsStart } from '../lib/ws.svelte.js';
  import { toast } from '../lib/toast.svelte.js';
  import { openInEditor } from '../lib/nav.svelte.js';
  import {
    library, setCurrentFolder, parentOf, breadcrumbs,
    setView, setSort, toggleSortDir, sortFiles,
    setFilter, setSearch, resetFilters, filterFiles, codecOptions, tagOptions,
    isSelected, toggleSelect, selectAll, selectOnly, clearSelection,
  } from '../lib/library.svelte.js';
  import { confirmDialog, promptDialog } from '../lib/dialog.svelte.js';
  import { openFolderPicker } from '../lib/folderPicker.svelte.js';
  import PanelHeader from '../components/PanelHeader.svelte';
  import HoverScrubThumb from '../components/HoverScrubThumb.svelte';
  import TagChips from '../components/TagChips.svelte';
  import TagEditorPopover from '../components/TagEditorPopover.svelte';

  let files = $state([]);
  let folderChildren = $state([]);
  let uploading = $state(false);
  let uploadPct = $state(0);
  let fileInput;

  // Tag-Editor (Popover): gleichzeitig nur eines geöffnet.
  let tagEditorFor = $state(null);        // file_id oder null
  let tagEditorAnchor = $state(null);     // Ankerelement
  function openTagEditor(ev, f) {
    tagEditorAnchor = ev.currentTarget;
    tagEditorFor = f.id;
  }
  function closeTagEditor() {
    tagEditorFor = null;
    tagEditorAnchor = null;
  }
  function onTagsChanged() { refresh(); }

  // Drag & Drop
  let dropActive = $state(false);         // Für das Panel-Overlay (OS-Dateien)
  let dropDepth = 0;                      // Counter für nested dragenter/leave
  let dragOverFolder = $state(null);      // Pfad des hover-Ziel-Ordners
  let dragOverUp = $state(false);         // Breadcrumb / Up-Button als Ziel
  let osDragging = $state(false);         // true, wenn OS-Datei gezogen wird
  const DT_FILE_IDS = 'application/x-cuttoffl-file-ids';

  const crumbs = $derived(breadcrumbs(library.currentFolder));
  const visibleFiles = $derived(sortFiles(filterFiles(files)));
  const availableCodecs = $derived(codecOptions(files));
  const availableTags = $derived(tagOptions(files));
  const filtersActive = $derived(
    library.filterStatus !== 'all' ||
    library.filterFormat !== 'all' ||
    library.filterRes    !== 'all' ||
    library.filterTag    !== ''    ||
    (library.search || '').trim() !== ''
  );
  const hiddenByFilter = $derived(files.length - visibleFiles.length);
  const selectedCount = $derived(library.selection.length);
  const allVisibleIds = $derived(visibleFiles.map((f) => f.id));
  const allVisibleSelected = $derived(
    allVisibleIds.length > 0 && allVisibleIds.every((id) => library.selection.includes(id))
  );

  // Sortieroptionen für das Dropdown (Label passt zur Ansicht)
  // Aktive Filter als strukturierte Liste für die Chip-Anzeige.
  // So sieht der User auf einen Blick welche Filter greifen und kann
  // sie einzeln per X entfernen.
  const activeFilters = $derived.by(() => {
    const out = [];
    if (library.search && library.search.trim()) {
      out.push({ key: 'search', label: `Suche: "${library.search.trim()}"`,
                 clear: () => setSearch('') });
    }
    if (library.filterStatus !== 'all') {
      const lbl = STATUS_OPTIONS.find((o) => o.v === library.filterStatus)?.label
                  || library.filterStatus;
      out.push({ key: 'status', label: `Status: ${lbl}`,
                 clear: () => setFilter('status', 'all') });
    }
    if (library.filterFormat !== 'all') {
      out.push({ key: 'format', label: `Codec: ${library.filterFormat}`,
                 clear: () => setFilter('format', 'all') });
    }
    if (library.filterRes !== 'all') {
      const lbl = RES_OPTIONS.find((o) => o.v === library.filterRes)?.label
                  || library.filterRes;
      out.push({ key: 'res', label: `Auflösung: ${lbl}`,
                 clear: () => setFilter('res', 'all') });
    }
    if (library.filterTag) {
      out.push({ key: 'tag', label: `Tag: ${library.filterTag}`,
                 clear: () => setFilter('tag', '') });
    }
    return out;
  });

  const SORT_OPTIONS = [
    { k: 'date',     label: 'Datum'  },
    { k: 'name',     label: 'Name'   },
    { k: 'size',     label: 'Größe'  },
    { k: 'duration', label: 'Dauer'  },
  ];
  const STATUS_OPTIONS = [
    { v: 'all',        label: 'Alle Status' },
    { v: 'ready',      label: 'Bereit' },
    { v: 'processing', label: 'Verarbeitung' },
    { v: 'failed',     label: 'Fehlgeschlagen' },
  ];
  const RES_OPTIONS = [
    { v: 'all',   label: 'Alle Auflösungen' },
    { v: 'sd',    label: 'SD (≤576p)' },
    { v: 'hd',    label: 'HD (720p)' },
    { v: 'fhd',   label: 'Full-HD (1080p)' },
    { v: 'uhd',   label: '4K UHD (2160p)' },
    { v: 'above', label: '> 4K' },
  ];

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
  $effect(() => { library.currentFolder; clearSelection(); refresh(); });

  // Wenn ein Filter ins Leere läuft (z. B. Tag-Filter auf einen Wert,
  // den nach Löschen keine Datei mehr trägt), setzen wir ihn automatisch
  // zurück -- sonst wundert sich der User, warum "1 Datei" oben steht
  // und die Liste trotzdem leer ist.
  $effect(() => {
    if (library.filterTag && !availableTags.includes(library.filterTag)) {
      const lost = library.filterTag;
      setFilter('tag', '');
      toast.info(`Tag-Filter "${lost}" aufgehoben -- keine Datei trägt diesen Tag mehr`);
    }
  });
  $effect(() => {
    if (library.filterFormat !== 'all'
        && !availableCodecs.includes(library.filterFormat)) {
      const lost = library.filterFormat;
      setFilter('format', 'all');
      toast.info(`Codec-Filter "${lost}" aufgehoben -- keine Datei mehr mit diesem Codec`);
    }
  });

  async function onUpload(ev) {
    const list = ev.target.files;
    if (!list || list.length === 0) return;
    await uploadFiles([...list]);
    if (fileInput) fileInput.value = '';
  }

  // Sequenzieller Upload -- zeigt Gesamtfortschritt, ein Toast am Ende.
  // Bei SHA-256-Konflikt fragt der Benutzer, ob trotzdem hochgeladen werden
  // soll. Die Antwort wird als "alle gleich behandeln" merkbar (applyAll),
  // damit Mehrfach-Uploads nicht nerven.
  async function uploadFiles(list) {
    if (!list.length) return;
    uploading = true;
    uploadPct = 0;
    let ok = 0, fail = 0, skipped = 0;
    let forceAll = null;  // null = immer fragen, true/false = für alle weiteren
    for (let i = 0; i < list.length; i++) {
      const file = list[i];
      const onProg = (p) => { uploadPct = (i + p) / list.length; };
      try {
        await api.upload(file, onProg, library.currentFolder);
        ok++;
      } catch (e) {
        if (e?.status === 409 && e.conflict) {
          let useForce = forceAll;
          if (useForce === null) {
            const c = e.conflict;
            const hash6 = (c.sha256 || '').slice(0, 12);
            const folderLabel = c.existing_folder
              ? `Ordner "${c.existing_folder}"` : 'Basis';
            useForce = await confirmDialog(
              `"${file.name}" ist inhaltlich identisch mit "${c.existing_name}" `
              + `im ${folderLabel} (SHA-256 ${hash6}...). `
              + `Trotzdem als zweite Kopie hochladen?`
              + (list.length > 1 ? '\nDiese Entscheidung gilt für alle weiteren Duplikate in diesem Durchgang.' : ''),
              {
                title: 'Identische Datei bereits vorhanden',
                okLabel: 'Trotzdem hochladen',
                cancelLabel: 'Überspringen',
                okVariant: 'primary',
              },
            );
            if (list.length > 1) forceAll = useForce;
          }
          if (useForce) {
            try {
              await api.upload(file, onProg, library.currentFolder, { force: true });
              ok++;
              continue;
            } catch (e2) {
              fail++;
              toast.error(`${file.name}: ${e2.message}`);
              continue;
            }
          } else {
            skipped++;
            continue;
          }
        }
        fail++;
        toast.error(`${file.name}: ${e.message}`);
      }
    }
    uploading = false;
    uploadPct = 0;
    if (ok > 0) toast.success(
      list.length === 1
        ? `${list[0].name} hochgeladen -- Proxy wird erzeugt`
        : `${ok} Datei(en) hochgeladen`,
    );
    if (skipped > 0) toast.info(`${skipped} Duplikat(e) übersprungen`);
    if (fail > 0 && ok === 0) toast.error(`${fail} Datei(en) fehlgeschlagen`);
    refresh();
  }

  async function onDelete(f) {
    const ok = await confirmDialog(
      `Datei "${f.original_name}" wirklich löschen? Originaldatei, Proxy, Thumbnail, Sprite und Wellenform werden entfernt.`,
      { title: 'Datei löschen', okLabel: 'Löschen', okVariant: 'danger' },
    );
    if (!ok) return;
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
    const next = await promptDialog(
      'Neuen Dateinamen eingeben:',
      f.original_name,
      { title: 'Datei umbenennen' },
    );
    if (next == null) return;
    const name = next.trim();
    if (!name || name === f.original_name) return;
    try {
      await api.renameFile(f.id, name);
      toast.success('Datei umbenannt');
      refresh();
    } catch (e) { toast.error(e.message); }
  }

  function onTagClick(tag) {
    setFilter('tag', tag);
  }

  async function onCreateFolder() {
    const name = await promptDialog(
      'Wie soll der neue Ordner heißen?',
      '',
      { title: 'Neuen Ordner anlegen', placeholder: 'z. B. Urlaub 2026' },
    );
    if (name == null) return;
    const clean = name.trim();
    if (!clean) return;
    if (/[\/\\:]/.test(clean)) {
      toast.error('Name darf kein / \\ oder : enthalten');
      return;
    }
    // Wir legen keinen leeren Ordner an (Ordner sind virtuell); wir wechseln
    // einfach in den gewünschten Pfad, dort können dann Dateien hochgeladen
    // oder verschoben werden. Der Ordner wird sichtbar, sobald eine Datei
    // darin liegt. Zur Klarheit meldet ein Toast das.
    const target = library.currentFolder
      ? `${library.currentFolder}/${clean}`
      : clean;
    setCurrentFolder(target);
    toast.info('Ordner wird sichtbar, sobald du hier etwas hochlädst oder hierher verschiebst');
  }

  async function onRenameFolder(child) {
    const next = await promptDialog(
      'Neuer Name für den Ordner:',
      child.name,
      { title: 'Ordner umbenennen' },
    );
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
    const ok = await confirmDialog(
      `Leeren Ordner "${child.name}" entfernen?`,
      { title: 'Ordner löschen', okLabel: 'Löschen', okVariant: 'danger' },
    );
    if (!ok) return;
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
      toast.info(target ? `Verschoben nach ${target}` : 'In die Basis verschoben');
      refresh();
    } catch (e) { toast.error(e.message); }
  }

  async function onMoveTo(f) {
    const target = await openFolderPicker({
      title: `"${f.original_name}" verschieben nach …`,
      current: f.folder_path || '',
    });
    if (target == null) return;
    if ((f.folder_path || '') === target) return;
    doMove(f, target);
  }

  // ---- Bulk-Aktionen -------------------------------------------------------
  function onToggleSelectAll() {
    if (allVisibleSelected) clearSelection();
    else selectAll(allVisibleIds);
  }

  async function onBulkMove() {
    const ids = [...library.selection];
    if (ids.length === 0) return;
    const target = await openFolderPicker({
      title: `${ids.length} Datei(en) verschieben nach …`,
      current: library.currentFolder,
    });
    if (target == null) return;
    try {
      const res = await api.bulkMoveFiles(ids, target);
      toast.success(`${res.moved} Datei(en) verschoben`);
      clearSelection();
      refresh();
    } catch (e) { toast.error(e.message); }
  }

  // ---- Drag & Drop ---------------------------------------------------------
  function hasOSFiles(e) {
    const dt = e.dataTransfer;
    if (!dt) return false;
    // Firefox: types ist DOMStringList, enthält 'Files' beim OS-Drag
    const types = dt.types ? Array.from(dt.types) : [];
    return types.includes('Files');
  }

  function hasInternalFiles(e) {
    const dt = e.dataTransfer;
    if (!dt) return false;
    const types = dt.types ? Array.from(dt.types) : [];
    return types.includes(DT_FILE_IDS);
  }

  function onPanelDragEnter(e) {
    if (!hasOSFiles(e)) return;
    e.preventDefault();
    dropDepth++;
    osDragging = true;
    dropActive = true;
  }

  function onPanelDragOver(e) {
    if (!hasOSFiles(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  }

  function onPanelDragLeave(e) {
    if (!hasOSFiles(e)) return;
    dropDepth = Math.max(0, dropDepth - 1);
    if (dropDepth === 0) {
      dropActive = false;
      osDragging = false;
    }
  }

  async function onPanelDrop(e) {
    if (!hasOSFiles(e)) return;
    e.preventDefault();
    dropActive = false;
    osDragging = false;
    dropDepth = 0;
    const osFiles = [...(e.dataTransfer.files || [])];
    if (osFiles.length === 0) return;
    // Nur Video-Endungen durchlassen
    const accept = /\.(mp4|mov|mkv|webm|avi|m4v|mts|ts|mpg|mpeg|flv|wmv)$/i;
    const good = osFiles.filter((f) => accept.test(f.name));
    const bad = osFiles.length - good.length;
    if (bad > 0) toast.warn(`${bad} Datei(en) übersprungen (kein Video-Format)`);
    if (good.length === 0) return;
    await uploadFiles(good);
  }

  // Datei-Kachel / Zeile starten Drag
  function onFileDragStart(e, f) {
    if (!e.dataTransfer) return;
    // Wenn die gezogene Datei Teil der aktuellen Auswahl ist, ziehen wir
    // die ganze Auswahl -- sonst nur dieses eine Item.
    const ids = library.selection.includes(f.id)
      ? [...library.selection]
      : [f.id];
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData(DT_FILE_IDS, JSON.stringify(ids));
    // Fallback-Text für externe Ziele
    e.dataTransfer.setData('text/plain', f.original_name);
  }

  function onFileDragEnd() {
    dragOverFolder = null;
    dragOverUp = false;
  }

  // Ordner-Kachel / Up-Button / Breadcrumb als Drop-Ziel
  function onFolderDragOver(e, targetPath) {
    if (!hasInternalFiles(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    dragOverFolder = targetPath;
  }

  function onFolderDragLeave(e, targetPath) {
    if (dragOverFolder === targetPath) dragOverFolder = null;
  }

  async function onFolderDrop(e, targetPath) {
    if (!hasInternalFiles(e)) return;
    e.preventDefault();
    e.stopPropagation();
    dragOverFolder = null;
    dragOverUp = false;
    let ids = [];
    try {
      ids = JSON.parse(e.dataTransfer.getData(DT_FILE_IDS) || '[]');
    } catch {
      ids = [];
    }
    if (!Array.isArray(ids) || ids.length === 0) return;
    // Nicht auf denselben Ordner droppen
    const tgt = targetPath === undefined ? '' : targetPath;
    try {
      const res = await api.bulkMoveFiles(ids, tgt);
      toast.success(
        res.moved === 1
          ? `Verschoben nach ${tgt || 'Basis'}`
          : `${res.moved} Datei(en) nach ${tgt || 'Basis'} verschoben`,
      );
      clearSelection();
      refresh();
    } catch (err) { toast.error(err.message); }
  }

  function onUpDragOver(e) {
    if (!hasInternalFiles(e)) return;
    if (!library.currentFolder) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    dragOverUp = true;
  }
  function onUpDragLeave() { dragOverUp = false; }
  async function onUpDrop(e) {
    if (!library.currentFolder) return;
    await onFolderDrop(e, parentOf(library.currentFolder));
  }

  async function onBulkDelete() {
    const ids = [...library.selection];
    if (ids.length === 0) return;
    const ok = await confirmDialog(
      `${ids.length} Datei(en) endgültig löschen? Alle Ableitungen (Proxy, Thumbnail, Sprite, Wellenform) werden ebenfalls entfernt.`,
      { title: 'Mehrfach-Löschung', okLabel: 'Löschen', okVariant: 'danger' },
    );
    if (!ok) return;
    try {
      const res = await api.bulkDeleteFiles(ids);
      toast.info(`${res.deleted} Datei(en) entfernt`);
      clearSelection();
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

<section class="panel" class:drop-active={dropActive}
         aria-label="Bibliothek"
         ondragenter={onPanelDragEnter}
         ondragover={onPanelDragOver}
         ondragleave={onPanelDragLeave}
         ondrop={onPanelDrop}>
  {#if dropActive}
    <div class="drop-overlay" aria-hidden="true">
      <i class="fa-solid fa-cloud-arrow-up"></i>
      <div class="drop-title">Hier loslassen zum Hochladen</div>
      <div class="drop-sub">
        Ordner: <b>{library.currentFolder || 'Basis'}</b>
      </div>
    </div>
  {/if}
  <PanelHeader icon="fa-folder-tree" title="Bibliothek"
               subtitle={library.currentFolder
                 ? `${library.currentFolder}  ·  ${files.length} Datei(en), ${folderChildren.length} Unterordner`
                 : `${files.length} Datei(en), ${folderChildren.length} Ordner`}>
    <button class="btn" onclick={onCreateFolder}
            title="Neuen Unterordner im aktuellen Ordner anlegen">
      <i class="fa-solid fa-folder-plus"></i>
      Ordner
    </button>
    <label class="btn btn-primary" class:busy={uploading}
           data-tour="lib-upload"
           title="Eine Video-Datei vom Rechner hochladen. Unterstützte Formate: MP4, MOV, MKV, WebM, AVI, M4V.">
      <i class="fa-solid fa-upload"></i>
      <span>{uploading ? `Hochladen ${Math.round(uploadPct * 100)} %` : 'Video hochladen'}</span>
      <input bind:this={fileInput} type="file" accept="video/*"
             multiple onchange={onUpload} disabled={uploading} />
    </label>
    <a class="btn" href={api.folderZipUrl(library.currentFolder, true)} download
       class:disabled={files.length === 0 && folderChildren.length === 0}
       title={library.currentFolder
         ? `Alle Dateien des Ordners "${library.currentFolder}" (und Unterordner) als ZIP herunterladen`
         : 'Gesamte Bibliothek als ZIP herunterladen'}>
      <i class="fa-solid fa-file-zipper"></i>
      <span class="sm-hide">ZIP</span>
    </a>
    <button class="btn" onclick={refresh} title="Liste neu vom Server laden">
      <i class="fa-solid fa-rotate"></i>
    </button>
  </PanelHeader>

  <!-- Toolbar: Ansicht + Sortierung -->
  <div class="toolbar">
    <div class="group view-switch" role="group" aria-label="Ansicht wählen"
         data-tour="lib-view-switch">
      <button class="seg" class:active={library.view === 'grid'}
              onclick={() => setView('grid')}
              title="Kachelansicht mit großen Vorschaubildern">
        <i class="fa-solid fa-grip"></i>
        <span class="lbl">Kacheln</span>
      </button>
      <button class="seg" class:active={library.view === 'list'}
              onclick={() => setView('list')}
              title="Tabellenansicht mit allen Details in einer Zeile">
        <i class="fa-solid fa-list"></i>
        <span class="lbl">Liste</span>
      </button>
      <button class="seg" class:active={library.view === 'compact'}
              onclick={() => setView('compact')}
              title="Dichte Ansicht für viele Dateien auf einen Blick">
        <i class="fa-solid fa-bars-staggered"></i>
        <span class="lbl">Kompakt</span>
      </button>
    </div>

    <div class="group sort-group">
      <label class="sort-label" for="lib-sort">Sortieren:</label>
      <select id="lib-sort" class="sort-select"
              value={library.sortBy}
              onchange={(e) => setSort(e.currentTarget.value, null)}
              title="Sortierreihenfolge der Dateien">
        {#each SORT_OPTIONS as o (o.k)}
          <option value={o.k}>{o.label}</option>
        {/each}
      </select>
      <button class="btn btn-sm" onclick={toggleSortDir}
              title={library.sortDir === 'asc'
                ? 'Aufsteigend -- klicken für absteigend'
                : 'Absteigend -- klicken für aufsteigend'}>
        <i class="fa-solid {library.sortDir === 'asc'
          ? 'fa-arrow-up-short-wide'
          : 'fa-arrow-down-wide-short'}"></i>
      </button>
    </div>

    <div class="group search-group" data-tour="lib-search">
      <i class="fa-solid fa-magnifying-glass search-icon"></i>
      <input type="search" class="search-input"
             placeholder="Name oder Tag suchen..."
             value={library.search}
             oninput={(e) => setSearch(e.currentTarget.value)}
             title="Durchsucht Dateinamen und Tags (Teilstring, Groß-/Kleinschreibung egal)" />
      {#if library.search}
        <button class="search-clear" onclick={() => setSearch('')}
                title="Suche zurücksetzen">
          <i class="fa-solid fa-xmark"></i>
        </button>
      {/if}
    </div>

    <div class="group filter-group">
      <select class="sort-select"
              value={library.filterStatus}
              onchange={(e) => setFilter('status', e.currentTarget.value)}
              title="Nach Proxy-Status filtern">
        {#each STATUS_OPTIONS as o (o.v)}
          <option value={o.v}>{o.label}</option>
        {/each}
      </select>
      <select class="sort-select"
              value={library.filterFormat}
              onchange={(e) => setFilter('format', e.currentTarget.value)}
              title="Nach Video-Codec filtern">
        <option value="all">Alle Codecs</option>
        {#each availableCodecs as c (c)}
          <option value={c}>{c}</option>
        {/each}
      </select>
      <select class="sort-select"
              value={library.filterRes}
              onchange={(e) => setFilter('res', e.currentTarget.value)}
              title="Nach Auflösung filtern">
        {#each RES_OPTIONS as o (o.v)}
          <option value={o.v}>{o.label}</option>
        {/each}
      </select>
      {#if availableTags.length > 0}
        <select class="sort-select"
                value={library.filterTag}
                onchange={(e) => setFilter('tag', e.currentTarget.value)}
                title="Nach Tag filtern">
          <option value="">Alle Tags</option>
          {#each availableTags as t (t)}
            <option value={t}>{t}</option>
          {/each}
        </select>
      {/if}
      {#if filtersActive}
        <button class="btn btn-sm" onclick={resetFilters}
                title="Alle Filter und die Suche zurücksetzen">
          <i class="fa-solid fa-rotate-left"></i> Zurücksetzen
        </button>
      {/if}
    </div>
  </div>

  {#if activeFilters.length > 0}
    <!-- Chip-Leiste mit den aktuell aktiven Filtern. Ein Klick auf das
         × entfernt den jeweiligen Filter gezielt. -->
    <div class="active-filters" role="status" aria-live="polite"
         data-tour="lib-filters">
      <i class="fa-solid fa-filter"></i>
      <span class="af-label">Aktive Filter:</span>
      {#each activeFilters as af (af.key)}
        <span class="af-chip">
          {af.label}
          <button class="af-x" onclick={af.clear}
                  title="Diesen Filter entfernen">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </span>
      {/each}
    </div>
  {/if}

  {#if selectedCount > 0}
    <div class="bulk-bar" role="toolbar" aria-label="Mehrfachauswahl"
         data-tour="lib-bulk-bar">
      <div class="bulk-info">
        <i class="fa-solid fa-square-check"></i>
        <strong>{selectedCount}</strong> Datei(en) ausgewählt
      </div>
      <div class="bulk-actions">
        <button class="btn btn-sm" onclick={onToggleSelectAll}
                title={allVisibleSelected
                  ? 'Auswahl der sichtbaren Dateien entfernen'
                  : 'Alle sichtbaren Dateien auswählen'}>
          <i class="fa-solid {allVisibleSelected ? 'fa-square' : 'fa-square-check'}"></i>
          {allVisibleSelected ? 'Keine sichtbaren' : 'Alle sichtbaren'}
        </button>
        <button class="btn btn-sm" onclick={clearSelection}
                title="Auswahl komplett aufheben">
          <i class="fa-solid fa-xmark"></i> Auswahl aufheben
        </button>
        <button class="btn btn-sm" onclick={onBulkMove}
                title="Ausgewählte Dateien in einen anderen Ordner verschieben">
          <i class="fa-solid fa-folder-tree"></i> Verschieben
        </button>
        <button class="btn btn-sm btn-danger" onclick={onBulkDelete}
                title="Ausgewählte Dateien löschen (inkl. Proxy, Thumbnail usw.)">
          <i class="fa-solid fa-trash"></i> Löschen
        </button>
      </div>
    </div>
  {/if}

  <!-- Breadcrumb -->
  <nav class="breadcrumb" aria-label="Ordner-Navigation" data-tour="lib-folders">
    {#if library.currentFolder}
      <button class="up" class:drop-target={dragOverUp}
              onclick={() => setCurrentFolder(parentOf(library.currentFolder))}
              ondragover={onUpDragOver}
              ondragleave={onUpDragLeave}
              ondrop={onUpDrop}
              title="Eine Ebene höher (Drop zum Verschieben)">
        <i class="fa-solid fa-arrow-up"></i>
      </button>
    {/if}
    {#each crumbs as c, i (c.path)}
      {#if i > 0}<span class="sep">/</span>{/if}
      <button class="crumb" class:current={i === crumbs.length - 1}
              class:drop-target={dragOverFolder === c.path}
              onclick={() => setCurrentFolder(c.path)}
              ondragover={(e) => onFolderDragOver(e, c.path)}
              ondragleave={(e) => onFolderDragLeave(e, c.path)}
              ondrop={(e) => onFolderDrop(e, c.path)}
              title={i === 0 ? 'Zur Basis (oberste Ebene)' : `Zu ${c.path}`}>
        {#if i === 0}<i class="fa-solid fa-house"></i>{/if}
        {c.label}
      </button>
    {/each}
  </nav>

  <div class="body">
    {#if folderChildren.length === 0 && files.length === 0}
      <div class="empty soft">
        <i class="fa-solid fa-folder-open"></i>
        {#if library.currentFolder}
          <p>Der Ordner <b>{library.currentFolder}</b> ist leer.</p>
          <p>Lade hier ein Video hoch, lege einen Unterordner an, oder gehe zurück.</p>
          <div class="empty-actions">
            <button class="btn" onclick={() => setCurrentFolder(parentOf(library.currentFolder))}>
              <i class="fa-solid fa-arrow-up"></i> Eine Ebene höher
            </button>
            <button class="btn" onclick={() => setCurrentFolder('')}>
              <i class="fa-solid fa-house"></i> Zur Basis
            </button>
          </div>
        {:else}
          <p>Hier ist nichts. Lade ein Video hoch oder lege einen Ordner an.</p>
        {/if}
      </div>
    {:else}
      {#if folderChildren.length > 0}
        <section>
          <h3 class="sec-title">Ordner</h3>
          <div class="grid">
            {#each folderChildren as child (child.path)}
              <article class="card folder"
                       class:drop-target={dragOverFolder === child.path}
                       ondragover={(e) => onFolderDragOver(e, child.path)}
                       ondragleave={(e) => onFolderDragLeave(e, child.path)}
                       ondrop={(e) => onFolderDrop(e, child.path)}>
                <button class="folder-btn" onclick={() => setCurrentFolder(child.path)}
                        title={`In den Ordner "${child.path}" wechseln (Drop zum Verschieben)`}>
                  <div class="folder-icon">
                    <i class="fa-solid fa-folder"></i>
                  </div>
                  <div class="folder-meta">
                    <div class="name" title={child.name}>{child.name}</div>
                    <div class="row mono subtle">
                      <span>{child.total_count} Datei{child.total_count === 1 ? '' : 'en'}</span>
                    </div>
                  </div>
                  <i class="fa-solid fa-chevron-right chev"></i>
                </button>
                <div class="actions">
                  <a class="btn btn-sm" href={api.folderZipUrl(child.path, true)} download
                     class:disabled={child.total_count === 0}
                     title={child.total_count > 0
                       ? `Inhalt als ZIP herunterladen (${child.total_count} Datei(en))`
                       : 'Ordner ist leer'}>
                    <i class="fa-solid fa-file-zipper"></i>
                  </a>
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
          <div class="sec-head">
            <h3 class="sec-title">Videos</h3>
            {#if filtersActive && hiddenByFilter > 0}
              <span class="filter-info">
                {visibleFiles.length} von {files.length} sichtbar
                ({hiddenByFilter} durch Filter ausgeblendet)
              </span>
            {/if}
          </div>
          {#if visibleFiles.length === 0}
            <div class="empty-small soft">
              <i class="fa-solid fa-filter-circle-xmark"></i>
              <p>Keine Datei passt zu Suche und Filtern.</p>
              <button class="btn btn-sm" onclick={resetFilters}>
                <i class="fa-solid fa-rotate-left"></i> Zurücksetzen
              </button>
            </div>
          {/if}

          {#if library.view === 'grid'}
            <div class="grid">
              {#each visibleFiles as f, i (f.id)}
                {@const s = statusBadge(f)}
                <article class="card file" class:selected={isSelected(f.id)}
                         data-tour-first-tile={i === 0 ? 'true' : null}
                         draggable="true"
                         ondragstart={(e) => onFileDragStart(e, f)}
                         ondragend={onFileDragEnd}>
                  <label class="sel-corner" title="Für Mehrfachaktionen auswählen">
                    <input type="checkbox"
                           checked={isSelected(f.id)}
                           onchange={() => toggleSelect(f.id)}
                           aria-label="Datei auswählen" />
                  </label>
                  <button class="thumb-btn" onclick={() => f.has_proxy && openInEditor(f.id)}
                          disabled={!f.has_proxy}
                          title={f.has_proxy ? 'Im Editor öffnen' : 'Proxy noch nicht fertig'}>
                    <div class="thumb">
                      <HoverScrubThumb
                        fileId={f.id}
                        alt={f.original_name}
                        hasThumb={f.has_thumb}
                        hasSprite={f.has_sprite}
                      />
                      <span class="badge {s.c}">{s.t}</span>
                    </div>
                  </button>
                  <div class="meta">
                    <div class="name" title={f.original_name}>{f.original_name}</div>
                    {#if f.tags && f.tags.length > 0}
                      <TagChips tags={f.tags} maxShown={4} onClick={onTagClick} />
                    {/if}
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
                              data-tour="lib-file-open"
                              title={f.has_proxy
                                ? 'Dieses Video im Schnitt-Editor öffnen'
                                : 'Bitte warten bis die Proxy-Vorschau fertig ist'}>
                        <i class="fa-solid fa-scissors"></i> Öffnen
                      </button>
                      <button class="btn" onclick={() => onRename(f)}
                              title="Angezeigten Dateinamen ändern">
                        <i class="fa-solid fa-pen"></i>
                      </button>
                      <button class="btn" onclick={(e) => openTagEditor(e, f)}
                              title="Tags dieser Datei bearbeiten">
                        <i class="fa-solid fa-tag"></i>
                      </button>
                      <button class="btn" onclick={() => onMoveTo(f)}
                              title="In einen anderen Ordner verschieben">
                        <i class="fa-solid fa-folder-tree"></i>
                        <span class="sm-hide">Verschieben</span>
                      </button>
                      <a class="btn" href={api.fileDownloadUrl(f.id)} download
                         title="Nur das Video herunterladen">
                        <i class="fa-solid fa-download"></i>
                      </a>
                      {#if f.has_transcript}
                        <a class="btn" href={api.transcriptSrtUrl(f.id)} download
                           title="Nur Untertitel als SRT herunterladen (für WebVTT siehe Editor-Panel)">
                          <i class="fa-solid fa-closed-captioning"></i>
                        </a>
                        <a class="btn" href={api.fileBundleUrl(f.id)} download
                           title="Video + Untertitel (SRT & VTT) als ZIP herunterladen">
                          <i class="fa-solid fa-file-zipper"></i>
                        </a>
                      {/if}
                      <button class="btn" onclick={() => onRegenProxy(f)}
                              title="Proxy-Vorschau neu erzeugen">
                        <i class="fa-solid fa-arrows-rotate"></i>
                      </button>
                      {#if f.protected}
                        <button class="btn btn-locked" disabled
                                title="Dieses Video ist geschützt (Demo). Löschung oder Neu-Laden nur in Einstellungen → Zurücksetzen.">
                          <i class="fa-solid fa-lock"></i>
                        </button>
                      {:else}
                        <button class="btn btn-danger" onclick={() => onDelete(f)}
                                title="Datei samt Vorschau, Thumbnail, Sprite und Wellenform löschen">
                          <i class="fa-solid fa-trash"></i>
                        </button>
                      {/if}
                    </div>
                  </div>
                </article>
              {/each}
            </div>

          {:else if library.view === 'list'}
            <div class="table-wrap">
              <table class="file-table">
                <thead>
                  <tr>
                    <th class="c-sel">
                      <input type="checkbox"
                             checked={allVisibleSelected}
                             onchange={onToggleSelectAll}
                             aria-label="Alle sichtbaren auswählen" />
                    </th>
                    <th class="c-thumb"></th>
                    <th class="c-name">Name</th>
                    <th class="c-dur mono">Dauer</th>
                    <th class="c-res mono">Auflösung</th>
                    <th class="c-codec mono">Codec</th>
                    <th class="c-size mono">Größe</th>
                    <th class="c-status">Proxy</th>
                    <th class="c-actions"></th>
                  </tr>
                </thead>
                <tbody>
                  {#each visibleFiles as f (f.id)}
                    {@const s = statusBadge(f)}
                    <tr class:selected={isSelected(f.id)}
                        draggable="true"
                        ondragstart={(e) => onFileDragStart(e, f)}
                        ondragend={onFileDragEnd}>
                      <td class="c-sel">
                        <input type="checkbox"
                               checked={isSelected(f.id)}
                               onchange={() => toggleSelect(f.id)}
                               aria-label="Datei auswählen" />
                      </td>
                      <td class="c-thumb">
                        <button class="thumb-mini" onclick={() => f.has_proxy && openInEditor(f.id)}
                                disabled={!f.has_proxy}
                                title={f.has_proxy ? 'Im Editor öffnen' : 'Proxy noch nicht fertig'}>
                          {#if f.has_thumb}
                            <img src={api.thumbUrl(f.id)} alt="" />
                          {:else}
                            <i class="fa-solid fa-image"></i>
                          {/if}
                        </button>
                      </td>
                      <td class="c-name">
                        <div class="name-cell" title={f.original_name}>{f.original_name}</div>
                        {#if f.tags && f.tags.length > 0}
                          <div class="name-tags">
                            <TagChips tags={f.tags} maxShown={5} onClick={onTagClick} />
                          </div>
                        {/if}
                      </td>
                      <td class="c-dur mono">{fmtDur(f.duration_s)}</td>
                      <td class="c-res mono">{f.width}x{f.height}</td>
                      <td class="c-codec mono">{f.video_codec ?? '-'}</td>
                      <td class="c-size mono">{fmtSize(f.size_bytes)}</td>
                      <td class="c-status"><span class="badge {s.c}">{s.t}</span></td>
                      <td class="c-actions">
                        <button class="btn btn-sm btn-primary" onclick={() => openInEditor(f.id)}
                                disabled={!f.has_proxy} title="Im Editor öffnen">
                          <i class="fa-solid fa-scissors"></i>
                        </button>
                        <button class="btn btn-sm" onclick={() => onRename(f)}
                                title="Umbenennen">
                          <i class="fa-solid fa-pen"></i>
                        </button>
                        <button class="btn btn-sm" onclick={(e) => openTagEditor(e, f)}
                                title="Tags bearbeiten">
                          <i class="fa-solid fa-tag"></i>
                        </button>
                        <button class="btn btn-sm" onclick={() => onMoveTo(f)}
                                title="Verschieben">
                          <i class="fa-solid fa-folder-tree"></i>
                        </button>
                        <a class="btn btn-sm" href={api.fileDownloadUrl(f.id)} download
                           title="Nur Video herunterladen">
                          <i class="fa-solid fa-download"></i>
                        </a>
                        {#if f.has_transcript}
                          <a class="btn btn-sm" href={api.transcriptSrtUrl(f.id)} download
                             title="Nur Untertitel (SRT)">
                            <i class="fa-solid fa-closed-captioning"></i>
                          </a>
                          <a class="btn btn-sm" href={api.fileBundleUrl(f.id)} download
                             title="Video + Untertitel als ZIP">
                            <i class="fa-solid fa-file-zipper"></i>
                          </a>
                        {/if}
                        {#if f.protected}
                          <button class="btn btn-sm btn-locked" disabled
                                  title="Geschütztes Demo-Video. Entfernen nur in Einstellungen → Zurücksetzen.">
                            <i class="fa-solid fa-lock"></i>
                          </button>
                        {:else}
                          <button class="btn btn-sm btn-danger" onclick={() => onDelete(f)}
                                  title="Löschen">
                            <i class="fa-solid fa-trash"></i>
                          </button>
                        {/if}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>

          {:else}
            <ul class="compact-list">
              {#each visibleFiles as f (f.id)}
                {@const s = statusBadge(f)}
                <li class="compact-row" class:selected={isSelected(f.id)}
                    draggable="true"
                    ondragstart={(e) => onFileDragStart(e, f)}
                    ondragend={onFileDragEnd}>
                  <label class="compact-sel" title="Für Mehrfachaktionen auswählen">
                    <input type="checkbox"
                           checked={isSelected(f.id)}
                           onchange={() => toggleSelect(f.id)}
                           aria-label="Datei auswählen" />
                  </label>
                  <button class="compact-main" onclick={() => f.has_proxy && openInEditor(f.id)}
                          disabled={!f.has_proxy}
                          title={f.has_proxy ? 'Im Editor öffnen' : 'Proxy noch nicht fertig'}>
                    <i class="fa-solid fa-film"></i>
                    <span class="compact-name" title={f.original_name}>{f.original_name}</span>
                    <span class="compact-meta mono">
                      {fmtDur(f.duration_s)} · {f.width}x{f.height} · {fmtSize(f.size_bytes)}
                    </span>
                    <span class="badge {s.c}">{s.t}</span>
                  </button>
                  {#if f.tags && f.tags.length > 0}
                    <TagChips tags={f.tags} maxShown={3} onClick={onTagClick} />
                  {/if}
                  <div class="compact-actions">
                    <button class="btn btn-sm" onclick={() => onRename(f)} title="Umbenennen">
                      <i class="fa-solid fa-pen"></i>
                    </button>
                    <button class="btn btn-sm" onclick={(e) => openTagEditor(e, f)} title="Tags bearbeiten">
                      <i class="fa-solid fa-tag"></i>
                    </button>
                    <button class="btn btn-sm" onclick={() => onMoveTo(f)} title="Verschieben">
                      <i class="fa-solid fa-folder-tree"></i>
                    </button>
                    {#if f.protected}
                      <button class="btn btn-sm btn-locked" disabled
                              title="Geschütztes Demo-Video. Entfernen nur in Einstellungen → Zurücksetzen.">
                        <i class="fa-solid fa-lock"></i>
                      </button>
                    {:else}
                      <button class="btn btn-sm btn-danger" onclick={() => onDelete(f)} title="Löschen">
                        <i class="fa-solid fa-trash"></i>
                      </button>
                    {/if}
                  </div>
                </li>
              {/each}
            </ul>
          {/if}
        </section>
      {/if}
    {/if}
  </div>
</section>

{#if tagEditorFor}
  {@const current = files.find((f) => f.id === tagEditorFor)}
  {#if current}
    <TagEditorPopover
      fileId={current.id}
      initialTags={current.tags || []}
      suggestions={availableTags}
      anchor={tagEditorAnchor}
      onClose={closeTagEditor}
      onChange={onTagsChanged}
    />
  {/if}
{/if}

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
  .up {
    background: var(--bg-elev); border: 1px solid var(--border);
    color: var(--fg-muted); cursor: pointer;
    padding: 4px 10px; border-radius: 4px; margin-right: 4px;
    display: inline-flex; align-items: center; gap: 6px;
    font: inherit; font-size: 13px;
  }
  .up:hover { color: var(--fg-primary); border-color: var(--border-strong); }

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
    transition: border-color 120ms, transform 120ms;
  }
  .folder:hover { border-color: var(--accent); transform: translateY(-1px); }
  .folder-btn {
    background: transparent; border: none; padding: 14px;
    color: inherit; cursor: pointer; text-align: left;
    display: flex; gap: 12px; align-items: center;
    font: inherit;
    width: 100%;
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
  .folder-btn .chev {
    color: var(--fg-faint);
    font-size: 14px;
    transition: transform 120ms, color 120ms;
  }
  .folder-btn:hover .chev { color: var(--accent); transform: translateX(2px); }
  .folder .actions {
    padding: 0 12px 12px;
    display: flex; gap: 6px; justify-content: flex-end;
  }

  .empty-actions { display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; justify-content: center; }
  .empty b { color: var(--fg-primary); }

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

  /* Toolbar unter dem PanelHeader: Ansicht + Sortierung */
  .toolbar {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 16px;
    background: var(--bg-panel);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }
  .toolbar .group { display: flex; align-items: center; gap: 6px; }

  .view-switch {
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 2px;
    gap: 0;
  }
  .view-switch .seg {
    background: transparent;
    border: none;
    color: var(--fg-muted);
    padding: 5px 10px;
    cursor: pointer;
    font: inherit;
    font-size: 12px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: background 120ms, color 120ms;
  }
  .view-switch .seg:hover { color: var(--fg-primary); }
  .view-switch .seg.active {
    background: var(--bg-panel);
    color: var(--accent);
    box-shadow: 0 1px 2px rgba(0,0,0,0.15);
  }
  .view-switch .seg .lbl { font-size: 12px; }

  .sort-label {
    font-size: 12px;
    color: var(--fg-muted);
    letter-spacing: 0.3px;
  }
  .sort-select {
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 4px 8px;
    font: inherit;
    font-size: 12px;
    cursor: pointer;
  }
  .sort-select:focus {
    outline: none;
    border-color: var(--accent);
  }

  /* Such-Feld */
  .search-group {
    position: relative;
    flex: 1 1 220px;
    min-width: 180px;
    max-width: 360px;
  }
  .search-icon {
    position: absolute;
    left: 10px; top: 50%;
    transform: translateY(-50%);
    color: var(--fg-faint);
    font-size: 12px;
    pointer-events: none;
  }
  .search-input {
    width: 100%;
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 28px 6px 30px;
    font: inherit;
    font-size: 13px;
  }
  .search-input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-soft);
  }
  .search-clear {
    position: absolute;
    right: 6px; top: 50%;
    transform: translateY(-50%);
    background: transparent;
    border: none;
    color: var(--fg-muted);
    cursor: pointer;
    padding: 4px 6px;
    border-radius: 4px;
    font: inherit;
  }
  .search-clear:hover { color: var(--fg-primary); background: var(--bg-panel); }

  .filter-group { flex-wrap: wrap; }

  /* Aktive-Filter-Leiste -- zeigt alle derzeit wirksamen Filter als
     Chips. Jeder Chip hat ein x zum gezielten Entfernen. */
  .active-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    padding: 8px 16px;
    background: var(--accent-soft);
    border-bottom: 1px solid color-mix(in oklab, var(--accent) 40%, var(--border));
    font-size: 13px;
  }
  .active-filters > i { color: var(--accent); }
  .af-label {
    color: var(--fg-muted);
    font-weight: 500;
    margin-right: 2px;
  }
  .af-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 4px 3px 10px;
    background: var(--bg-panel);
    border: 1px solid var(--accent);
    color: var(--fg-primary);
    border-radius: 14px;
    font-size: 12px;
    font-weight: 500;
  }
  .af-x {
    background: transparent;
    border: none;
    color: var(--fg-muted);
    cursor: pointer;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-size: 11px;
  }
  .af-x:hover { color: var(--accent); background: var(--accent-soft); }

  /* Sektion-Kopf mit Filterinfo */
  .sec-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    margin: 0 0 10px;
  }
  .sec-head .sec-title { margin: 0; }
  .filter-info {
    font-size: 11px;
    color: var(--fg-faint);
    letter-spacing: 0.2px;
  }

  .empty-small {
    padding: 40px 20px;
    text-align: center;
    color: var(--fg-faint);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    background: var(--bg-panel);
    border: 1px dashed var(--border);
    border-radius: 8px;
  }
  .empty-small i { font-size: 28px; }

  /* Liste-Ansicht: Tabelle */
  .table-wrap {
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-panel);
  }
  .file-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  .file-table thead th {
    background: var(--bg-elev);
    color: var(--fg-muted);
    text-align: left;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  .file-table tbody td {
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
  }
  .file-table tbody tr:last-child td { border-bottom: none; }
  .file-table tbody tr:hover { background: var(--bg-elev); }

  .c-thumb { width: 80px; }
  .c-dur, .c-res, .c-codec, .c-size { white-space: nowrap; }
  .c-size { text-align: right; }
  .c-status { width: 80px; }
  .c-actions { text-align: right; white-space: nowrap; }
  .c-actions .btn { margin-left: 2px; }

  .thumb-mini {
    width: 64px; height: 40px;
    background: var(--bg-sink);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0;
    overflow: hidden;
    cursor: pointer;
    display: grid; place-items: center;
    color: var(--fg-faint);
  }
  .thumb-mini:disabled { cursor: default; opacity: 0.7; }
  .thumb-mini img { width: 100%; height: 100%; object-fit: cover; }
  .thumb-mini:not(:disabled):hover { outline: 2px solid var(--accent); outline-offset: -2px; }

  .name-cell {
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 360px;
  }
  .name-tags { margin-top: 4px; }

  /* Kompakt-Ansicht */
  .compact-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }
  .compact-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0;
    border-bottom: 1px solid var(--border);
  }
  .compact-row:last-child { border-bottom: none; }
  .compact-row:hover { background: var(--bg-elev); }

  .compact-main {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 10px;
    background: transparent;
    border: none;
    color: var(--fg-primary);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .compact-main:disabled { cursor: default; opacity: 0.7; }
  .compact-main > i {
    color: var(--accent);
    width: 18px;
    text-align: center;
  }
  .compact-name {
    flex: 1 1 auto;
    min-width: 0;
    font-weight: 600;
    font-size: 13px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .compact-meta {
    font-size: 11px;
    color: var(--fg-muted);
    flex: 0 0 auto;
    white-space: nowrap;
  }
  .compact-actions {
    display: flex;
    gap: 4px;
    padding: 4px 8px;
    flex: 0 0 auto;
  }

  /* Bulk-Aktionsleiste */
  .bulk-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    padding: 8px 16px;
    background: color-mix(in oklab, var(--accent) 18%, var(--bg-panel));
    border-bottom: 1px solid var(--accent);
    flex-wrap: wrap;
  }
  .bulk-info {
    display: inline-flex; align-items: center; gap: 8px;
    color: var(--fg-primary);
    font-size: 13px;
  }
  .bulk-info i { color: var(--accent); }
  .bulk-info strong { font-weight: 700; color: var(--accent); }
  .bulk-actions { display: flex; gap: 6px; flex-wrap: wrap; }

  /* Auswahl-Checkbox auf der Grid-Kachel */
  .file { position: relative; }
  .file.selected { outline: 2px solid var(--accent); outline-offset: -1px; }
  .sel-corner {
    position: absolute;
    top: 6px; left: 6px;
    z-index: 2;
    background: rgba(0,0,0,0.55);
    padding: 4px 6px;
    border-radius: 4px;
    line-height: 0;
    cursor: pointer;
    backdrop-filter: blur(2px);
  }
  .sel-corner input {
    width: 16px; height: 16px;
    cursor: pointer;
    accent-color: var(--accent);
    margin: 0;
  }

  /* Auswahl-Spalte in der Tabelle */
  .c-sel { width: 36px; text-align: center; }
  .c-sel input { accent-color: var(--accent); cursor: pointer; }
  .file-table tbody tr.selected { background: var(--accent-soft); }

  /* Auswahl in der kompakten Liste */
  .compact-sel {
    flex: 0 0 auto;
    padding: 0 8px 0 12px;
    display: grid; place-items: center;
    cursor: pointer;
  }
  .compact-sel input { accent-color: var(--accent); cursor: pointer; margin: 0; }
  .compact-row.selected { background: var(--accent-soft); }

  /* Drag & Drop -- OS-Dateien auf das Panel */
  .panel { position: relative; }
  .drop-overlay {
    position: absolute;
    inset: 0;
    z-index: 50;
    background: color-mix(in oklab, var(--accent) 22%, rgba(0,0,0,0.55));
    border: 3px dashed var(--accent);
    border-radius: 8px;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    color: var(--fg-primary);
    pointer-events: none;
    backdrop-filter: blur(2px);
    gap: 12px;
    padding: 20px;
    text-align: center;
  }
  .drop-overlay i {
    font-size: 56px;
    color: var(--accent);
  }
  .drop-overlay .drop-title {
    font-size: 20px; font-weight: 700;
  }
  .drop-overlay .drop-sub {
    font-size: 13px; color: var(--fg-muted);
  }
  .drop-overlay b { color: var(--accent); }

  /* Drop-Ziel-Hervorhebung */
  .folder.drop-target {
    outline: 2px dashed var(--accent);
    outline-offset: -2px;
    background: var(--accent-soft);
    transform: scale(1.02);
    transition: transform 120ms;
  }
  .up.drop-target,
  .crumb.drop-target {
    background: var(--accent-soft);
    border-color: var(--accent);
    color: var(--accent);
    outline: 1px dashed var(--accent);
    outline-offset: 2px;
  }

  /* Cursor-Hinweis auf draggable Items */
  .file[draggable="true"] { cursor: grab; }
  .file[draggable="true"]:active { cursor: grabbing; }
  .compact-row[draggable="true"] { cursor: grab; }
  .file-table tbody tr[draggable="true"] { cursor: grab; }
</style>
