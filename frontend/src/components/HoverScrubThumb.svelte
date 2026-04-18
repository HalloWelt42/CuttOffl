<script>
  // Thumbnail-Kachel mit Hover-Scrub:
  // Beim Ueberfahren wird die Sprite-Grafik geladen und an der Mausposition
  // das passende Tile gezeigt -- wie ein schneller Preview ohne Player.

  import { api } from '../lib/api.js';

  let {
    fileId,
    alt = '',
    hasThumb = false,
    hasSprite = false,
  } = $props();

  let hostEl;
  let hovering = $state(false);
  let meta = $state(null);        // {tile_w, tile_h, cols, rows, count}
  let loading = $state(false);
  let tileIndex = $state(0);      // aktueller Frame-Index (0..count-1)

  // Background-Size ist cols*100% x rows*100% damit ein Tile über das
  // Element-Rechteck passt. Position wird als Prozentsatz relativ zum
  // Tile-Raster berechnet (ohne Pixelmathe am Sprite).
  const bgStyle = $derived.by(() => {
    if (!meta || !hovering || meta.count <= 0) return '';
    const col = tileIndex % meta.cols;
    const row = Math.floor(tileIndex / meta.cols);
    const xPct = meta.cols > 1 ? (col / (meta.cols - 1)) * 100 : 0;
    const yPct = meta.rows > 1 ? (row / (meta.rows - 1)) * 100 : 0;
    return `
      background-image: url(${api.spriteUrl(fileId)});
      background-size: ${meta.cols * 100}% ${meta.rows * 100}%;
      background-position: ${xPct}% ${yPct}%;
      background-repeat: no-repeat;
    `;
  });

  async function ensureMeta() {
    if (meta || !hasSprite || loading) return;
    loading = true;
    try {
      meta = await api.spriteMeta(fileId);
    } catch {
      meta = null;
    } finally {
      loading = false;
    }
  }

  function onEnter() {
    hovering = true;
    ensureMeta();
  }
  function onLeave() {
    hovering = false;
    tileIndex = 0;
  }
  function onMove(e) {
    if (!meta || meta.count <= 0) return;
    const rect = hostEl.getBoundingClientRect();
    if (rect.width <= 0) return;
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    const frac = x / rect.width;
    const idx = Math.min(meta.count - 1, Math.max(0, Math.floor(frac * meta.count)));
    tileIndex = idx;
  }
</script>

<div
  bind:this={hostEl}
  class="scrub"
  class:active={hovering && meta}
  onmouseenter={onEnter}
  onmouseleave={onLeave}
  onmousemove={onMove}
  style={bgStyle}
  role="presentation"
>
  {#if !(hovering && meta)}
    {#if hasThumb}
      <img src={api.thumbUrl(fileId)} {alt} />
    {:else}
      <i class="fa-solid fa-image placeholder"></i>
    {/if}
  {/if}
  {#if hovering && meta && meta.count > 1}
    <div class="scrub-bar">
      <div class="scrub-bar-fill"
           style:width="{((tileIndex + 1) / meta.count) * 100}%">
      </div>
    </div>
  {/if}
</div>

<style>
  .scrub {
    position: relative;
    width: 100%;
    height: 100%;
    background: var(--bg-sink);
    display: grid;
    place-items: center;
    color: var(--fg-faint);
    overflow: hidden;
  }
  .scrub img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .scrub.active { background-color: var(--bg-sink); }
  .placeholder { font-size: 28px; }

  .scrub-bar {
    position: absolute;
    left: 0; right: 0; bottom: 0;
    height: 3px;
    background: rgba(0,0,0,0.4);
    pointer-events: none;
  }
  .scrub-bar-fill {
    height: 100%;
    background: var(--accent);
    transition: width 40ms linear;
  }
</style>
