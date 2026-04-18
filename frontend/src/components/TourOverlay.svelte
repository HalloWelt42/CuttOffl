<script>
  // TourOverlay -- Spotlight-Backdrop + Hinweisbox + Controls.
  //
  // Der Backdrop ist ein halbtransparentes Rechteck mit einem Loch
  // über dem aktuellen Ziel-Element. Das Loch wird per CSS mask-image
  // gezeichnet, damit das Ziel-Element klickbar bleibt und der Rest
  // der App visuell zurücktritt. Die Hinweisbox positioniert sich
  // relativ zum Ziel-Element -- je nachdem, wo im Viewport Platz ist.

  import {
    tour, currentStep, nextStep, prevStep, stopTour,
    toggleMode, getTour, tourAudio, toggleTourAudio,
    pauseTour, resumeTour, scheduleAdvance, clearAdvance,
    DEMO_AUDIO_BUFFER_MS, DEMO_FALLBACK_MS,
  } from '../lib/tour.svelte.js';
  import { onDestroy } from 'svelte';

  const activeTour = $derived(tour.activeId ? getTour(tour.activeId) : null);
  const step = $derived(tour.running ? currentStep() : null);
  const stepTotal = $derived(activeTour?.steps?.length ?? 0);
  const hasTarget = $derived(!!tour.targetRect);

  // Platzierung der Hinweisbox -- sucht die Seite des Ziel-Elements
  // mit dem meisten Platz und richtet die Box dort aus.
  const boxStyle = $derived.by(() => {
    if (!tour.running) return '';
    const pad = 18;
    const boxW = 380;
    const boxH = 200;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const r = tour.targetRect;
    if (!r) {
      // Keine Zielkoordinate -> mittig im Viewport
      return `left: ${(vw - boxW) / 2}px; top: ${(vh - boxH) / 2}px;`;
    }
    // Entscheidung: unten, oben, rechts, links vom Ziel?
    const spaceBelow = vh - r.bottom;
    const spaceAbove = r.top;
    const spaceRight = vw - r.right;
    const spaceLeft = r.left;
    let left, top;
    if (spaceBelow >= boxH + pad) {
      left = clamp(r.left + r.width / 2 - boxW / 2, pad, vw - boxW - pad);
      top = r.bottom + pad;
    } else if (spaceAbove >= boxH + pad) {
      left = clamp(r.left + r.width / 2 - boxW / 2, pad, vw - boxW - pad);
      top = r.top - boxH - pad;
    } else if (spaceRight >= boxW + pad) {
      left = r.right + pad;
      top = clamp(r.top + r.height / 2 - boxH / 2, pad, vh - boxH - pad);
    } else if (spaceLeft >= boxW + pad) {
      left = r.left - boxW - pad;
      top = clamp(r.top + r.height / 2 - boxH / 2, pad, vh - boxH - pad);
    } else {
      left = (vw - boxW) / 2;
      top = (vh - boxH) / 2;
    }
    return `left: ${left}px; top: ${top}px; width: ${boxW}px;`;
  });

  // Clip-Path-Polygon zeichnet das Loch: wir erzeugen einen Polygon-
  // Pfad, der den ganzen Viewport als Außen-Rechteck hat und das
  // Ziel-Rechteck als inneres "Loch" ausspart (Even-Odd-Regel).
  const maskStyle = $derived.by(() => {
    const r = tour.targetRect;
    if (!r) return '';
    const pad = 6;
    const x1 = Math.max(0, r.left - pad);
    const y1 = Math.max(0, r.top - pad);
    const x2 = Math.min(window.innerWidth, r.right + pad);
    const y2 = Math.min(window.innerHeight, r.bottom + pad);
    // Winkel-verrundetes Rechteck -- Border-Radius beim Spotlight
    return `--hx1: ${x1}px; --hy1: ${y1}px; `
         + `--hx2: ${x2}px; --hy2: ${y2}px;`;
  });

  function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(v, hi));
  }

  function onKey(e) {
    if (!tour.running) return;
    if (e.key === 'Escape') { stopTour(); return; }
    if (e.key === 'ArrowRight' || e.key === 'Enter') {
      e.preventDefault();
      void nextStep();
    }
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      void prevStep();
    }
  }

  // Audio-Begleitung: pro Schritt gibt es eine vorab erzeugte MP3
  // unter /tour-audio/<tour-id>-<idx>.mp3. Wenn die Datei fehlt
  // (404) oder der Nutzer Audio abgeschaltet hat, bleibt es still.
  let audioEl = $state(null);
  // Merker, ob für den aktuellen Schritt der Auto-Advance bereits
  // eingeplant wurde (vermeidet doppelte Scheduling-Aufrufe).
  let advanceScheduledFor = -1;

  $effect(() => {
    const src = step?.audio_src;
    if (!audioEl) return;
    if (!tour.running || !src) {
      audioEl.pause();
      return;
    }
    // Quelle wechseln, wenn nötig
    try {
      const abs = new URL(src, window.location.origin).href;
      if (audioEl.src !== abs) {
        audioEl.src = src;
        advanceScheduledFor = -1;
      }
    } catch { audioEl.src = src; advanceScheduledFor = -1; }
    if (tourAudio.enabled && !tour.paused) {
      const p = audioEl.play();
      if (p && typeof p.catch === 'function') {
        p.catch(() => {
          // Autoplay-Block: kein Fehler, User muss ggf. den Lautsprecher-
          // Toggle einmal anfassen, damit der Browser Audio erlaubt.
          scheduleFallbackAdvance();
        });
      }
    } else {
      audioEl.pause();
      // Kein Audio aktiv -> Auto-Advance per Fallback-Zeit einplanen
      scheduleFallbackAdvance();
    }
  });

  // Beim Umschalten des Lautsprecher-Toggles den aktuellen Step sofort
  // abspielen bzw. pausieren (ohne auf Step-Wechsel zu warten).
  $effect(() => {
    if (!audioEl) return;
    if (!tour.running) return;
    if (tourAudio.enabled && !tour.paused) {
      if (audioEl.paused && audioEl.src) {
        audioEl.play().catch(() => scheduleFallbackAdvance());
      }
    } else {
      audioEl.pause();
      if (!tourAudio.enabled) scheduleFallbackAdvance();
    }
  });

  // Pause-Zustand der Tour spiegelt sich auf Audio: pausieren /
  // fortsetzen. Im Demo-Modus greift das auch auf den Advance-Timer.
  $effect(() => {
    if (!audioEl) return;
    if (tour.paused) {
      audioEl.pause();
    } else if (tour.running && tourAudio.enabled && audioEl.src) {
      if (audioEl.paused) audioEl.play().catch(() => {});
    }
  });

  function scheduleFallbackAdvance() {
    if (tour.mode !== 'demo' || tour.paused || !tour.running) return;
    if (advanceScheduledFor === tour.stepIndex) return;
    advanceScheduledFor = tour.stepIndex;
    const fallback = step?.demo_ms ?? DEMO_FALLBACK_MS;
    scheduleAdvance(fallback, fallback);
  }

  function onAudioLoaded() {
    // Ab jetzt steht duration fest -- wir planen den Advance erst
    // nach dem Audio-Ende + Puffer ein, nicht gleich beim Start.
    if (tour.mode !== 'demo' || tour.paused || !tour.running) return;
    // Audio-Ende triggert onAudioEnded; hier nur sicherstellen, dass
    // kein Fallback-Timer aus einem früheren State noch läuft.
    clearAdvance();
    advanceScheduledFor = -1;
  }

  function onAudioEnded() {
    if (tour.mode !== 'demo' || tour.paused || !tour.running) return;
    if (advanceScheduledFor === tour.stepIndex) return;
    advanceScheduledFor = tour.stepIndex;
    // Puffer zum Nachlesen, dann nextStep
    scheduleAdvance(DEMO_AUDIO_BUFFER_MS, DEMO_AUDIO_BUFFER_MS);
  }

  function onAudioError() {
    // MP3 fehlt oder kaputt -> sofort Fallback-Zeit verwenden
    scheduleFallbackAdvance();
  }

  // Countdown-Anzeige: läuft via requestAnimationFrame, aktualisiert
  // einen lokalen $state, damit die UI smooth tickt.
  let countdownMs = $state(0);
  let countdownRaf = null;
  function tickCountdown() {
    if (tour.advanceAt > 0) {
      countdownMs = Math.max(0, tour.advanceAt - Date.now());
    } else {
      countdownMs = 0;
    }
    countdownRaf = requestAnimationFrame(tickCountdown);
  }
  $effect(() => {
    if (tour.running && tour.mode === 'demo') {
      if (!countdownRaf) countdownRaf = requestAnimationFrame(tickCountdown);
    } else {
      if (countdownRaf) { cancelAnimationFrame(countdownRaf); countdownRaf = null; }
      countdownMs = 0;
    }
  });
  onDestroy(() => {
    if (countdownRaf) cancelAnimationFrame(countdownRaf);
  });

  const countdownPct = $derived.by(() => {
    if (!tour.advanceTotal || !countdownMs) return 0;
    return Math.min(100, (countdownMs / tour.advanceTotal) * 100);
  });
</script>

<svelte:window onkeydown={onKey} />

{#if tour.running && step}
  {#if hasTarget}
    <div class="tour-backdrop has-hole" style={maskStyle} aria-hidden="true">
      <div class="tour-hole"></div>
    </div>
    <div class="tour-ring" style={maskStyle}></div>
  {:else}
    <div class="tour-backdrop solid" aria-hidden="true"></div>
  {/if}

  <div class="tour-box" style={boxStyle} role="dialog" aria-live="polite">
    <div class="tour-head">
      <div class="tour-counter">
        <i class="fa-solid {activeTour?.icon ?? 'fa-life-ring'}"
           style:color={activeTour?.color}></i>
        <span>{activeTour?.title}</span>
        <span class="counter-num mono">
          {tour.stepIndex + 1} / {stepTotal}
        </span>
      </div>
      <button class="tour-audio-toggle"
              class:on={tourAudio.enabled}
              onclick={toggleTourAudio}
              aria-label={tourAudio.enabled ? 'Audio ausschalten' : 'Audio einschalten'}
              title={tourAudio.enabled
                ? 'Erklärungen werden vorgelesen -- klicken zum Stummschalten'
                : 'Audio ist aus -- klicken zum Einschalten'}>
        <i class="fa-solid {tourAudio.enabled ? 'fa-volume-high' : 'fa-volume-xmark'}"></i>
      </button>
      <button class="tour-x" onclick={stopTour} aria-label="Tour beenden"
              title="Tour beenden (Esc)">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>

    <h3 class="tour-title">{step.title}</h3>
    <p class="tour-body">{step.body}</p>
    {#if step.hint}
      <p class="tour-hint">
        <i class="fa-solid fa-lightbulb"></i>
        {step.hint}
      </p>
    {/if}

    <div class="tour-foot">
      <button class="tour-btn mode-btn" onclick={toggleMode}
              title={tour.mode === 'demo'
                ? 'Auf manuelles Weiterklicken zurückschalten'
                : 'Für mich vorführen -- wechselt automatisch weiter'}>
        {#if tour.mode === 'demo'}
          <i class="fa-solid fa-hand-pointer"></i>
          Ich klick selber
        {:else}
          <i class="fa-solid fa-play"></i>
          Zeig es mir
        {/if}
      </button>

      {#if tour.mode === 'demo'}
        <!-- Countdown + Pause/Play im Demo-Modus. Zeigt, wie lang es
             bis zum nächsten Schritt dauert und lässt den User die
             Tour jederzeit anhalten. -->
        <div class="countdown" class:is-paused={tour.paused}
             title={tour.paused
               ? 'Tour pausiert -- Klick auf Play setzt fort'
               : (countdownMs > 0
                   ? `Nächster Schritt in ${Math.ceil(countdownMs / 1000)}s`
                   : 'Erklärung läuft')}>
          <button class="tour-btn playpause"
                  onclick={() => (tour.paused ? resumeTour() : pauseTour())}
                  aria-label={tour.paused ? 'Fortsetzen' : 'Pause'}>
            <i class="fa-solid {tour.paused ? 'fa-play' : 'fa-pause'}"></i>
          </button>
          <div class="countdown-bar">
            <div class="cd-fill" style="width: {countdownPct}%"></div>
          </div>
          <span class="cd-num mono">
            {#if tour.paused}
              <i class="fa-solid fa-pause"></i>
            {:else if countdownMs > 0}
              {Math.ceil(countdownMs / 1000)}s
            {:else}
              <i class="fa-solid fa-circle-notch fa-spin"></i>
            {/if}
          </span>
        </div>
      {/if}

      <div class="tour-nav">
        <button class="tour-btn"
                onclick={prevStep}
                disabled={tour.stepIndex === 0}
                title="Einen Schritt zurück (Pfeil links)">
          <i class="fa-solid fa-arrow-left"></i> Zurück
        </button>
        <button class="tour-btn primary"
                onclick={nextStep}
                title="Nächster Schritt (Pfeil rechts oder Enter)">
          {#if tour.stepIndex >= stepTotal - 1 && tour.queue.length === 0}
            <i class="fa-solid fa-check"></i> Fertig
          {:else}
            Weiter <i class="fa-solid fa-arrow-right"></i>
          {/if}
        </button>
      </div>
    </div>

    <!-- Progress-Balken der Tour -->
    <div class="tour-progress">
      <div class="fill"
           style="width: {((tour.stepIndex + 1) / stepTotal * 100).toFixed(1)}%"></div>
    </div>

    <!-- Queue-Indikator, wenn weitere Touren nachkommen (Präsentation) -->
    {#if tour.queue.length > 0 && tour.stepIndex >= stepTotal - 1}
      <div class="queue-hint mono">
        <i class="fa-solid fa-forward"></i>
        Gleich weiter: nächste Tour ({tour.queue.length} verbleiben)
      </div>
    {/if}

    <!-- Vorgelesene Erklärung: einmalig synthetisiert, liegt als MP3
         unter /tour-audio/<id>-<idx>.mp3. Fehlt die Datei, läuft die
         Tour geräuschlos weiter. Der Advance zum nächsten Schritt
         hängt im Demo-Modus am `ended`-Event -- so wird nie mitten
         im Satz abgebrochen. -->
    <audio bind:this={audioEl} preload="auto"
           onloadedmetadata={onAudioLoaded}
           onended={onAudioEnded}
           onerror={onAudioError}></audio>
  </div>
{/if}

<style>
  /* Backdrop ohne Ziel -- voller Viewport halbtransparent */
  .tour-backdrop.solid {
    position: fixed; inset: 0;
    background: rgba(5, 8, 12, 0.72);
    z-index: 9000;
    backdrop-filter: blur(1.5px);
    pointer-events: auto;
  }

  /* Backdrop mit Loch: wir rendern zwei CSS-Boxen um das Loch herum,
     sodass die ausgesparte Fläche klickbar bleibt. */
  .tour-backdrop.has-hole {
    position: fixed; inset: 0;
    z-index: 9000;
    pointer-events: none;
  }
  .tour-backdrop.has-hole::before,
  .tour-backdrop.has-hole::after {
    content: "";
    position: fixed;
    background: rgba(5, 8, 12, 0.78);
    backdrop-filter: blur(1.5px);
    pointer-events: auto;
  }
  /* Oberer und unterer Streifen (volle Breite) */
  .tour-backdrop.has-hole::before {
    left: 0; right: 0;
    top: 0; height: var(--hy1);
  }
  .tour-backdrop.has-hole::after {
    left: 0; right: 0;
    top: var(--hy2); bottom: 0;
  }
  /* Linker und rechter Streifen (zwischen oben und unten) */
  .tour-backdrop.has-hole .tour-hole::before,
  .tour-backdrop.has-hole .tour-hole::after {
    content: "";
    position: fixed;
    background: rgba(5, 8, 12, 0.78);
    backdrop-filter: blur(1.5px);
    pointer-events: auto;
    top: var(--hy1);
    height: calc(var(--hy2) - var(--hy1));
  }
  .tour-backdrop.has-hole .tour-hole::before {
    left: 0;
    width: var(--hx1);
  }
  .tour-backdrop.has-hole .tour-hole::after {
    left: var(--hx2);
    right: 0;
  }

  /* Leuchtender Rand ums Zielelement */
  .tour-ring {
    position: fixed;
    left: var(--hx1);
    top: var(--hy1);
    width: calc(var(--hx2) - var(--hx1));
    height: calc(var(--hy2) - var(--hy1));
    border: 2px solid var(--accent);
    border-radius: 10px;
    box-shadow:
      0 0 0 4px rgba(88, 166, 255, 0.22),
      0 0 24px 2px rgba(88, 166, 255, 0.35);
    pointer-events: none;
    z-index: 9001;
    animation: ring-pulse 1.6s ease-in-out infinite;
  }
  @keyframes ring-pulse {
    0%, 100% { box-shadow:
      0 0 0 4px rgba(88, 166, 255, 0.22),
      0 0 24px 2px rgba(88, 166, 255, 0.35);
    }
    50%      { box-shadow:
      0 0 0 6px rgba(88, 166, 255, 0.32),
      0 0 32px 4px rgba(88, 166, 255, 0.48);
    }
  }

  .tour-box {
    position: fixed;
    z-index: 9002;
    background: var(--bg-panel);
    border: 1px solid var(--border-strong);
    border-radius: 10px;
    box-shadow: 0 14px 40px rgba(0, 0, 0, 0.55);
    padding: 14px 16px 10px;
    color: var(--fg-primary);
    font-size: 13px;
  }
  .tour-head {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 10px;
  }
  .tour-counter {
    display: flex; align-items: center; gap: 8px;
    flex: 1; min-width: 0;
    font-size: 12px;
    color: var(--fg-muted);
  }
  .tour-counter i { color: var(--accent); font-size: 14px; }
  .tour-counter span:first-of-type { color: var(--fg-primary); font-weight: 600; }
  .counter-num {
    margin-left: auto;
    font-size: 11px;
    color: var(--fg-faint);
  }
  .tour-audio-toggle {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--fg-muted);
    cursor: pointer;
    width: 28px; height: 24px;
    font-size: 12px;
    display: grid; place-items: center;
    transition: background 120ms, color 120ms, border-color 120ms;
  }
  .tour-audio-toggle:hover {
    color: var(--fg-primary);
    border-color: var(--border-strong);
  }
  .tour-audio-toggle.on {
    color: var(--accent);
    border-color: color-mix(in oklab, var(--accent) 45%, var(--border));
    background: var(--accent-soft);
  }

  .tour-x {
    background: transparent; border: none;
    color: var(--fg-muted);
    cursor: pointer;
    font-size: 14px;
    padding: 2px 4px;
  }
  .tour-x:hover { color: var(--fg-primary); }

  .tour-title {
    margin: 0 0 6px;
    font-size: 15px;
    font-weight: 700;
    color: var(--fg-primary);
  }
  .tour-body {
    margin: 0;
    line-height: 1.55;
    color: var(--fg-muted);
  }
  .tour-hint {
    margin: 10px 0 0;
    padding: 8px 10px;
    background: color-mix(in oklab, var(--warning) 14%, var(--bg-elev));
    border: 1px solid color-mix(in oklab, var(--warning) 35%, var(--border));
    border-radius: 6px;
    font-size: 12px;
    line-height: 1.45;
    color: var(--fg-primary);
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }
  .tour-hint i { color: var(--warning); margin-top: 2px; }

  .tour-foot {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-top: 12px;
  }
  .tour-nav {
    margin-left: auto;
    display: flex;
    gap: 6px;
  }
  .tour-btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 12px;
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--fg-primary);
    font: inherit;
    font-size: 12px;
    cursor: pointer;
    transition: background 120ms, border-color 120ms;
  }
  .tour-btn:hover {
    background: var(--bg-panel);
    border-color: var(--border-strong);
  }
  .tour-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .tour-btn.primary {
    background: var(--accent);
    color: var(--accent-on);
    border-color: var(--accent);
    font-weight: 600;
  }
  .tour-btn.primary:hover {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
  }
  .mode-btn {
    color: var(--fg-muted);
  }
  .mode-btn i { color: var(--accent); }

  .tour-progress {
    margin: 10px -16px 0;
    height: 3px;
    background: var(--bg-sink);
    border-top: 1px solid var(--border);
    overflow: hidden;
  }
  .tour-progress .fill {
    height: 100%;
    background: var(--accent);
    transition: width 200ms ease-out;
  }

  /* Countdown + Pause/Play im Demo-Modus */
  .countdown {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px 4px 4px;
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 8px;
    min-width: 140px;
  }
  .countdown.is-paused {
    background: color-mix(in oklab, var(--warning) 14%, var(--bg-elev));
    border-color: color-mix(in oklab, var(--warning) 40%, var(--border));
  }
  .tour-btn.playpause {
    padding: 4px 8px;
    font-size: 11px;
    background: transparent;
    border: none;
  }
  .tour-btn.playpause:hover {
    background: transparent;
    color: var(--accent);
  }
  .countdown-bar {
    flex: 1;
    height: 4px;
    background: var(--bg-sink);
    border-radius: 2px;
    overflow: hidden;
  }
  .cd-fill {
    height: 100%;
    background: var(--accent);
    transition: width 120ms linear;
  }
  .is-paused .cd-fill { background: var(--warning); }
  .cd-num {
    font-size: 11px;
    color: var(--fg-muted);
    min-width: 28px;
    text-align: right;
  }
  .is-paused .cd-num { color: var(--warning); }

  .queue-hint {
    margin: 6px -16px -10px;
    padding: 6px 12px;
    font-size: 11px;
    color: var(--accent);
    background: var(--accent-soft);
    border-top: 1px solid color-mix(in oklab, var(--accent) 30%, var(--border));
    border-radius: 0 0 10px 10px;
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .queue-hint i { color: var(--accent); }

  /* Responsive: kleine Viewports -> Box füllt untere Hälfte */
  @media (max-width: 640px) {
    .tour-box {
      left: 12px !important;
      right: 12px !important;
      top: auto !important;
      bottom: 12px !important;
      width: auto !important;
    }
  }
</style>
