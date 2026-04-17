<script>
  // Transkript-Panel im Editor. Zeigt Segmente aus der SRT-Datei und
  // synchronisiert mit dem Playhead:
  // - Klick auf ein Segment springt an dessen Start
  // - Das gerade aktive Segment wird hervorgehoben und bei aktivem
  //   Auto-Follow in den sichtbaren Bereich gescrollt
  // - Suche filtert die Segmente nach Teilstring
  // - Download-Knopf lädt die SRT direkt
  //
  // Wenn noch kein Transkript vorhanden ist, zeigt das Panel einen
  // "Transkribieren"-Knopf an, der den Job über startTranscribe startet.
  // Wenn die Transkription läuft, kommt eine Progress-Zeile.

  import { api } from '../lib/api.js';
  import {
    editor, seek, startTranscribe, cancelTranscribe, activeSegmentAt,
    toggleTranscriptFollow,
  } from '../lib/editor.svelte.js';
  import { toast } from '../lib/toast.svelte.js';
  import { confirmDialog } from '../lib/dialog.svelte.js';

  let query = $state('');
  // svelte-ignore non_reactive_update
  let listEl;
  let capsStatus = $state(null);

  const t = $derived(editor.transcript);
  // Live-Segmente haben Vorrang, solange die Transkription laeuft --
  // sobald sie fertig ist, uebernimmt die endgueltige SRT-Liste.
  const segments = $derived(
    editor.transcribing && editor.liveSegments.length > 0
      ? editor.liveSegments
      : (t?.segments || [])
  );
  const filtered = $derived.by(() => {
    const q = query.trim().toLocaleLowerCase('de');
    if (!q) return segments;
    return segments.filter((s) => (s.text || '').toLocaleLowerCase('de').includes(q));
  });
  const active = $derived(activeSegmentAt(editor.playhead, segments));

  function fmtTs(s) {
    if (s == null) return '-';
    const ms = Math.floor((s % 1) * 1000);
    s = Math.floor(s);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return (h > 0 ? `${h}:${String(m).padStart(2,'0')}` : `${m}`)
           + `:${String(sec).padStart(2,'0')}`;
  }

  // Aktives Segment in den Sichtbereich scrollen. Eigener Follow-
  // Schalter (transcriptFollowOn) -- unabhaengig vom Timeline-Follow.
  // Wir nutzen data-idx als stabilen Schluessel (Float-Vergleich in
  // data-Attributen ist unzuverlaessig).
  let userScrolledAt = 0;
  function onUserScroll() { userScrolledAt = Date.now(); }

  $effect(() => {
    if (!editor.transcriptFollowOn || !listEl || !active) return;
    // Nach manuellem Scroll 1,5 s Pause, damit der User nicht staendig
    // wieder an die aktuelle Stelle gerissen wird.
    if (Date.now() - userScrolledAt < 1500) return;
    const idx = segments.indexOf(active);
    if (idx < 0) return;
    const el = listEl.querySelector(`[data-idx="${idx}"]`);
    if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  });

  async function checkCapabilities() {
    try { capsStatus = await api.transcriptionStatus(); }
    catch { capsStatus = null; }
  }

  async function onStart() {
    if (!editor.fileId) return;
    await checkCapabilities();
    if (!capsStatus?.available) {
      toast.error('Transkription ist nicht eingerichtet. Siehe Einstellungen.');
      return;
    }
    startTranscribe(editor.fileId);
  }

  async function onDelete() {
    if (!editor.fileId) return;
    const ok = await confirmDialog(
      'Transkript endgültig löschen? Das Video selbst bleibt unverändert.',
      { title: 'Transkript löschen', okLabel: 'Löschen', okVariant: 'danger' },
    );
    if (!ok) return;
    try {
      await api.deleteTranscript(editor.fileId);
      editor.transcript = { has_transcript: false, segments: [], language: null, model: null };
      toast.info('Transkript entfernt');
    } catch (e) { toast.error(e.message); }
  }
</script>

<div class="tp">
  <div class="tp-head">
    <i class="fa-solid fa-closed-captioning"></i>
    <span class="title">Transkript</span>
    {#if t?.has_transcript}
      <span class="meta mono">
        {segments.length} Segmente
        {#if t.language} · {t.language}{/if}
      </span>
    {/if}
  </div>

  {#if editor.transcribing}
    <div class="banner">
      <i class="fa-solid fa-spinner fa-spin"></i>
      <span class="banner-text">
        Transkription läuft... {Math.round((editor.transcribePct || 0) * 100)} %
        {#if editor.liveSegments.length > 0}
          &middot; {editor.liveSegments.length} Segmente bisher
        {/if}
      </span>
      <button class="btn btn-sm btn-danger" onclick={cancelTranscribe}
              title="Transkription nach dem aktuellen Abschnitt abbrechen">
        <i class="fa-solid fa-stop"></i> Abbrechen
      </button>
    </div>
  {/if}

  {#if !t?.has_transcript && !editor.transcribing && editor.liveSegments.length === 0}
    <div class="empty">
      <p>
        Dieses Video hat noch kein Transkript. Die KI extrahiert den Ton und
        erzeugt daraus Untertitel (SRT).
      </p>
      <button class="btn btn-primary" onclick={onStart}
              disabled={!editor.fileId}
              title="Transkription starten -- läuft als Job im Hintergrund">
        <i class="fa-solid fa-wand-magic-sparkles"></i> Transkribieren
      </button>
    </div>
  {:else if t?.has_transcript || segments.length > 0}
    <div class="tp-tools">
      <input type="search" class="tp-search"
             placeholder="Im Transkript suchen..."
             bind:value={query} />
      <button class="btn btn-sm" class:is-on={editor.transcriptFollowOn}
              onclick={toggleTranscriptFollow}
              title={editor.transcriptFollowOn
                ? 'Mitlaufen beim Abspielen ist an. Die Liste scrollt zur aktuellen Stelle.'
                : 'Mitlaufen ist aus. Du scrollst frei.'}>
        <i class="fa-solid fa-location-crosshairs"></i>
      </button>
      {#if t?.has_transcript}
        <a class="btn btn-sm" href={api.transcriptSrtUrl(editor.fileId)} download
           title="SRT-Datei herunterladen">
          <i class="fa-solid fa-download"></i> SRT
        </a>
        <button class="btn btn-sm btn-danger" onclick={onDelete}
                title="Transkript entfernen (Video bleibt)">
          <i class="fa-solid fa-trash"></i>
        </button>
      {/if}
    </div>

    <ul class="segs" bind:this={listEl} onscroll={onUserScroll}>
      {#each filtered as s, i (s.start + '-' + s.end + '-' + i)}
        {@const isActive = active && s.start === active.start && s.end === active.end}
        <li class:active={isActive} data-idx={segments.indexOf(s)}>
          <button class="seg" class:seg-active={isActive}
                  onclick={() => seek(s.start)}
                  title="Zu dieser Stelle springen">
            <span class="ts mono">{fmtTs(s.start)}</span>
            <span class="txt">{s.text}</span>
          </button>
        </li>
      {/each}
      {#if filtered.length === 0}
        <li class="nohit">Keine Treffer für "{query}"</li>
      {/if}
    </ul>
  {/if}
</div>

<style>
  .tp { display: flex; flex-direction: column; height: 100%; min-height: 0; }
  .tp-head {
    display: flex; align-items: center; gap: 8px;
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-panel);
    font-size: 13px;
  }
  .tp-head i { color: var(--accent); }
  .tp-head .title { font-weight: 600; }
  .tp-head .meta { color: var(--fg-muted); font-size: 11px; margin-left: auto; }

  .banner {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 12px;
    background: var(--accent-soft);
    color: var(--fg-primary);
    border-bottom: 1px solid var(--accent);
    font-size: 13px;
  }
  .banner > i { color: var(--accent); }
  .banner-text { flex: 1 1 auto; }

  .empty {
    padding: 18px 14px;
    text-align: center;
    color: var(--fg-muted);
    display: flex; flex-direction: column; gap: 12px;
    align-items: center;
    line-height: 1.6;
    font-size: 14px;
  }
  .empty p { margin: 0; max-width: 320px; }

  .tp-tools {
    display: flex; gap: 6px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-panel);
  }
  .tp-search {
    flex: 1 1 auto;
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 5px 10px;
    font: inherit;
    font-size: 12px;
  }
  .tp-search:focus {
    outline: none;
    border-color: var(--accent);
  }

  .segs {
    list-style: none; padding: 6px 0; margin: 0;
    flex: 1 1 auto;
    overflow-y: auto;
    min-height: 0;
  }
  .segs li {
    /* Dezente Farbsteuerung fuer nicht-aktive Segmente */
    color: var(--fg-muted);
  }
  .segs li.active {
    color: var(--fg-primary);
  }
  .segs li.nohit {
    padding: 12px;
    color: var(--fg-faint);
    font-size: 14px;
    text-align: center;
  }
  .seg {
    width: 100%;
    display: grid;
    grid-template-columns: 64px 1fr;
    gap: 12px;
    align-items: baseline;
    padding: 10px 14px;
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    color: inherit;
    cursor: pointer;
    text-align: left;
    font: inherit;
    /* Lesbarer: groesser + etwas dicker */
    font-size: 15px;
    font-weight: 500;
    line-height: 1.55;
    transition: background 120ms, color 120ms, border-color 120ms;
  }
  .seg:hover { background: var(--bg-elev); }
  .seg .ts {
    color: var(--fg-faint);
    font-size: 12px;
    font-weight: 500;
  }
  .seg .txt { color: inherit; }

  /* Aktives Segment: akzentfarbig unterlegt, linke Leiste breiter, Text
     fetter -- klar lesbar beim Mitlaufen, wie in Voice2Text. */
  .seg-active {
    background: var(--accent-soft);
    border-left-color: var(--accent);
    color: var(--fg-primary);
    font-weight: 700;
  }
  .seg-active .ts { color: var(--accent); font-weight: 700; }
</style>
