<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import { editor, seek, tickPreview } from '../lib/editor.svelte.js';

  // Bewusst KEINE $state() -- das sind DOM-Refs aus bind:this und
  // werden nicht von der UI reaktiv gelesen; $state() hier triggert
  // Reactivity-Loops im Player.
  // svelte-ignore non_reactive_update
  let videoEl;
  // svelte-ignore non_reactive_update
  let playerEl;
  let lastExternal = 0;
  let isFullscreen = $state(false);

  function fmt(t) {
    if (!isFinite(t)) return '--:--:--.--';
    const h = Math.floor(t / 3600);
    const m = Math.floor((t % 3600) / 60);
    const s = Math.floor(t % 60);
    const f = Math.floor((t - Math.floor(t)) * 100);
    return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(f).padStart(2,'0')}`;
  }

  // Playhead aus Editor-Store → Video-Element
  $effect(() => {
    if (!videoEl || !editor.fileId) return;
    const p = editor.playhead;
    if (Math.abs(p - lastExternal) < 0.04) return; // ignoriere Echo
    if (Math.abs(p - videoEl.currentTime) > 0.1) {
      videoEl.currentTime = p;
    }
  });

  function onTimeUpdate() {
    if (!videoEl) return;
    lastExternal = videoEl.currentTime;
    editor.playhead = videoEl.currentTime;

    // Preview-Logik: Bereichs-/Clip-/Timeline-Wiedergabe
    const action = tickPreview(videoEl.currentTime);
    if (!action) return;
    if (action.stop) {
      videoEl.pause();
    } else if (typeof action.seekTo === 'number') {
      videoEl.currentTime = action.seekTo;
      if (videoEl.paused) videoEl.play().catch(() => {});
    }
  }

  // Wenn eine neue Preview gestartet wird, automatisch abspielen.
  $effect(() => {
    const p = editor.preview;
    if (!videoEl || !p || !p.autoPlay) return;
    // erst seek abschliessen lassen
    const seekTo = p.start;
    if (Math.abs(videoEl.currentTime - seekTo) > 0.1) {
      videoEl.currentTime = seekTo;
    }
    videoEl.play().catch(() => {});
  });

  // HTML5-Video feuert "timeupdate" nur alle ~200 ms -- zu wenig fuer
  // eine smoothe Playhead-Nadel auf der Timeline. Solange das Video
  // laeuft, holen wir per rAF den exakten currentTime und spiegeln ihn
  // in den Store. Damit bleibt die Nadel synchron zu 60 fps, ohne dass
  // wir die tatsaechliche Wiedergabe interpolieren muessten.
  let smoothRaf = 0;

  function smoothTick() {
    smoothRaf = 0;
    if (!videoEl || videoEl.paused) return;
    const t = videoEl.currentTime;
    lastExternal = t;
    // Nur schreiben, wenn sich auch wirklich was veraendert hat
    if (Math.abs(t - editor.playhead) > 0.001) editor.playhead = t;
    smoothRaf = requestAnimationFrame(smoothTick);
  }

  function onPlay()  {
    editor.isPlaying = true;
    if (!smoothRaf) smoothRaf = requestAnimationFrame(smoothTick);
  }
  function onPause() {
    editor.isPlaying = false;
    if (smoothRaf) { cancelAnimationFrame(smoothRaf); smoothRaf = 0; }
  }

  export function togglePlay() {
    if (!videoEl) return;
    if (videoEl.paused) videoEl.play(); else videoEl.pause();
  }

  export function nudge(delta) {
    if (!videoEl) return;
    videoEl.currentTime = Math.max(0, Math.min(editor.duration, videoEl.currentTime + delta));
  }

  export function stepFrame(dir) {
    const fps = editor.file?.fps || 25;
    nudge(dir / fps);
  }

  async function toggleFullscreen() {
    if (!playerEl) return;
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else if (playerEl.requestFullscreen) {
        await playerEl.requestFullscreen();
      } else if (playerEl.webkitRequestFullscreen) {
        // Safari
        playerEl.webkitRequestFullscreen();
      }
    } catch {
      // ignorieren (z. B. User-Gesture-Policy)
    }
  }

  onMount(() => {
    const on = () => { isFullscreen = !!document.fullscreenElement; };
    document.addEventListener('fullscreenchange', on);
    document.addEventListener('webkitfullscreenchange', on);
    return () => {
      document.removeEventListener('fullscreenchange', on);
      document.removeEventListener('webkitfullscreenchange', on);
      if (smoothRaf) cancelAnimationFrame(smoothRaf);
    };
  });
</script>

{#if editor.file}
  {@const subSeg = editor.subtitlesOn && editor.transcript?.has_transcript
    ? (() => {
        const t = editor.playhead;
        for (const s of editor.transcript.segments || []) {
          if (t >= (s.start ?? 0) && t < (s.end ?? 0)) return s;
        }
        return null;
      })()
    : null}
  <div class="player" class:is-fullscreen={isFullscreen} bind:this={playerEl}>
    <div class="vid-wrap">
      {#key editor.fileId}
        <video
          bind:this={videoEl}
          src={api.proxyUrl(editor.fileId)}
          preload="auto"
          ontimeupdate={onTimeUpdate}
          onplay={onPlay}
          onpause={onPause}
          onclick={togglePlay}
        >
          <!-- Leerer captions-Track erfuellt die a11y-Anforderung; die
               echten Untertitel kommen aus dem Transkript und werden als
               Overlay (.subtitle) gerendert, nicht ueber native tracks. -->
          <track kind="captions" />
        </video>
      {/key}
      {#if subSeg}
        <div class="subtitle" aria-live="polite">{subSeg.text}</div>
      {/if}
    </div>
    <div class="controls mono">
      <button class="btn" onclick={() => nudge(-10)}
              title="10 Sekunden zurückspringen (Taste J)">
        <i class="fa-solid fa-backward"></i>
      </button>
      <button class="btn" onclick={() => stepFrame(-1)}
              title="Ein Einzelbild zurück (Pfeil links; mit Umschalt: 10 Bilder)">
        <i class="fa-solid fa-step-backward"></i>
      </button>
      <button class="btn btn-primary" onclick={togglePlay}
              title={editor.isPlaying ? 'Wiedergabe anhalten (Leertaste)' : 'Wiedergabe starten (Leertaste)'}>
        <i class="fa-solid {editor.isPlaying ? 'fa-pause' : 'fa-play'}"></i>
      </button>
      <button class="btn" onclick={() => stepFrame(1)}
              title="Ein Einzelbild vor (Pfeil rechts; mit Umschalt: 10 Bilder)">
        <i class="fa-solid fa-step-forward"></i>
      </button>
      <button class="btn" onclick={() => nudge(10)}
              title="10 Sekunden vorspringen (Taste L)">
        <i class="fa-solid fa-forward"></i>
      </button>
      <span class="t">{fmt(editor.playhead)}</span>
      <span class="sep">/</span>
      <span class="t dim">{fmt(editor.duration)}</span>
      <span class="spacer"></span>
      {#if editor.transcript?.has_transcript}
        <button class="btn" class:active={editor.subtitlesOn}
                onclick={() => { editor.subtitlesOn = !editor.subtitlesOn;
                                  try { localStorage.setItem('editor.subtitlesOn',
                                    JSON.stringify(editor.subtitlesOn)); } catch {} }}
                title={editor.subtitlesOn
                  ? 'Untertitel im Video ausblenden'
                  : 'Untertitel im Video einblenden'}>
          <i class="fa-solid fa-closed-captioning"></i>
        </button>
      {/if}
      <button class="btn" onclick={toggleFullscreen}
              title={isFullscreen
                ? 'Vollbild verlassen (Esc)'
                : 'Video im Vollbild abspielen; auch die Timeline-Vorschau läuft in Vollbild weiter'}>
        <i class="fa-solid {isFullscreen ? 'fa-compress' : 'fa-expand'}"></i>
      </button>
    </div>
  </div>
{:else}
  <div class="empty soft">Kein Video geladen</div>
{/if}

<style>
  .player {
    display: flex; flex-direction: column;
    background: var(--bg-sink);
    border-bottom: 1px solid var(--border);
  }
  /* Fullscreen: Player fuellt den kompletten Screen. Das Video nimmt den
     gesamten verfuegbaren Raum bis auf die Controls-Leiste ein (object-fit
     contain behaelt die Aspect Ratio und zeigt ggf. schwarze Letterbox-
     Balken). Controls bleiben sichtbar, damit Preview/Play/Stop im
     Vollbild funktioniert. */
  .player.is-fullscreen,
  .player:fullscreen,
  .player:-webkit-full-screen {
    width: 100vw;
    height: 100vh;
    background: #000;
    border: none;
  }
  .player.is-fullscreen .vid-wrap,
  .player:fullscreen .vid-wrap,
  .player:-webkit-full-screen .vid-wrap {
    flex: 1 1 auto;
    width: 100%;
    min-height: 0;
  }
  .player.is-fullscreen video,
  .player:fullscreen video,
  .player:-webkit-full-screen video {
    width: 100%;
    height: 100%;
    max-width: none;
    max-height: none;
    object-fit: contain;
  }
  .spacer { flex: 1; }
  .vid-wrap {
    position: relative;
    flex: 1;
    display: grid; place-items: center;
    background: #000;
    min-height: 0;
    overflow: hidden;
  }
  video {
    max-width: 100%;
    max-height: 100%;
    display: block;
    cursor: pointer;
  }

  /* Untertitel-Overlay am unteren Bildrand. Ueberlappt das Video, bleibt
     zentriert, mit ein bisschen Schwarzschatten fuer Lesbarkeit egal
     welcher Hintergrund. */
  .subtitle {
    position: absolute;
    left: 50%;
    bottom: 4%;
    transform: translateX(-50%);
    max-width: 90%;
    padding: 6px 14px;
    background: rgba(0, 0, 0, 0.65);
    color: #fff;
    font-size: 18px;
    font-weight: 600;
    line-height: 1.35;
    border-radius: 4px;
    text-align: center;
    text-shadow: 0 1px 3px rgba(0,0,0,0.9);
    pointer-events: none;
    white-space: pre-wrap;
  }
  .player.is-fullscreen .subtitle,
  .player:fullscreen .subtitle {
    font-size: 28px;
    padding: 10px 24px;
    bottom: 6%;
  }

  /* Aktiver Toggle fuer den CC-Button */
  .controls .btn.active {
    color: var(--accent);
    border-color: var(--accent);
    background: var(--accent-soft);
  }
  .controls {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    background: var(--bg-panel);
    border-top: 1px solid var(--border);
  }
  .controls button {
    background: var(--bg-elev);
    color: var(--fg-muted);
    border: 1px solid var(--border);
    padding: 6px 10px;
    border-radius: 6px;
    cursor: pointer;
    min-width: 36px;
    font-size: 12px;
  }
  .controls button:hover { color: var(--fg-primary); border-color: var(--border-strong); }
  .t { margin-left: 12px; font-size: 13px; }
  .dim { color: var(--fg-muted); }
  .sep { color: var(--fg-faint); }
  .empty { display: grid; place-items: center; height: 100%; color: var(--fg-faint); }
</style>
