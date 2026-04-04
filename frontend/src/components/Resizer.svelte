<script>
  let { min = 140, max = 480, value = $bindable(), side = 'left' } = $props();

  let dragging = $state(false);

  function onDown(ev) {
    ev.preventDefault();
    dragging = true;
    const start = ev.clientX;
    const startVal = value;
    function move(e) {
      const dx = e.clientX - start;
      const next = side === 'left' ? startVal + dx : startVal - dx;
      value = Math.max(min, Math.min(max, next));
    }
    function up() {
      dragging = false;
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
    }
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  }
</script>

<div
  class="resizer"
  class:dragging
  onmousedown={onDown}
  role="separator"
  aria-orientation="vertical"
></div>

<style>
  .resizer {
    width: 4px;
    cursor: col-resize;
    background: transparent;
    transition: background 120ms;
    flex: 0 0 auto;
  }
  .resizer:hover,
  .dragging { background: var(--accent); }
</style>
