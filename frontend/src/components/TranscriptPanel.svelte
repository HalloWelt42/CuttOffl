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
  let currentMatchIdx = $state(0);     // 0-basiert, -1 = kein aktiver Treffer
  let searchInputEl = $state();
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

  // Indizes aller Segmente, die den Suchbegriff enthalten. Anders als
  // vorher filtern wir die Liste NICHT -- alle Segmente bleiben sichtbar,
  // nur die Treffer werden markiert und per vor/zurueck angesprungen.
  const q = $derived(query.trim());
  const qLow = $derived(q.toLocaleLowerCase('de'));
  const matches = $derived.by(() => {
    if (!qLow) return [];
    const hits = [];
    for (let i = 0; i < segments.length; i++) {
      if ((segments[i].text || '').toLocaleLowerCase('de').includes(qLow)) {
        hits.push(i);
      }
    }
    return hits;
  });

  // Treffer-Index klemmen, wenn sich die matches aendern
  $effect(() => {
    if (matches.length === 0) { currentMatchIdx = -1; return; }
    if (currentMatchIdx < 0) currentMatchIdx = 0;
    else if (currentMatchIdx >= matches.length) currentMatchIdx = matches.length - 1;
  });

  const active = $derived(activeSegmentAt(editor.playhead, segments));

  /** Text eines Segments in [text, match, text, ...]-Tupel zerlegen,
   *  damit die Suchtreffer im Template mit <mark> gerendert werden. */
  function splitForHighlight(text) {
    if (!qLow) return [{ t: text, hit: false }];
    const parts = [];
    const lower = text.toLocaleLowerCase('de');
    let i = 0;
    while (i < text.length) {
      const at = lower.indexOf(qLow, i);
      if (at === -1) { parts.push({ t: text.slice(i), hit: false }); break; }
      if (at > i)    parts.push({ t: text.slice(i, at), hit: false });
      parts.push({ t: text.slice(at, at + qLow.length), hit: true });
      i = at + qLow.length;
    }
    return parts;
  }

  function gotoMatch(idx) {
    if (matches.length === 0) return;
    const n = matches.length;
    // Modulo mit Korrektur fuer negative Werte
    currentMatchIdx = ((idx % n) + n) % n;
    const segIdx = matches[currentMatchIdx];
    const seg = segments[segIdx];
    if (!seg) return;
    // Playhead mitziehen -- das aktive Segment wird so auch in der
    // Timeline und Untertitel sichtbar
    seek(seg.start);
    // In den Sichtbereich scrollen
    const el = listEl?.querySelector(`[data-idx="${segIdx}"]`);
    if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }
  function nextMatch() { gotoMatch(currentMatchIdx + 1); }
  function prevMatch() { gotoMatch(currentMatchIdx - 1); }

  function onSearchKey(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (e.shiftKey) prevMatch(); else nextMatch();
    } else if (e.key === 'Escape') {
      query = '';
      searchInputEl?.blur();
    }
  }

  function clearSearch() { query = ''; searchInputEl?.focus(); }

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
    // Bei aktiver Suche ueberlassen wir das Scrollen der Such-Navigation
    // (gotoMatch). So springt die Ansicht nicht zwischen Playhead und
    // Treffer hin und her.
    if (qLow) return;
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
      <div class="search-wrap">
        <i class="fa-solid fa-magnifying-glass search-ico"></i>
        <input type="search" class="tp-search"
               placeholder="Im Transkript suchen..."
               bind:this={searchInputEl}
               bind:value={query}
               onkeydown={onSearchKey} />
        {#if query}
          <button class="search-clear" onclick={clearSearch}
                  title="Suche leeren (Esc)">
            <i class="fa-solid fa-xmark"></i>
          </button>
        {/if}
      </div>
      {#if qLow}
        <span class="match-count mono"
              class:no-hit={matches.length === 0}>
          {matches.length === 0 ? '0 Treffer'
            : `${currentMatchIdx + 1} von ${matches.length}`}
        </span>
        <button class="btn btn-sm" onclick={prevMatch}
                disabled={matches.length === 0}
                title="Voriger Treffer (Shift+Enter)">
          <i class="fa-solid fa-chevron-up"></i>
        </button>
        <button class="btn btn-sm" onclick={nextMatch}
                disabled={matches.length === 0}
                title="Naechster Treffer (Enter)">
          <i class="fa-solid fa-chevron-down"></i>
        </button>
      {/if}
      <button class="btn btn-sm" class:is-on={editor.transcriptFollowOn}
              onclick={toggleTranscriptFollow}
              title={editor.transcriptFollowOn
                ? 'Mitlaufen beim Abspielen ist an. Die Liste scrollt zur aktuellen Stelle.'
                : 'Mitlaufen ist aus. Du scrollst frei.'}>
        <i class="fa-solid fa-location-crosshairs"></i>
      </button>
      {#if t?.has_transcript}
        <a class="btn btn-sm" href={api.transcriptSrtUrl(editor.fileId)} download
           title="Als SRT-Datei herunterladen (klassisches Untertitel-Format)">
          <i class="fa-solid fa-download"></i> SRT
        </a>
        <a class="btn btn-sm" href={api.transcriptVttUrl(editor.fileId)} download
           title="Als WebVTT-Datei herunterladen (fuer HTML5-Video-Player)">
          <i class="fa-solid fa-download"></i> VTT
        </a>
        <button class="btn btn-sm btn-danger" onclick={onDelete}
                title="Transkript entfernen (Video bleibt)">
          <i class="fa-solid fa-trash"></i>
        </button>
      {/if}
    </div>

    <ul class="segs" bind:this={listEl} onscroll={onUserScroll}>
      {#each segments as s, i (s.start + '-' + s.end + '-' + i)}
        {@const isActive = active && s.start === active.start && s.end === active.end}
        {@const matchPos = matches.indexOf(i)}
        {@const isMatch = matchPos >= 0}
        {@const isCurrentMatch = isMatch && matchPos === currentMatchIdx}
        <li class:active={isActive}
            class:is-match={isMatch}
            class:is-current-match={isCurrentMatch}
            data-idx={i}>
          <button class="seg" class:seg-active={isActive}
                  onclick={() => seek(s.start)}
                  title="Zu dieser Stelle springen">
            <span class="ts mono">{fmtTs(s.start)}</span>
            <span class="txt">
              {#each splitForHighlight(s.text) as part, pi (pi)}
                {#if part.hit}<mark>{part.t}</mark>{:else}{part.t}{/if}
              {/each}
            </span>
          </button>
        </li>
      {/each}
      {#if qLow && matches.length === 0}
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
    display: flex;
    gap: 6px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-panel);
    align-items: center;
    flex-wrap: wrap;
  }
  .search-wrap {
    position: relative;
    flex: 1 1 180px;
    min-width: 150px;
  }
  .search-ico {
    position: absolute;
    left: 8px; top: 50%;
    transform: translateY(-50%);
    color: var(--fg-faint);
    font-size: 11px;
    pointer-events: none;
  }
  .tp-search {
    width: 100%;
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 5px 26px 5px 26px;
    font: inherit;
    font-size: 13px;
  }
  .tp-search:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-soft);
  }
  .search-clear {
    position: absolute;
    right: 4px; top: 50%;
    transform: translateY(-50%);
    background: transparent;
    border: none;
    color: var(--fg-muted);
    cursor: pointer;
    padding: 2px 5px;
    border-radius: 4px;
    font: inherit;
  }
  .search-clear:hover { color: var(--fg-primary); background: var(--bg-panel); }

  .match-count {
    font-size: 11px;
    color: var(--fg-muted);
    padding: 3px 6px;
    background: var(--bg-elev);
    border-radius: 10px;
    border: 1px solid var(--border);
  }
  .match-count.no-hit {
    color: var(--danger);
    border-color: color-mix(in oklab, var(--danger) 40%, var(--border));
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

  /* Such-Markierung: <mark>-Spans im Text. Suchtreffer-Segmente
     insgesamt bekommen einen dezenten linken Strich in Amber, das
     aktive (aktuell angesprungene) Treffer-Segment ist kraeftiger. */
  .segs mark {
    background: color-mix(in oklab, var(--warning) 45%, transparent);
    color: var(--fg-primary);
    padding: 0 2px;
    border-radius: 2px;
  }
  .segs li.is-match .seg {
    border-left-color: color-mix(in oklab, var(--warning) 55%, var(--border));
  }
  .segs li.is-current-match .seg {
    background: color-mix(in oklab, var(--warning) 18%, var(--bg-elev));
    border-left-color: var(--warning);
  }
  .segs li.is-current-match mark {
    background: var(--warning);
    color: #1a0d03;
  }
</style>
