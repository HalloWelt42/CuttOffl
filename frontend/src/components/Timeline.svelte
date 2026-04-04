<script>
  import { onMount } from 'svelte';
  import { editor, seek, selectClip, setClipRange } from '../lib/editor.svelte.js';

  let canvas;
  let wrap;
  let width = $state(800);
  let dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;

  // Farben aus CSS-Variablen ziehen (einmalig beim Render)
  function cssVar(name, fallback) {
    if (typeof window === 'undefined') return fallback;
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  // Zoom = Pixel pro Sekunde
  let pxPerSec = $state(40);
  let scrollX = $state(0);

  // Drag-State (scrubben oder Clip-Kanten verschieben)
  let drag = null;

  // Layout-Konstanten
  const RULER_H    = 22;
  const KEYFRAME_H = 10;
  const FILM_H     = 44;     // Thumbnail-Streifen
  const WAVE_H     = 36;     // Waveform-Band
  const CLIP_H     = 38;
  const GAP        = 4;

  const filmY   = RULER_H + GAP + KEYFRAME_H + GAP;
  const waveY   = filmY + FILM_H + GAP;
  const clipY   = waveY + WAVE_H + GAP;
  const height  = clipY + CLIP_H + GAP;

  function totalPx() { return Math.max(width, editor.duration * pxPerSec + 20); }
  function timeAtX(x) { return Math.max(0, (x + scrollX) / pxPerSec); }
  function xAtTime(t) { return t * pxPerSec - scrollX; }

  function measure() {
    if (!wrap) return;
    width = wrap.clientWidth;
    dpr = window.devicePixelRatio || 1;
    canvas.width  = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width  = width + 'px';
    canvas.style.height = height + 'px';
    render();
  }

  function render() {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    // Hintergrund
    ctx.fillStyle = '#0b0f14';
    ctx.fillRect(0, 0, width, height);

    drawRuler(ctx);
    drawKeyframes(ctx);
    drawFilmstrip(ctx);
    drawWaveform(ctx);
    drawClips(ctx);
    drawPlayhead(ctx);
  }

  function drawRuler(ctx) {
    ctx.fillStyle = '#1a2431';
    ctx.fillRect(0, 0, width, RULER_H);
    ctx.strokeStyle = '#2a3a4f';
    ctx.beginPath(); ctx.moveTo(0, RULER_H); ctx.lineTo(width, RULER_H); ctx.stroke();

    const tickStep = pickTickStep();
    ctx.fillStyle = '#5f6b7a';
    ctx.font = '11px "JetBrains Mono", ui-monospace, monospace';
    const tStart = Math.floor(scrollX / pxPerSec / tickStep) * tickStep;
    for (let t = tStart; t <= scrollX / pxPerSec + width / pxPerSec; t += tickStep) {
      const x = xAtTime(t);
      if (x < -20 || x > width + 20) continue;
      ctx.strokeStyle = '#2a3a4f';
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, RULER_H); ctx.stroke();
      ctx.fillText(fmtT(t), x + 3, 14);
    }
  }

  function drawKeyframes(ctx) {
    const y = RULER_H + GAP;
    ctx.fillStyle = '#0f1924';
    ctx.fillRect(0, y, width, KEYFRAME_H);
    ctx.fillStyle = cssVar('--kf-color', '#cfa06b');
    for (const kf of editor.keyframes) {
      const x = xAtTime(kf);
      if (x < -2 || x > width + 2) continue;
      ctx.fillRect(x - 0.5, y + 1, 1, KEYFRAME_H - 2);
    }
  }

  function drawFilmstrip(ctx) {
    // Band-Hintergrund
    ctx.fillStyle = '#07101a';
    ctx.fillRect(0, filmY, width, FILM_H);

    const meta = editor.spriteMeta;
    const img = editor.spriteImage;
    if (!meta || !img) {
      // Platzhalter
      ctx.fillStyle = '#1a2431';
      for (let x = 0; x < width; x += 160) {
        ctx.fillRect(x + 2, filmY + 2, 156, FILM_H - 4);
      }
      ctx.fillStyle = '#5f6b7a';
      ctx.font = '11px "JetBrains Mono", monospace';
      ctx.fillText(editor.file ? 'Vorschau-Streifen wird erzeugt...' : '', 8, filmY + FILM_H / 2 + 4);
      return;
    }

    // Jede Sekunde berechnen: welcher Tile-Index? Dest-Höhe = FILM_H
    // Dest-Breite so, dass Aspect beibehalten wird.
    const destH = FILM_H;
    const destW = destH * (meta.tile_w / meta.tile_h);

    // Iteration nach Tile-Indizes, die im sichtbaren Bereich liegen
    const tStart = scrollX / pxPerSec;
    const tEnd   = tStart + width / pxPerSec;
    const iStart = Math.max(0, Math.floor(tStart / meta.interval));
    const iEnd   = Math.min(meta.count - 1, Math.ceil(tEnd / meta.interval));

    for (let i = iStart; i <= iEnd; i++) {
      const t = i * meta.interval;
      const x = xAtTime(t);
      const col = i % meta.cols;
      const row = Math.floor(i / meta.cols);
      const sx = col * meta.tile_w;
      const sy = row * meta.tile_h;
      ctx.drawImage(
        img,
        sx, sy, meta.tile_w, meta.tile_h,
        x, filmY, destW, destH,
      );
    }

    // Schatten-Linien an Tile-Grenzen für Lesbarkeit
    ctx.strokeStyle = 'rgba(0,0,0,0.35)';
    ctx.lineWidth = 1;
    for (let i = iStart; i <= iEnd + 1; i++) {
      const x = xAtTime(i * meta.interval);
      ctx.beginPath(); ctx.moveTo(x, filmY); ctx.lineTo(x, filmY + FILM_H); ctx.stroke();
    }
  }

  function drawWaveform(ctx) {
    // Band-Hintergrund
    ctx.fillStyle = '#0a141e';
    ctx.fillRect(0, waveY, width, WAVE_H);
    ctx.strokeStyle = '#1e2a39';
    ctx.beginPath();
    ctx.moveTo(0, waveY + WAVE_H / 2); ctx.lineTo(width, waveY + WAVE_H / 2);
    ctx.stroke();

    const wf = editor.waveform;
    if (!wf || !wf.peaks || !wf.peaks.length) return;

    const sps = wf.samples_per_second;
    const mid = waveY + WAVE_H / 2;
    const maxH = (WAVE_H / 2) - 2;
    const tStart = scrollX / pxPerSec;
    const tEnd   = tStart + width / pxPerSec;

    // Pro Pixel einen Peak-Bucket
    ctx.fillStyle = cssVar('--wave-color', '#f59e0b');
    for (let x = 0; x < width; x++) {
      const tA = tStart + x / pxPerSec;
      const tB = tStart + (x + 1) / pxPerSec;
      if (tA > editor.duration) break;
      const iA = Math.max(0, Math.floor(tA * sps));
      const iB = Math.min(wf.peaks.length - 1, Math.ceil(tB * sps));
      let peak = 0;
      for (let i = iA; i <= iB; i++) {
        const v = wf.peaks[i];
        if (v > peak) peak = v;
      }
      const h = Math.max(1, Math.round(peak * maxH));
      ctx.fillRect(x, mid - h, 1, h * 2);
    }
  }

  function drawClips(ctx) {
    for (const c of editor.edl?.timeline ?? []) {
      const x0 = xAtTime(c.src_start);
      const x1 = xAtTime(c.src_end);
      const w = Math.max(2, x1 - x0);
      const selected = editor.selectedClipId === c.id;
      const playing = editor.playingClipId === c.id;
      ctx.fillStyle = c.mode === 'copy'
        ? cssVar('--clip-copy', '#0d9488')
        : cssVar('--clip-reencode', '#6366f1');
      ctx.fillRect(x0, clipY, w, CLIP_H);
      if (playing) {
        ctx.fillStyle = 'rgba(234,179,8,0.30)';
        ctx.fillRect(x0, clipY, w, CLIP_H);
      }
      ctx.strokeStyle = playing
        ? cssVar('--playing', '#eab308')
        : (selected ? cssVar('--accent', '#38bdf8') : 'rgba(255,255,255,0.15)');
      ctx.lineWidth = (playing || selected) ? 2 : 1;
      ctx.strokeRect(x0 + 0.5, clipY + 0.5, w - 1, CLIP_H - 1);
      ctx.fillStyle = '#e5eaf0';
      ctx.font = '11px "Chakra Petch", system-ui';
      ctx.save();
      ctx.beginPath();
      ctx.rect(x0 + 4, clipY, w - 8, CLIP_H);
      ctx.clip();
      ctx.fillText(`${c.mode} · ${(c.src_end - c.src_start).toFixed(2)}s`, x0 + 6, clipY + 15);
      ctx.fillStyle = '#c7d2fe';
      ctx.fillText(`${c.src_start.toFixed(2)} → ${c.src_end.toFixed(2)}`, x0 + 6, clipY + 30);
      ctx.restore();
      ctx.fillStyle = 'rgba(255,255,255,0.25)';
      ctx.fillRect(x0, clipY, 3, CLIP_H);
      ctx.fillRect(x1 - 3, clipY, 3, CLIP_H);
    }
  }

  function drawPlayhead(ctx) {
    const fps = editor.file?.fps || 25;
    const tol = 1 / fps;
    const onKF = editor.keyframes.some((k) => Math.abs(k - editor.playhead) <= tol);
    const playColor = onKF
      ? cssVar('--playhead-kf', '#22c55e')
      : cssVar('--playhead', '#f472b6');
    const px = xAtTime(editor.playhead);
    ctx.strokeStyle = playColor;
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, height); ctx.stroke();
    ctx.fillStyle = playColor;
    ctx.beginPath();
    ctx.moveTo(px - 5, 0); ctx.lineTo(px + 5, 0); ctx.lineTo(px, 8); ctx.closePath();
    ctx.fill();
  }

  function pickTickStep() {
    const sec = 80 / pxPerSec;
    const steps = [0.1, 0.2, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600];
    for (const s of steps) if (s >= sec) return s;
    return 1200;
  }

  function fmtT(t) {
    if (t < 0) t = 0;
    const m = Math.floor(t / 60);
    const s = t - m * 60;
    if (pxPerSec >= 60) return `${m}:${s.toFixed(1).padStart(4, '0')}`;
    return `${m}:${String(Math.floor(s)).padStart(2, '0')}`;
  }

  // Re-render bei Zustandsaenderungen
  $effect(() => {
    editor.playhead; editor.duration; editor.keyframes;
    editor.edl?.timeline; editor.selectedClipId; editor.playingClipId;
    editor.spriteMeta; editor.spriteImage; editor.waveform;
    scrollX; pxPerSec; width;
    render();
  });

  // Auto-Follow: smoothes Mitlaufen. Ab 2/3 von links wird sanft nachgezogen;
  // wenn der Playhead abrupt (z.B. via Seek) weit rausspringt, wird er geholt.
  // userInteracting pausiert Follow fuer 500ms nach Scroll/Drag/Wheel.
  let userInteracting = $state(false);
  let followPauseTimer = 0;
  let rafId = 0;

  function pauseFollow() {
    userInteracting = true;
    clearTimeout(followPauseTimer);
    followPauseTimer = setTimeout(() => { userInteracting = false; }, 500);
  }

  function followTick() {
    rafId = 0;
    if (!editor.followOn || userInteracting) {
      if (editor.isPlaying || editor.preview) rafId = requestAnimationFrame(followTick);
      return;
    }
    if (!editor.isPlaying && !editor.preview) return;

    const w   = width;
    const pps = pxPerSec;
    const tot = totalPx();
    if (w <= 0 || tot <= 0) {
      rafId = requestAnimationFrame(followTick);
      return;
    }

    const px = editor.playhead * pps;
    const anchor = w / 3;                    // Ziel: Playhead bei 1/3 von links
    const target = Math.max(0, Math.min(tot - w, px - anchor));

    const curLead = px - scrollX;            // Abstand Playhead vom linken Rand
    const farAway =
      curLead < 0 || curLead > w + 200;      // Seek oder weit daneben -> springen

    if (farAway) {
      scrollX = target;
    } else if (curLead > w * (2 / 3)) {
      // im letzten Drittel: sanft nachziehen
      const delta = target - scrollX;
      if (Math.abs(delta) < 0.5) scrollX = target;
      else scrollX += delta * 0.18;           // easing-Faktor
    }

    rafId = requestAnimationFrame(followTick);
  }

  $effect(() => {
    const playing = editor.isPlaying;
    const preview = editor.preview;
    const follow  = editor.followOn;
    if ((playing || preview) && follow && !rafId) {
      rafId = requestAnimationFrame(followTick);
    }
  });

  // --- Interaktion ---

  function hitClip(x, y) {
    if (y < clipY || y > clipY + CLIP_H) return null;
    for (const c of (editor.edl?.timeline ?? [])) {
      const x0 = xAtTime(c.src_start);
      const x1 = xAtTime(c.src_end);
      if (x >= x0 && x <= x1) {
        let edge = null;
        if (x - x0 < 6) edge = 'start';
        else if (x1 - x < 6) edge = 'end';
        return { clip: c, edge };
      }
    }
    return null;
  }

  function onPointerDown(ev) {
    const r = canvas.getBoundingClientRect();
    const x = ev.clientX - r.left;
    const y = ev.clientY - r.top;

    const hit = hitClip(x, y);
    if (hit) {
      selectClip(hit.clip.id);
      if (hit.edge) {
        drag = {
          kind: 'trim', edge: hit.edge, clipId: hit.clip.id,
          origStart: hit.clip.src_start, origEnd: hit.clip.src_end,
          startX: x,
        };
        pauseFollow();
        canvas.setPointerCapture?.(ev.pointerId);
        return;
      }
    } else {
      selectClip(null);
    }

    // Scrub
    seek(timeAtX(x));
    drag = { kind: 'scrub' };
    pauseFollow();
    canvas.setPointerCapture?.(ev.pointerId);
  }

  function onPointerMove(ev) {
    if (!drag) return;
    const r = canvas.getBoundingClientRect();
    const x = ev.clientX - r.left;
    const t = timeAtX(x);
    if (drag.kind === 'scrub') {
      seek(t);
    } else if (drag.kind === 'trim') {
      const c = editor.edl.timeline.find((x) => x.id === drag.clipId);
      if (!c) return;
      if (drag.edge === 'start') {
        const ns = Math.min(c.src_end - 0.1, Math.max(0, t));
        c.src_start = Number(ns.toFixed(3));
      } else {
        const ne = Math.max(c.src_start + 0.1, Math.min(editor.duration, t));
        c.src_end = Number(ne.toFixed(3));
      }
    }
  }

  function onPointerUp() {
    if (drag?.kind === 'trim') {
      const c = editor.edl.timeline.find((x) => x.id === drag.clipId);
      if (c) setClipRange(c.id, c.src_start, c.src_end);
    }
    drag = null;
    pauseFollow();
  }

  function onWheel(ev) {
    pauseFollow();
    if (ev.ctrlKey || ev.metaKey) {
      ev.preventDefault();
      const r = canvas.getBoundingClientRect();
      const x = ev.clientX - r.left;
      const focusT = timeAtX(x);
      const factor = ev.deltaY < 0 ? 1.25 : 0.8;
      pxPerSec = Math.max(4, Math.min(400, pxPerSec * factor));
      scrollX = Math.max(0, focusT * pxPerSec - x);
    } else {
      scrollX = Math.max(0, Math.min(totalPx() - width, scrollX + ev.deltaX + ev.deltaY));
    }
  }

  onMount(() => {
    measure();
    let raf = 0;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(measure);
    });
    ro.observe(wrap);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  });
</script>

<div class="tl" bind:this={wrap}>
  <canvas
    bind:this={canvas}
    onpointerdown={onPointerDown}
    onpointermove={onPointerMove}
    onpointerup={onPointerUp}
    onpointercancel={onPointerUp}
    onwheel={onWheel}
  ></canvas>
</div>

<style>
  .tl {
    flex: 0 0 auto;
    background: var(--bg-panel);
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
  }
  canvas {
    display: block;
    cursor: crosshair;
  }
</style>
