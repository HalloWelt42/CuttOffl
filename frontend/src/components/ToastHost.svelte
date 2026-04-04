<script>
  import { toasts, dismiss } from '../lib/toast.svelte.js';

  const ICONS = {
    success: 'fa-circle-check',
    info:    'fa-circle-info',
    warning: 'fa-triangle-exclamation',
    error:   'fa-circle-xmark',
  };
</script>

<div class="toast-host" aria-live="polite">
  {#each toasts.list as t (t.id)}
    <div class="toast {t.kind}" role="status">
      <i class="fa-solid {ICONS[t.kind] ?? 'fa-circle-info'}"></i>
      <span class="msg">{t.msg}</span>
      <button class="close" onclick={() => dismiss(t.id)} aria-label="Schließen">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>
  {/each}
</div>

<style>
  .toast-host {
    position: fixed;
    bottom: 72px;
    right: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    z-index: 1000;
    pointer-events: none;
  }
  .toast {
    pointer-events: auto;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    min-width: 280px;
    max-width: 420px;
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--border-strong);
    border-left: 3px solid var(--accent);
    border-radius: 8px;
    box-shadow: var(--shadow-md);
    font-size: 13px;
  }
  .toast.success { border-left-color: var(--success); }
  .toast.warning { border-left-color: var(--warning); }
  .toast.error   { border-left-color: var(--danger); }
  .toast.info    { border-left-color: var(--info); }
  .msg { flex: 1; line-height: 1.35; }
  .close {
    background: transparent;
    color: var(--fg-muted);
    border: none;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
  }
  .close:hover { color: var(--fg-primary); background: var(--bg-panel); }
</style>
