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
  // mit dem meisten Platz und richtet die Box dort aus. Am Ende
  // klemmen wir die Position hart in den Viewport, damit die Box
  // auch in Grenzfällen (kleines Fenster, Ziel am Viewport-Rand)
  // immer vollständig sichtbar bleibt.
  const boxStyle = $derived.by(() => {
    if (!tour.running) return '';
    const pad = 18;
    const boxW = 380;
    const boxH = 200;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const r = tour.targetRect;
    let left, top;
    if (!r) {
      left = (vw - boxW) / 2;
      top  = (vh - boxH) / 2;
    } else {
      const spaceBelow = vh - r.bottom;
      const spaceAbove = r.top;
      const spaceRight = vw - r.right;
      const spaceLeft  = r.left;
      if (spaceBelow >= boxH + pad) {
        left = r.left + r.width / 2 - boxW / 2;
        top  = r.bottom + pad;
      } else if (spaceAbove >= boxH + pad) {
        left = r.left + r.width / 2 - boxW / 2;
        top  = r.top - boxH - pad;
      } else if (spaceRight >= boxW + pad) {
        left = r.right + pad;
        top  = r.top + r.height / 2 - boxH / 2;
      } else if (spaceLeft >= boxW + pad) {
        left = r.left - boxW - pad;
        top  = r.top + r.height / 2 - boxH / 2;
      } else {
        left = (vw - boxW) / 2;
        top  = (vh - boxH) / 2;
      }
    }
    // Harte Begrenzung in den Viewport -- die Box rutscht sonst
    // teilweise unter JobsBar oder an den oberen Rand.
    left = clamp(left, pad, Math.max(pad, vw - boxW - pad));
    top  = clamp(top,  pad, Math.max(pad, vh - boxH - pad));
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

  // Fortschrittsanzeige im Demo-Modus -- zwei Phasen:
  //   1. Audio läuft  -> Balken füllt sich entlang audio.currentTime
  //   2. Audio fertig -> Puffer-Countdown (tour.advanceAt), Balken
  //                      leert sich
  // Statt Spinner gibt es also immer eine echte, ablesbare Zeit.
  let countdownMs = $state(0);
  let audioCurrent = $state(0);
  let audioDuration = $state(0);
  let audioPlaying = $state(false);
  let tickRaf = null;

  function tick() {
    if (tour.advanceAt > 0) {
      countdownMs = Math.max(0, tour.advanceAt - Date.now());
    } else {
      countdownMs = 0;
    }
    if (audioEl) {
      audioCurrent = audioEl.currentTime || 0;
      audioDuration = audioEl.duration || 0;
      audioPlaying = !audioEl.paused && audioDuration > 0
                     && audioCurrent < audioDuration;
    }
    tickRaf = requestAnimationFrame(tick);
  }
  $effect(() => {
    if (tour.running && tour.mode === 'demo') {
      if (!tickRaf) tickRaf = requestAnimationFrame(tick);
    } else {
      if (tickRaf) { cancelAnimationFrame(tickRaf); tickRaf = null; }
      countdownMs = 0;
      audioPlaying = false;
    }
  });
  onDestroy(() => {
    if (tickRaf) cancelAnimationFrame(tickRaf);
  });

  // Was zeigen wir im Progress-Balken?
  //   - audioPlaying          -> Audio-Position (aufsteigend 0->100 %)
  //   - countdownMs > 0       -> Puffer (absteigend 100->0 %)
  //   - sonst (Fallback-Timer z.B. bei fehlendem Audio)
  //                           -> Fallback-Countdown (100->0 %)
  const progressPct = $derived.by(() => {
    if (audioPlaying && audioDuration > 0) {
      return Math.min(100, (audioCurrent / audioDuration) * 100);
    }
    if (countdownMs > 0 && tour.advanceTotal > 0) {
      return Math.min(100, (countdownMs / tour.advanceTotal) * 100);
    }
    return 0;
  });

  // Sekunden-Anzeige rechts neben dem Balken
  const timerLabel = $derived.by(() => {
    if (tour.paused) return '⏸';
    if (audioPlaying) {
      const remain = Math.max(0, audioDuration - audioCurrent);
      return `${Math.ceil(remain)}s`;
    }
    if (countdownMs > 0) return `${Math.ceil(countdownMs / 1000)}s`;
    return '';
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
      <!-- Kompakter Icon-Toggle Guided/Demo. Spart Platz und macht
           Raum für Pause/Play + Progress. Tooltip erklärt die Funktion. -->
      <button class="tour-icon-btn" onclick={toggleMode}
              title={tour.mode === 'demo'
                ? 'Tour läuft automatisch -- klicken für manuelles Weiterklicken'
                : 'Manuelles Weiterklicken -- klicken für automatischen Demo-Modus'}
              aria-label={tour.mode === 'demo'
                ? 'Auf manuell umschalten'
                : 'Auf Demo umschalten'}>
        <i class="fa-solid {tour.mode === 'demo'
                             ? 'fa-hand-pointer'
                             : 'fa-play'}"></i>
      </button>

      {#if tour.mode === 'demo'}
        <!-- Pause/Play -- eigener Button, klar abgetrennt -->
        <button class="tour-icon-btn pp-btn"
                class:is-paused={tour.paused}
                onclick={() => (tour.paused ? resumeTour() : pauseTour())}
                aria-label={tour.paused ? 'Fortsetzen' : 'Pause'}
                title={tour.paused
                  ? 'Tour pausiert -- klicken zum Fortsetzen'
                  : 'Tour pausieren'}>
          <i class="fa-solid {tour.paused ? 'fa-play' : 'fa-pause'}"></i>
        </button>

        <!-- Einheitlicher Progress-Balken: zeigt während des Vorlesens
             die Audio-Position, danach den Nachlese-Countdown. -->
        <div class="progress-box" class:is-paused={tour.paused}>
          <div class="progress-track">
            <div class="progress-fill" style="width: {progressPct}%"></div>
          </div>
          <span class="progress-label mono">{timerLabel}</span>
        </div>
      {/if}

      <div class="tour-nav">
        <button class="tour-btn"
                onclick={prevStep}
                disabled={tour.stepIndex === 0}
                title="Einen Schritt zurück (Pfeil links)">
          <i class="fa-solid fa-arrow-left"></i>
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
  /* Backdrop ohne Ziel -- voller Viewport halbtransparent.
     Kein backdrop-filter/blur: der verwischt im Tour-Spotlight
     sichtbar auch das freigestellte Ziel-Element. Nur Abdunklung. */
  .tour-backdrop.solid {
    position: fixed; inset: 0;
    background: rgba(5, 8, 12, 0.55);
    z-index: 9000;
    pointer-events: auto;
  }

  /* Backdrop mit Loch: wir rendern vier Streifen um das Loch herum,
     sodass die ausgesparte Fläche klickbar und vor allem gestochen
     scharf bleibt. */
  .tour-backdrop.has-hole {
    position: fixed; inset: 0;
    z-index: 9000;
    pointer-events: none;
  }
  .tour-backdrop.has-hole::before,
  .tour-backdrop.has-hole::after {
    content: "";
    position: fixed;
    background: rgba(5, 8, 12, 0.55);
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
    background: rgba(5, 8, 12, 0.55);
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

  /* Kompakte Icon-Buttons im Footer (Mode-Toggle, Pause/Play) */
  .tour-icon-btn {
    width: 30px; height: 30px;
    display: grid; place-items: center;
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--fg-muted);
    cursor: pointer;
    font-size: 12px;
    transition: background 120ms, color 120ms, border-color 120ms;
    flex-shrink: 0;
  }
  .tour-icon-btn:hover {
    background: var(--bg-panel);
    color: var(--accent);
    border-color: var(--border-strong);
  }
  .tour-icon-btn.pp-btn {
    color: var(--accent);
    border-color: color-mix(in oklab, var(--accent) 40%, var(--border));
    background: var(--accent-soft);
  }
  .tour-icon-btn.pp-btn.is-paused {
    color: var(--warning);
    border-color: color-mix(in oklab, var(--warning) 40%, var(--border));
    background: color-mix(in oklab, var(--warning) 14%, var(--bg-elev));
  }

  /* Fortschritts-Balken + Sekunden-Label */
  .progress-box {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .progress-track {
    flex: 1;
    height: 4px;
    background: var(--bg-sink);
    border: 1px solid var(--border);
    border-radius: 3px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: var(--accent);
    transition: width 150ms linear;
  }
  .progress-box.is-paused .progress-fill { background: var(--warning); }
  .progress-label {
    font-size: 11px;
    color: var(--fg-muted);
    min-width: 28px;
    text-align: right;
  }
  .progress-box.is-paused .progress-label { color: var(--warning); }

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
