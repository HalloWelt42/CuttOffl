<script>
  // Generisches verschiebbares Info-Fenster. Wird via `geometry` an einen
  // $state-Store gebunden (x, y, width, height, open). Bei mousedown auf
  // der Titelleiste laesst sich das Fenster ziehen, per SE-Griff kann es
  // in der Groesse veraendert werden. Geometrie wird ueber die mitgegebene
  // onPersist-Callback vom Parent im localStorage gesichert.
  //
  // Das "typische Blau" der Hinweisfenster: Header mit Akzent-Rand + Info-
  // Symbol. Inhalt in eigener Slot-Zone mit grosszuegiger Typografie.

  import { onMount } from 'svelte';

  let {
    geometry,
    title = 'Information',
    icon = 'fa-circle-info',
    onClose = () => {},
    onPersist = () => {},
    children,
  } = $props();

  const MIN_W = 320;
  const MIN_H = 220;

  let dragging = $state(false);
  let resizing = $state(false);
  let dragStart = { mx: 0, my: 0, x: 0, y: 0 };
  let resizeStart = { mx: 0, my: 0, w: 0, h: 0 };

  function clampInViewport() {
    const pad = 8;
    const maxX = Math.max(pad, window.innerWidth  - geometry.width  - pad);
    const maxY = Math.max(pad, window.innerHeight - geometry.height - pad);
    geometry.x = Math.max(pad, Math.min(geometry.x, maxX));
    geometry.y = Math.max(pad, Math.min(geometry.y, maxY));
  }

  function onHeaderDown(e) {
    // Nur Linksklick und nicht auf Buttons
    if (e.button !== 0) return;
    if (e.target.closest('button, input, a, select, textarea')) return;
    dragging = true;
    dragStart = { mx: e.clientX, my: e.clientY, x: geometry.x, y: geometry.y };
    window.addEventListener('mousemove', onDragMove);
    window.addEventListener('mouseup', onDragEnd);
    e.preventDefault();
  }
  function onDragMove(e) {
    if (!dragging) return;
    geometry.x = dragStart.x + (e.clientX - dragStart.mx);
    geometry.y = dragStart.y + (e.clientY - dragStart.my);
    clampInViewport();
  }
  function onDragEnd() {
    if (!dragging) return;
    dragging = false;
    window.removeEventListener('mousemove', onDragMove);
    window.removeEventListener('mouseup', onDragEnd);
    onPersist();
  }

  function onResizeDown(e) {
    if (e.button !== 0) return;
    resizing = true;
    resizeStart = { mx: e.clientX, my: e.clientY, w: geometry.width, h: geometry.height };
    window.addEventListener('mousemove', onResizeMove);
    window.addEventListener('mouseup', onResizeEnd);
    e.preventDefault();
    e.stopPropagation();
  }
  function onResizeMove(e) {
    if (!resizing) return;
    geometry.width  = Math.max(MIN_W, resizeStart.w + (e.clientX - resizeStart.mx));
    geometry.height = Math.max(MIN_H, resizeStart.h + (e.clientY - resizeStart.my));
    clampInViewport();
  }
  function onResizeEnd() {
    if (!resizing) return;
    resizing = false;
    window.removeEventListener('mousemove', onResizeMove);
    window.removeEventListener('mouseup', onResizeEnd);
    onPersist();
  }

  function onWinResize() { if (geometry.open) clampInViewport(); }

  function onKey(e) {
    if (!geometry.open) return;
    if (e.key === 'Escape') { e.preventDefault(); onClose(); }
  }

  onMount(() => {
    clampInViewport();
    window.addEventListener('resize', onWinResize);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('resize', onWinResize);
      window.removeEventListener('keydown', onKey);
    };
  });
</script>

{#if geometry.open}
  <div class="fp"
       role="dialog" aria-modal="false" aria-label={title}
       style:left="{geometry.x}px"
       style:top="{geometry.y}px"
       style:width="{geometry.width}px"
       style:height="{geometry.height}px">
    <header class="fp-head" onmousedown={onHeaderDown}
            class:is-dragging={dragging}
            title="Titelleiste greifen und ziehen, um das Fenster zu verschieben">
      <i class="fa-solid {icon} fp-icon"></i>
      <h3 class="fp-title">{title}</h3>
      <button class="fp-close" onclick={onClose}
              title="Fenster schließen (Esc)">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </header>
    <div class="fp-body">
      {@render children?.()}
    </div>
    <div class="fp-resize" onmousedown={onResizeDown}
         role="separator" aria-orientation="vertical"
         title="Unten rechts greifen und ziehen, um die Größe zu ändern">
      <i class="fa-solid fa-grip-lines-vertical"></i>
    </div>
  </div>
{/if}

<style>
  .fp {
    position: fixed;
    z-index: 1400;
    display: flex;
    flex-direction: column;
    background: var(--bg-panel);
    color: var(--fg-primary);
    border: 1px solid var(--accent);
    border-radius: 10px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45),
                0 0 0 1px color-mix(in oklab, var(--accent) 45%, transparent);
    overflow: hidden;
  }

  .fp-head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    background: color-mix(in oklab, var(--accent) 22%, var(--bg-elev));
    border-bottom: 1px solid var(--accent);
    cursor: grab;
    user-select: none;
  }
  .fp-head.is-dragging { cursor: grabbing; }
  .fp-icon { color: var(--accent); font-size: 16px; }
  .fp-title {
    flex: 1 1 auto;
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.2px;
  }
  .fp-close {
    background: transparent;
    border: none;
    color: var(--fg-muted);
    cursor: pointer;
    width: 28px;
    height: 28px;
    border-radius: 6px;
    display: grid;
    place-items: center;
    font-size: 14px;
  }
  .fp-close:hover { color: var(--fg-primary); background: var(--bg-panel); }

  .fp-body {
    flex: 1 1 auto;
    overflow: auto;
    padding: 16px 18px;
    font-size: 15px;
    line-height: 1.65;
    color: var(--fg-primary);
  }

  .fp-resize {
    position: absolute;
    right: 2px; bottom: 2px;
    width: 18px; height: 18px;
    cursor: nwse-resize;
    color: var(--fg-faint);
    display: grid;
    place-items: center;
    transform: rotate(-45deg);
    opacity: 0.6;
  }
  .fp-resize:hover { color: var(--accent); opacity: 1; }
  .fp-resize i { font-size: 12px; }
</style>
