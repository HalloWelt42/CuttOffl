<script>
  import { onMount } from 'svelte';

  let { children } = $props();
  let error = $state(null);

  // Harmlose Browser-Warnungen ausfiltern
  const IGNORE = [
    /ResizeObserver loop/i,
    /ResizeObserver loop completed with undelivered notifications/i,
  ];
  const shouldIgnore = (msg) => !!msg && IGNORE.some((re) => re.test(msg));

  onMount(() => {
    const onErr = (e) => {
      const msg = e?.error?.message || e?.message || String(e);
      if (shouldIgnore(msg)) return;
      error = msg;
    };
    const onRej = (e) => {
      const msg = e?.reason?.message || String(e?.reason);
      if (shouldIgnore(msg)) return;
      error = msg;
    };
    window.addEventListener('error', onErr);
    window.addEventListener('unhandledrejection', onRej);
    return () => {
      window.removeEventListener('error', onErr);
      window.removeEventListener('unhandledrejection', onRej);
    };
  });
</script>

{#if error}
  <div class="err">
    <i class="fa-solid fa-triangle-exclamation"></i>
    <div>
      <div class="title">Oh -- ein Fehler ist aufgetreten.</div>
      <div class="msg mono">{error}</div>
    </div>
    <button onclick={() => (error = null)}>Weiter</button>
  </div>
{/if}
{@render children?.()}

<style>
  .err {
    position: fixed;
    left: 50%;
    top: 16px;
    transform: translateX(-50%);
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--danger);
    padding: 10px 14px;
    border-radius: 8px;
    box-shadow: var(--shadow-md);
    display: flex;
    gap: 12px;
    align-items: center;
    z-index: 2000;
    max-width: 80vw;
  }
  .title { font-weight: 600; margin-bottom: 2px; }
  .msg { font-size: 12px; color: var(--fg-muted); max-width: 640px; }
  button {
    background: var(--accent);
    color: #0b0f14;
    border: none;
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
  }
</style>
