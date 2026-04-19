<script>
  // Audio-Track-Zeile unter der Video-Timeline.
  //
  // Pro AudioClip im editor.edl.audio_track wird ein DOM-Block gerendert,
  // positioniert relativ zur gleichen Zeit-Skala wie die Video-Timeline
  // (editor.timelineZoom / editor.timelineScrollX).
  //
  // Interaktion:
  //   - Klick auf Block             -> selectAudioClip
  //   - Drag mitten auf dem Block   -> setAudioClipOffset (verschieben)
  //   - Drag linker/rechter Handle  -> setAudioClipRange (trimmen)
  //   - Klick in leeren Track-Bereich -> seek (wie Video-Timeline)

  import { api } from '../lib/api.js';
  import {
    editor, seek, selectAudioClip, setMuteOriginal,
    setAudioClipOffset, setAudioClipRange, setAudioClipGain,
    splitAudioAtPlayhead, deleteAudioClip,
  } from '../lib/editor.svelte.js';
  import AudioLibraryPicker from './AudioLibraryPicker.svelte';

  let pickerOpen = $state(false);

  let host;
  let width = $state(800);
  // pxPerSec spiegelt editor.timelineZoom (gleiche Skala wie Timeline).
  let pxPerSec = $state(editor.timelineZoom || 40);
  $effect(() => {
    const z = editor.timelineZoom;
    if (z && Math.abs(z - pxPerSec) > 0.1) pxPerSec = z;
  });

  // scrollX liest ausschliesslich aus dem Store -- die Video-Timeline
  // ist die Source of Truth fuer den horizontalen Offset.
  const scrollX = $derived(editor.timelineScrollX || 0);

  function totalPx() {
    return Math.max(width, (editor.duration || 0) * pxPerSec + 20);
  }
  function xAtTime(t) { return t * pxPerSec - scrollX; }
  function timeAtX(x) { return Math.max(0, (x + scrollX) / pxPerSec); }
  function clipPx(c) { return (c.src_end - c.src_start) * pxPerSec; }

  function measure() {
    if (host) width = host.clientWidth;
  }

  $effect(() => {
    measure();
    const ro = new ResizeObserver(measure);
    if (host) ro.observe(host);
    return () => ro.disconnect();
  });

  // --- Waveform-Cache pro file_id (shared ueber alle Clips derselben Datei)
  const waveformCache = $state({});
  function ensureWaveform(fileId) {
    if (!fileId || waveformCache[fileId] !== undefined) return;
    waveformCache[fileId] = null; // markieren "in-flight"
    api.waveform(fileId).then((wf) => {
      waveformCache[fileId] = wf;
    }).catch(() => {
      waveformCache[fileId] = null;
    });
  }

  // SVG-Polygonpunkte fuer einen Clip: Downsample der peaks auf die
  // sichtbare Breite, beschnitten auf src_start..src_end.
  function clipPolygon(c, widthPx, heightPx) {
    const wf = waveformCache[c.file_id];
    if (!wf || !Array.isArray(wf.peaks) || wf.peaks.length === 0) return '';
    const rate = wf.samples_per_second || 50;
    const i0 = Math.max(0, Math.floor(c.src_start * rate));
    const i1 = Math.min(wf.peaks.length, Math.ceil(c.src_end * rate));
    if (i1 <= i0) return '';
    const nTarget = Math.max(8, Math.min(480, Math.floor(widthPx)));
    const step = Math.max(1, Math.floor((i1 - i0) / nTarget));
    const reduced = [];
    for (let i = i0; i < i1; i += step) {
      let max = 0;
      for (let j = 0; j < step && i + j < i1; j++) {
        const v = Math.abs(wf.peaks[i + j]);
        if (v > max) max = v;
      }
      reduced.push(max);
    }
    const mid = heightPx / 2;
    const lastIdx = reduced.length - 1 || 1;
    const top = reduced.map((v, i) => {
      const x = (i / lastIdx) * widthPx;
      const y = mid - v * mid;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    const bot = reduced.map((v, i) => {
      const idx = lastIdx - i;
      const x = (idx / lastIdx) * widthPx;
      const y = mid + reduced[idx] * mid;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return [...top, ...bot].join(' ');
  }

  // Pro Clip nachladen, sobald er sichtbar ist. $effect reagiert auf
  // neue audio_track-Eintraege.
  $effect(() => {
    for (const c of editor.edl?.audio_track ?? []) {
      ensureWaveform(c.file_id);
    }
  });

  // --- Drag-State -------------------------------------------------------
  let drag = null;
  function onClipMouseDown(e, clip) {
    if (e.button !== 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const mode = e.target.classList.contains('handle-left')
      ? 'trim-left'
      : e.target.classList.contains('handle-right')
      ? 'trim-right'
      : 'move';
    drag = {
      mode,
      clipId: clip.id,
      startX: e.clientX,
      origSrcStart: clip.src_start,
      origSrcEnd: clip.src_end,
      origTimelineStart: clip.timeline_start,
      clipWidthPx: rect.width,
    };
    selectAudioClip(clip.id);
    window.addEventListener('mousemove', onDragMove);
    window.addEventListener('mouseup', onDragUp);
    e.stopPropagation();
    e.preventDefault();
  }

  function onDragMove(e) {
    if (!drag) return;
    const deltaPx = e.clientX - drag.startX;
    const deltaS = deltaPx / pxPerSec;
    const clip = editor.edl?.audio_track?.find((c) => c.id === drag.clipId);
    if (!clip) return;
    if (drag.mode === 'move') {
      setAudioClipOffset(drag.clipId, drag.origTimelineStart + deltaS);
    } else if (drag.mode === 'trim-left') {
      const newStart = Math.max(0,
        Math.min(drag.origSrcEnd - 0.05, drag.origSrcStart + deltaS));
      setAudioClipRange(drag.clipId, newStart, drag.origSrcEnd);
      // Wenn links getrimmt wird, soll der Inhalt "vor Ort" bleiben
      // (timeline_start mitshiften, damit der Audio-Inhalt nicht
      // springt).
      setAudioClipOffset(drag.clipId,
        drag.origTimelineStart + (newStart - drag.origSrcStart));
    } else if (drag.mode === 'trim-right') {
      const newEnd = Math.max(drag.origSrcStart + 0.05, drag.origSrcEnd + deltaS);
      setAudioClipRange(drag.clipId, drag.origSrcStart, newEnd);
    }
  }

  function onDragUp() {
    drag = null;
    window.removeEventListener('mousemove', onDragMove);
    window.removeEventListener('mouseup', onDragUp);
  }

  // Klick auf leere Track-Flaeche: seek. Vermeiden wenn ein Clip
  // darunter liegt (dort nur selektieren / draggen).
  function onHostMouseDown(e) {
    if (e.target !== host) return;
    const rect = host.getBoundingClientRect();
    const x = e.clientX - rect.left;
    seek(timeAtX(x));
  }
</script>

<div class="audio-toolbar mono">
  <span class="lbl"><i class="fa-solid fa-music"></i> Audio</span>
  <button class="bbtn" onclick={() => (pickerOpen = true)}
          title="Audio-Datei aus der Bibliothek am Playhead einfuegen">
    <i class="fa-solid fa-plus"></i> Hinzufügen
  </button>
  <button class="bbtn"
          onclick={() => splitAudioAtPlayhead()}
          disabled={!editor.edl?.audio_track?.length}
          title="Ausgewählten Audio-Clip am Playhead teilen (Taste S)">
    <i class="fa-solid fa-scissors"></i> Split
  </button>
  <button class="bbtn"
          disabled={!editor.selectedAudioClipId}
          onclick={() => editor.selectedAudioClipId && deleteAudioClip(editor.selectedAudioClipId)}
          title="Ausgewählten Audio-Clip entfernen (Taste Entf)">
    <i class="fa-solid fa-trash"></i>
  </button>
  <span class="spacer"></span>
  {#if editor.selectedAudioClipId}
    {@const sel = editor.edl?.audio_track?.find((c) => c.id === editor.selectedAudioClipId)}
    {#if sel}
      <label class="gain" title="Lautstärke des ausgewählten Clips (dB)">
        Gain
        <input type="range" min="-30" max="12" step="1"
               value={sel.gain_db}
               oninput={(e) => setAudioClipGain(sel.id, Number(e.currentTarget.value))} />
        <span class="db mono">{sel.gain_db > 0 ? '+' : ''}{sel.gain_db} dB</span>
      </label>
    {/if}
  {/if}
  <label class="mute" title="Originalton des Videos beim Render stummschalten">
    <input type="checkbox"
           checked={!!editor.edl?.mute_original}
           onchange={(e) => setMuteOriginal(e.currentTarget.checked)} />
    <i class="fa-solid {editor.edl?.mute_original ? 'fa-volume-xmark' : 'fa-volume-high'}"></i>
    <span>Original stumm</span>
  </label>
</div>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="audio-track"
     bind:this={host}
     role="presentation"
     onmousedown={onHostMouseDown}>
  <div class="inner" style:width="{totalPx()}px" style:transform="translateX({-scrollX}px)">
    {#each editor.edl?.audio_track ?? [] as clip (clip.id)}
      {@const widthPx = clipPx(clip)}
      {@const polygon = clipPolygon(clip, widthPx, 44)}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="audio-clip"
           class:selected={editor.selectedAudioClipId === clip.id}
           style:left="{clip.timeline_start * pxPerSec}px"
           style:width="{widthPx}px"
           onmousedown={(e) => onClipMouseDown(e, clip)}>
        <svg class="wf" viewBox="0 0 {widthPx} 44" preserveAspectRatio="none">
          <polygon points={polygon} />
        </svg>
        <div class="label mono">{clip.file_id.slice(0, 6)}</div>
        <div class="handle handle-left"></div>
        <div class="handle handle-right"></div>
      </div>
    {/each}
    <!-- Playhead-Linie in der Audio-Zeile, synchron zur Video-Playhead -->
    <div class="playhead" style:left="{(editor.playhead || 0) * pxPerSec}px"></div>
  </div>
  {#if (editor.edl?.audio_track ?? []).length === 0}
    <div class="empty mono">
      <i class="fa-solid fa-music"></i>
      Keine Audio-Spur. Nutze "Hinzufügen" in der Toolbar oben.
    </div>
  {/if}
</div>

<AudioLibraryPicker bind:open={pickerOpen} />

<style>
  .audio-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 10px;
    background: var(--bg-elev);
    border-top: 1px solid var(--border);
    font-size: 12px;
  }
  .audio-toolbar .lbl {
    color: var(--accent);
    font-weight: 600;
    margin-right: 4px;
  }
  .audio-toolbar .lbl i { margin-right: 4px; }
  .audio-toolbar .spacer { flex: 1; }
  .audio-toolbar .bbtn {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--fg-primary);
    padding: 3px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 11px;
  }
  .audio-toolbar .bbtn:hover:not(:disabled) { border-color: var(--accent); }
  .audio-toolbar .bbtn:disabled { opacity: 0.4; cursor: default; }
  .audio-toolbar .bbtn i { margin-right: 4px; }
  .audio-toolbar .gain {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 11px;
    color: var(--fg-muted);
  }
  .audio-toolbar .gain input[type="range"] { width: 100px; }
  .audio-toolbar .db { min-width: 44px; text-align: right; }
  .audio-toolbar .mute {
    display: inline-flex; align-items: center; gap: 4px;
    cursor: pointer;
    font-size: 11px;
    color: var(--fg-muted);
  }
  .audio-toolbar .mute input { margin: 0; }

  .audio-track {
    position: relative;
    height: 52px;
    background: var(--bg-sink);
    border-top: 1px solid var(--border);
    overflow: hidden;
    user-select: none;
    cursor: crosshair;
  }
  .inner {
    position: absolute;
    top: 0; left: 0; height: 100%;
    pointer-events: none;
  }
  .audio-clip {
    position: absolute;
    top: 4px;
    height: 44px;
    background: color-mix(in srgb, var(--accent) 22%, var(--bg-panel));
    border: 1px solid color-mix(in srgb, var(--accent) 50%, var(--border));
    border-radius: 4px;
    pointer-events: auto;
    cursor: grab;
    overflow: hidden;
  }
  .audio-clip.selected {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 30%, transparent);
  }
  .audio-clip:active { cursor: grabbing; }
  .wf {
    position: absolute;
    inset: 0;
    width: 100%; height: 100%;
    pointer-events: none;
  }
  .wf polygon { fill: var(--accent); opacity: 0.55; }
  .label {
    position: absolute;
    left: 6px; top: 4px;
    font-size: 10px;
    color: var(--fg-primary);
    background: rgba(0,0,0,0.4);
    padding: 1px 5px;
    border-radius: 3px;
    pointer-events: none;
  }
  .handle {
    position: absolute;
    top: 0; bottom: 0;
    width: 6px;
    cursor: ew-resize;
    background: var(--accent);
    opacity: 0;
    transition: opacity 80ms linear;
  }
  .audio-clip:hover .handle,
  .audio-clip.selected .handle { opacity: 0.7; }
  .handle-left  { left: 0; }
  .handle-right { right: 0; }

  .playhead {
    position: absolute;
    top: 0; bottom: 0;
    width: 1px;
    background: var(--danger, #e44);
    pointer-events: none;
  }

  .empty {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: var(--fg-muted);
    font-size: 12px;
    pointer-events: none;
  }
</style>
