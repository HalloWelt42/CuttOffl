<script>
  import { onMount, onDestroy } from 'svelte';
  import PanelHeader from '../components/PanelHeader.svelte';
  import Player from '../components/Player.svelte';
  import Resizer from '../components/Resizer.svelte';
  import Timeline from '../components/Timeline.svelte';
  import ExportDialog from '../components/ExportDialog.svelte';
  import { persisted, persist } from '../lib/persist.svelte.js';
  import { nav, go } from '../lib/nav.svelte.js';
  import {
    editor, loadFile, seek, snapTime, addClipFromRange, splitAtPlayhead,
    deleteSelected, undo, redo, setSnap, setFollow, handleJobEvent, toggleClipMode,
    saveNow, jumpToPrevKeyframe, jumpToNextKeyframe,
    startRangePreview, startClipPreview, startTimelinePreview, stopPreview,
  } from '../lib/editor.svelte.js';
  import { api } from '../lib/api.js';
  import { wsOn, wsStart } from '../lib/ws.svelte.js';
  import { toast } from '../lib/toast.svelte.js';

  let playerRef;
  let inPoint = $state(null);
  let outPoint = $state(null);
  let exportOpen = $state(false);
  let exports = $state([]);
  let exportsWidth = $state(persisted('editor.exportsPanelWidth', 380));
  $effect(() => persist('editor.exportsPanelWidth', exportsWidth));

  async function refreshExports() {
    try { exports = await api.listExports(); } catch {}
  }

  async function onMountHook() {
    wsStart();
    if (nav.activeFileId) await loadFile(nav.activeFileId);
    refreshExports();
  }

  $effect(() => {
    if (nav.activeFileId && editor.fileId !== nav.activeFileId) {
      loadFile(nav.activeFileId);
    }
  });

  onMount(() => {
    onMountHook();
    const off = wsOn((msg) => {
      handleJobEvent(msg);
      if (msg.type === 'job_event' && msg.job?.kind === 'render'
          && (msg.event === 'completed' || msg.event === 'failed')) {
        refreshExports();
      }
    });
    window.addEventListener('keydown', onKey);
    return () => {
      off();
      window.removeEventListener('keydown', onKey);
    };
  });

  function onKey(e) {
    // nur wenn Editor sichtbar ist
    if (nav.view !== 'editor') return;
    const tgt = e.target;
    if (tgt && (tgt.tagName === 'INPUT' || tgt.tagName === 'TEXTAREA' ||
                tgt.tagName === 'SELECT' || tgt.isContentEditable)) return;

    switch (e.key) {
      case ' ':
        e.preventDefault();
        if (e.shiftKey) { // Shift+Leertaste = Timeline abspielen
          if (editor.preview) stopPreview(); else startTimelinePreview();
        } else {
          if (editor.preview) stopPreview();
          playerRef?.togglePlay();
        }
        break;
      case 'j':        playerRef?.nudge(-5); break;
      case 'l':        playerRef?.nudge(5); break;
      case ',':        jumpToPrevKeyframe(); break;
      case '.':        jumpToNextKeyframe(); break;
      case 'ArrowLeft':   playerRef?.stepFrame(e.shiftKey ? -10 : -1); break;
      case 'ArrowRight':  playerRef?.stepFrame(e.shiftKey ? 10 : 1); break;
      case 'i':        setIn(); break;
      case 'o':        setOut(); break;
      case 'p':        // Bereichs-Vorschau (In→Out)
        if (inPoint != null && outPoint != null) startRangePreview(inPoint, outPoint);
        else if (editor.selectedClipId) startClipPreview(editor.selectedClipId);
        break;
      case 's':        splitAtPlayhead(); break;
      case 'Backspace':
      case 'Delete':   deleteSelected(); break;
      case 'Enter':    if (inPoint != null && outPoint != null) commitInOut(); break;
      case 'Escape':   if (editor.preview) stopPreview(); break;
    }
    if ((e.metaKey || e.ctrlKey) && !e.shiftKey && e.key === 'z') {
      e.preventDefault(); undo();
    } else if ((e.metaKey || e.ctrlKey) && (e.key === 'y' || (e.shiftKey && e.key.toLowerCase() === 'z'))) {
      e.preventDefault(); redo();
    }
  }

  function snapIfOn(t) { return editor.snapOn ? snapTime(t) : t; }
  function setIn()  {
    inPoint = snapIfOn(editor.playhead);
    if (outPoint != null && outPoint <= inPoint) outPoint = null;
  }
  function setOut() {
    outPoint = snapIfOn(editor.playhead);
    if (inPoint != null && outPoint <= inPoint) inPoint = null;
  }
  function commitInOut() {
    if (inPoint == null || outPoint == null) { toast.warn('In- und Out-Punkt setzen (I/O)'); return; }
    addClipFromRange(inPoint, outPoint);
    inPoint = null; outPoint = null;
  }
  function clearMarkers() { inPoint = null; outPoint = null; }

  // Zeigt, was beim nächsten "Clip" passiert
  const nextMode = $derived(editor.snapOn ? 'copy' : 'reencode');
  const modeLabel = {
    copy:     { icon: 'fa-magnet',  text: 'keyframe-genau · verlustfrei',    cls: 'copy' },
    reencode: { icon: 'fa-recycle', text: 'frame-genau · wird neu kodiert',  cls: 'reencode' },
  };
  // Prüft, ob der aktuelle Playhead auf einem Keyframe liegt (±1 Frame)
  const onKeyframe = $derived(() => {
    if (!editor.keyframes.length) return false;
    const fps = editor.file?.fps || 25;
    const tol = 1 / fps;
    return editor.keyframes.some((k) => Math.abs(k - editor.playhead) <= tol);
  });

  async function onDownload(jobId) {
    window.location.href = api.exportDownloadUrl(jobId);
  }
  async function onDeleteExport(jobId) {
    if (!confirm('Dieses Export-Ergebnis löschen?')) return;
    try { await api.deleteExport(jobId); refreshExports(); }
    catch (e) { toast.error(e.message); }
  }

  function fmt(t) {
    if (!isFinite(t)) return '--:--.---';
    const m = Math.floor(t / 60);
    const s = t - m * 60;
    return `${m}:${s.toFixed(3).padStart(6, '0')}`;
  }

  function fmtSize(n) {
    if (!n) return '-';
    const u = ['B','KB','MB','GB']; let i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
  }

  const stats = $derived(() => {
    const tl = editor.edl?.timeline ?? [];
    const total = tl.reduce((s, c) => s + (c.src_end - c.src_start), 0);
    return { count: tl.length, total };
  });

  async function onRenameProject() {
    if (!editor.projectId) return;
    const next = prompt('Projektname:', editor.project?.name ?? '');
    if (next == null) return;
    const name = next.trim();
    if (!name || name === editor.project?.name) return;
    try {
      const updated = await api.updateProject(editor.projectId, { name });
      editor.project = updated;
      toast.success('Projekt umbenannt');
    } catch (e) { toast.error(e.message); }
  }

  async function onRenderSingleClip(clipId) {
    if (!clipId) return;
    const jobId = await startRender(clipId);
    if (jobId) toast.info('Einzel-Clip-Render gestartet');
  }

  async function onRenameFile() {
    if (!editor.fileId) return;
    const next = prompt('Dateiname:', editor.file?.original_name ?? '');
    if (next == null) return;
    const name = next.trim();
    if (!name || name === editor.file?.original_name) return;
    try {
      const updated = await api.renameFile(editor.fileId, name);
      editor.file = updated;
      toast.success('Datei umbenannt');
    } catch (e) { toast.error(e.message); }
  }
</script>

<section class="wrap">
  <PanelHeader icon="fa-scissors"
               title={editor.project?.name ?? 'Editor'}
               subtitle={editor.file?.original_name ?? 'keine Datei gewählt'}>
    {#if editor.fileId}
      <button class="btn" onclick={onRenameProject}
              title="Projektnamen ändern (wird für den Dateinamen des späteren Exports verwendet)">
        <i class="fa-solid fa-pen"></i>
        <span class="sm-hide">Projekt</span>
      </button>
      <button class="btn" onclick={onRenameFile}
              title="Dateinamen des Originals ändern">
        <i class="fa-solid fa-pen-to-square"></i>
        <span class="sm-hide">Datei</span>
      </button>
      <button class="btn" onclick={() => { saveNow(); go('library'); }}
              title="Den aktuellen Schnitt speichern und zurück zur Bibliothek">
        <i class="fa-solid fa-arrow-left"></i> Bibliothek
      </button>
      <button class="btn btn-primary" onclick={() => (exportOpen = true)}
              disabled={!stats().count || editor.rendering}
              title="Render-Dialog öffnen und fertiges Video erzeugen">
        <i class="fa-solid fa-film"></i>
        {editor.rendering ? `Rendern ${Math.round(editor.renderProgress * 100)} %` : 'Rendern'}
      </button>
    {/if}
  </PanelHeader>

  {#if !editor.fileId}
    <div class="empty soft">
      <i class="fa-solid fa-film"></i>
      <p>Noch keine Datei gewählt. In der Bibliothek auf eine Kachel klicken.</p>
      <button class="btn" onclick={() => go('library')}><i class="fa-solid fa-folder-tree"></i> Zur Bibliothek</button>
    </div>
  {:else if !editor.edl}
    <div class="empty soft">Lade Projekt...</div>
  {:else}
    <div class="main">
      <div class="top">
        <div class="player-wrap">
          <Player bind:this={playerRef} />
        </div>

        {#if exports.length}
          <Resizer bind:value={exportsWidth} min={240} max={720} side="right" />
          <aside class="exports-aside" style:width="{exportsWidth}px">
            <div class="exports-head">
              <i class="fa-solid fa-box-archive"></i>
              Fertige Videos <span class="mono dim">({exports.length})</span>
            </div>
            <ul>
              {#each exports as ex (ex.job_id)}
                <li class:disabled={!ex.exists}>
                  <div class="line1">
                    <span class="name" title={ex.display_name}>{ex.display_name}</span>
                  </div>
                  <div class="line2 mono">
                    <span class="size">{fmtSize(ex.size_bytes)}</span>
                    <span class="date dim">{ex.updated_at}</span>
                    <span class="actions">
                      <button class="btn btn-sm" onclick={() => onDownload(ex.job_id)}
                              disabled={!ex.exists} title="Dieses fertige Video herunterladen">
                        <i class="fa-solid fa-download"></i>
                      </button>
                      <button class="btn btn-sm btn-danger" onclick={() => onDeleteExport(ex.job_id)}
                              title="Dieses fertige Video endgültig löschen">
                        <i class="fa-solid fa-trash"></i>
                      </button>
                    </span>
                  </div>
                </li>
              {/each}
            </ul>
          </aside>
        {/if}
      </div>

      <div class="mode-banner {modeLabel[nextMode].cls}"
           title={editor.snapOn
             ? 'Snap an: Cuts rasten auf den nächsten Keyframe. Clip wird verlustfrei kopiert.'
             : 'Snap aus: freie Position. Clip wird beim Render neu kodiert.'}>
        <i class="fa-solid {modeLabel[nextMode].icon}"></i>
        <span class="mode-name">{nextMode}</span>
        <span class="mode-desc soft">{modeLabel[nextMode].text}</span>
        {#if onKeyframe()}
          <span class="kf-chip mono" title="Playhead liegt exakt auf einem Keyframe">
            <i class="fa-solid fa-bullseye"></i> auf KF
          </span>
        {/if}
      </div>

      <div class="toolbar">
        <div class="group">
          <button class="btn" onclick={jumpToPrevKeyframe}
                  title="Zum vorherigen Keyframe springen (Taste: Komma)">
            <i class="fa-solid fa-backward-step"></i> Keyframe ←
          </button>
          <button class="btn" onclick={jumpToNextKeyframe}
                  title="Zum nächsten Keyframe springen (Taste: Punkt)">
            Keyframe → <i class="fa-solid fa-forward-step"></i>
          </button>
        </div>

        <div class="group">
          <button class="btn" onclick={setIn}
                  title="Startpunkt (In-Punkt) der Auswahl auf die aktuelle Playhead-Position setzen (Taste I)">
            <i class="fa-solid fa-angle-right"></i> Start
            {#if inPoint != null}<span class="mono t">{fmt(inPoint)}</span>{/if}
          </button>
          <button class="btn" onclick={setOut}
                  title="Endpunkt (Out-Punkt) der Auswahl auf die aktuelle Playhead-Position setzen (Taste O)">
            <i class="fa-solid fa-angle-left"></i> Ende
            {#if outPoint != null}<span class="mono t">{fmt(outPoint)}</span>{/if}
          </button>
          <button class="btn"
                  onclick={() => startRangePreview(inPoint, outPoint)}
                  disabled={inPoint == null || outPoint == null || editor.preview}
                  title="Den gewählten Bereich (Start → Ende) einmal abspielen (Taste P)">
            <i class="fa-solid fa-play"></i> Vorschau
          </button>
          <button class="btn btn-primary" onclick={commitInOut}
                  disabled={inPoint == null || outPoint == null}
                  title="Aus Start/Ende einen Clip in die Timeline übernehmen (Eingabetaste)">
            <i class="fa-solid fa-plus"></i> Clip übernehmen
            {#if inPoint != null && outPoint != null}
              <span class="mono t">{fmt(outPoint - inPoint)}</span>
            {/if}
          </button>
          <button class="btn" onclick={clearMarkers}
                  title="Start- und End-Markierung verwerfen">
            <i class="fa-solid fa-eraser"></i>
          </button>
        </div>

        <div class="group">
          <button class="btn" onclick={() => startClipPreview(editor.selectedClipId)}
                  disabled={!editor.selectedClipId || editor.preview}
                  title="Den ausgewählten Clip einmal vom Anfang bis zum Ende abspielen">
            <i class="fa-solid fa-play"></i> Clip abspielen
          </button>
          <button class="btn" onclick={() => onRenderSingleClip(editor.selectedClipId)}
                  disabled={!editor.selectedClipId || editor.rendering}
                  title="Nur den ausgewählten Clip als eigene Videodatei exportieren">
            <i class="fa-solid fa-file-export"></i> Clip exportieren
          </button>
          <button class="btn" onclick={splitAtPlayhead}
                  title="Den Clip am Playhead in zwei Clips teilen (Taste S)">
            <i class="fa-solid fa-scissors"></i> Teilen
          </button>
          <button class="btn" onclick={deleteSelected}
                  disabled={!editor.selectedClipId}
                  title="Den ausgewählten Clip aus der Timeline entfernen (Taste Entf / Backspace)">
            <i class="fa-solid fa-trash"></i>
          </button>
          <button class="btn" onclick={() => toggleClipMode(editor.selectedClipId)}
                  disabled={!editor.selectedClipId}
                  title="Modus des ausgewählten Clips umschalten: copy (verlustfrei, keyframe-genau) ↔ reencode (frame-genau, neu kodiert)">
            <i class="fa-solid fa-arrows-rotate"></i>
            {editor.edl.timeline.find((c) => c.id === editor.selectedClipId)?.mode ?? '---'}
          </button>
        </div>

        <div class="group">
          {#if editor.preview}
            <button class="btn btn-stop" onclick={stopPreview}
                    title="Laufende Vorschau stoppen (Taste Esc)">
              <i class="fa-solid fa-stop"></i> Stopp
              {#if editor.preview.kind === 'timeline'}
                <span class="small">Clip {editor.preview.clipIndex + 1}/{editor.preview.clips.length}</span>
              {/if}
            </button>
          {:else}
            <button class="btn"
                    onclick={startTimelinePreview}
                    disabled={!stats().count}
                    title="Alle Clips der Timeline nacheinander abspielen, mit Sprung über die Lücken (Umschalt + Leertaste)">
              <i class="fa-solid fa-film"></i> Ganze Timeline abspielen
            </button>
          {/if}
        </div>

        <div class="group">
          <button class="btn" onclick={undo} disabled={!editor.history.length}
                  title="Letzte Änderung rückgängig machen (Cmd/Strg + Z)">
            <i class="fa-solid fa-rotate-left"></i>
          </button>
          <button class="btn" onclick={redo} disabled={!editor.future.length}
                  title="Rückgängig gemachte Änderung wiederherstellen (Cmd/Strg + Umschalt + Z)">
            <i class="fa-solid fa-rotate-right"></i>
          </button>
          <label class="btn-toggle" class:is-on={editor.snapOn}
                 title={editor.snapOn
                   ? 'Keyframe-Magnet ist aktiv. Die Schnittmarken (In/Out) rasten automatisch auf den naechstliegenden Keyframe ein. Der Clip wird beim Rendern verlustfrei kopiert (Modus: copy).'
                   : 'Keyframe-Magnet ist aus. Schnittmarken bleiben auf der exakten Zeitposition stehen. Der Clip wird beim Rendern neu kodiert (Modus: reencode).'}>
            <input type="checkbox" checked={editor.snapOn}
                   onchange={(e) => setSnap(e.target.checked)} />
            <i class="fa-solid fa-magnet"></i>
            Keyframe-Magnet
          </label>
          <label class="btn-toggle" class:is-on={editor.followOn}
                 title={editor.followOn
                   ? 'Timeline folgt dem Playhead: sobald der Abspielkopf in das letzte Drittel der Ansicht gelangt, wird sanft nachgescrollt.'
                   : 'Timeline folgt dem Playhead nicht. Die Ansicht bleibt fix, der Playhead kann aus dem sichtbaren Bereich laufen.'}>
            <input type="checkbox" checked={editor.followOn}
                   onchange={(e) => setFollow(e.target.checked)} />
            <i class="fa-solid fa-location-crosshairs"></i>
            Timeline folgt
          </label>
        </div>

        <div class="group right mono">
          {#if inPoint != null && outPoint != null}
            <span class="dim">Auswahl: {fmt(outPoint - inPoint)}</span>
          {/if}
          <span>Clips: {stats().count}</span>
          <span>Σ {stats().total.toFixed(2)} s</span>
          {#if editor.saving}<span class="saving">speichere...</span>
          {:else if editor.dirty}<span class="dim">ungespeichert</span>
          {:else}<span class="ok">gespeichert</span>{/if}
        </div>
      </div>

      <Timeline />

    </div>
  {/if}
</section>

<ExportDialog bind:open={exportOpen} />

<style>
  .wrap { display: flex; flex-direction: column; height: 100%; }
  .empty {
    flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 14px; color: var(--fg-muted);
  }
  .empty i { font-size: 44px; color: var(--fg-faint); }
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .top {
    flex: 1;
    display: flex;
    min-height: 0;
    min-width: 0;
  }
  .player-wrap {
    flex: 1 1 auto;
    min-height: 0;
    min-width: 0;
    display: flex;
  }
  .exports-aside {
    flex: 0 0 auto;
    min-height: 0;
    border-left: 1px solid var(--border);
    background: var(--bg-sink);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .mode-banner, .toolbar { flex: 0 0 auto; }
  .mode-banner {
    display: flex; align-items: center; gap: 10px;
    height: 30px;
    padding: 0 14px;
    background: var(--bg-elev);
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    font-size: 12px;
    overflow: hidden;
    white-space: nowrap;
  }
  .mode-banner i        { color: var(--accent); }
  .mode-banner.copy     i { color: var(--clip-copy); }
  .mode-banner.reencode i { color: var(--clip-reencode); }
  .mode-name {
    font-weight: 700; text-transform: uppercase; letter-spacing: 1px;
    font-size: 11px;
    color: var(--fg-primary);
    padding: 2px 8px;
    border-radius: 3px;
    background: var(--bg-panel);
  }
  .mode-banner.copy     .mode-name {
    background: color-mix(in oklab, var(--clip-copy) 24%, var(--bg-panel));
    color: #dff7f3;
  }
  .mode-banner.reencode .mode-name {
    background: color-mix(in oklab, var(--clip-reencode) 24%, var(--bg-panel));
    color: #e3e0ff;
  }
  .mode-desc {
    color: var(--fg-muted);
    overflow: hidden; text-overflow: ellipsis;
    flex: 1; min-width: 0;
  }
  .mode-banner .kf-chip { margin-left: auto; flex: 0 0 auto; }
  .kf-chip {
    background: var(--success);
    color: #062012;
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 600;
    line-height: 16px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }
  .toolbar {
    display: flex; flex-wrap: wrap; gap: 6px;
    padding: 6px 12px;
    background: var(--bg-panel);
    border-top: 1px solid var(--border);
    align-items: center;
    min-height: 42px;
  }
  .group { display: flex; gap: 4px; align-items: center; padding-right: 10px; border-right: 1px solid var(--border); }
  .group:last-child { border-right: none; }
  .group.right { margin-left: auto; font-size: 12px; color: var(--fg-muted); }
  /* Button-Klassen kommen global aus app.css. Hier nur noch kontext-spezifische
     Ergaenzungen (z.B. kleine Timecodes innerhalb eines Buttons). */
  .btn .t { font-size: 11px; color: var(--fg-primary); margin-left: 4px; }
  .btn .small { font-size: 10px; opacity: 0.8; padding-left: 4px; }
  .t { font-size: 11px; color: var(--fg-primary); }
  .dim { color: var(--fg-muted); }
  .ok { color: var(--success); }
  .saving { color: var(--info); }

  .exports-head {
    display: flex; align-items: center; gap: 8px;
    font-size: 11px; color: var(--fg-muted);
    padding: 10px 12px;
    letter-spacing: 1px; text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    background: var(--bg-panel);
    flex: 0 0 auto;
  }
  .exports-head i { color: var(--accent); }
  .exports-aside ul {
    list-style: none; padding: 8px; margin: 0;
    display: flex; flex-direction: column; gap: 6px;
    overflow: auto;
    flex: 1 1 auto;
  }
  .exports-aside li {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 10px;
    display: flex; flex-direction: column; gap: 4px;
    font-size: 12px;
  }
  .exports-aside li.disabled { opacity: 0.5; }
  .exports-aside .name {
    color: var(--fg-primary);
    font-weight: 500;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .exports-aside .line2 {
    display: flex; align-items: center; gap: 8px;
    color: var(--fg-muted);
    font-size: 11px;
  }
  .exports-aside .size { flex: 0 0 auto; }
  .exports-aside .date { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
  .exports-aside .actions { display: flex; gap: 4px; flex: 0 0 auto; }
</style>
