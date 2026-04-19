<script>
  // Audio-Kachel fuer audio-only-Dateien in der Bibliothek.
  //
  // Zeigt die Waveform als statische SVG-Polyline. Kein Hover-Scrub
  // (Audio hat keine Frames); stattdessen nur ein Musik-Icon oben
  // rechts als Kennzeichnung.

  import { api } from '../lib/api.js';

  let {
    fileId,
    alt = '',
    hasWaveform = false,
  } = $props();

  // Waveform-JSON: { peaks: [0..1, ...], samples, rate }
  // Downsampling auf eine feste Anzahl Punkte fuer die SVG-Darstellung
  // -- 160 reicht fuer eine kompakte Kachel, sonst wird das SVG gross.
  const TARGET_POINTS = 160;

  let wf = $state(null);
  let loading = $state(false);
  let loadError = $state(false);

  async function ensureLoaded() {
    if (!hasWaveform || wf || loading || loadError) return;
    loading = true;
    try {
      const data = await api.waveform(fileId);
      wf = data;
    } catch {
      loadError = true;
    } finally {
      loading = false;
    }
  }

  // Downsample peaks -> 2*TARGET_POINTS polyline-Koordinaten (oben+unten)
  const polyline = $derived.by(() => {
    const peaks = wf?.peaks;
    if (!Array.isArray(peaks) || peaks.length === 0) return '';
    const n = peaks.length;
    const step = Math.max(1, Math.floor(n / TARGET_POINTS));
    const reduced = [];
    for (let i = 0; i < n; i += step) {
      let max = 0;
      for (let j = 0; j < step && i + j < n; j++) {
        const v = Math.abs(peaks[i + j]);
        if (v > max) max = v;
      }
      reduced.push(max);
    }
    // Polygon von links nach rechts auf der Oberkante,
    // rechts nach links auf der Unterkante -> gefuelltes Band.
    const w = 100, h = 40, mid = h / 2;
    const top = reduced.map((v, i) => {
      const x = (i / (reduced.length - 1 || 1)) * w;
      const y = mid - v * mid;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    });
    const bot = reduced.map((v, i) => {
      const idx = reduced.length - 1 - i;
      const x = (idx / (reduced.length - 1 || 1)) * w;
      const y = mid + reduced[idx] * mid;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    });
    return [...top, ...bot].join(' ');
  });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="audio-thumb" role="presentation" onmouseenter={ensureLoaded}
     aria-label={alt}>
  {#if hasWaveform && polyline}
    <svg viewBox="0 0 100 40" preserveAspectRatio="none" class="wf">
      <polygon points={polyline} />
    </svg>
  {:else if loading}
    <i class="fa-solid fa-circle-notch fa-spin placeholder" aria-hidden="true"></i>
  {:else}
    <i class="fa-solid fa-music placeholder" aria-hidden="true"></i>
  {/if}
  <span class="chip"><i class="fa-solid fa-music"></i> Audio</span>
</div>

<style>
  .audio-thumb {
    position: relative;
    width: 100%;
    height: 100%;
    background: var(--bg-sink);
    display: grid;
    place-items: center;
    color: var(--fg-faint);
    overflow: hidden;
  }
  .wf {
    width: 100%;
    height: 100%;
    display: block;
  }
  .wf polygon {
    fill: var(--accent);
    opacity: 0.7;
  }
  .placeholder { font-size: 28px; }
  .chip {
    position: absolute;
    top: 6px;
    left: 6px;
    padding: 2px 8px;
    border-radius: 4px;
    background: rgba(0, 0, 0, 0.55);
    color: var(--fg-primary);
    font-size: 10px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }
  .chip i { margin-right: 4px; }
</style>
