<script>
  import { onMount, tick } from 'svelte';
  import { dialog, dialogOk, dialogCancel } from '../lib/dialog.svelte.js';

  // Bewusst KEINE $state() -- nur DOM-Ref für focus(), nicht reaktiv.
  // svelte-ignore non_reactive_update
  let inputEl;

  $effect(() => {
    if (dialog.open && dialog.kind === 'prompt') {
      tick().then(() => inputEl?.focus());
    }
  });

  function onKey(e) {
    if (!dialog.open) return;
    if (e.key === 'Escape') { e.preventDefault(); dialogCancel(); }
    else if (e.key === 'Enter' && dialog.kind !== 'prompt') {
      e.preventDefault();
      dialogOk();
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    dialogOk();
  }

  onMount(() => {
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });
</script>

{#if dialog.open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="backdrop" role="presentation" onclick={dialogCancel}>
    <!-- Modal: Fokus landet durch Focus-Management auf dem Input/Button,
         Esc wird global abgefangen. tabindex="-1" macht den Container
         programmgesteuert fokussierbar. -->
    <div class="modal" role="dialog" aria-modal="true" tabindex="-1"
         aria-labelledby="dialog-title"
         onclick={(e) => e.stopPropagation()}>
      <header>
        <i class="fa-solid {dialog.kind === 'alert' ? 'fa-circle-info' :
                             dialog.kind === 'prompt' ? 'fa-keyboard' :
                             'fa-circle-question'}"></i>
        <h2 id="dialog-title">{dialog.title}</h2>
        <button class="x" onclick={dialogCancel}
                aria-label="Schließen" title="Dialog schließen (Esc)">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </header>

      <form onsubmit={onSubmit}>
        <div class="body">
          <p class="msg">{dialog.message}</p>
          {#if dialog.kind === 'prompt'}
            <input
              type="text"
              bind:this={inputEl}
              bind:value={dialog.value}
              placeholder={dialog.placeholder}
              autocomplete="off"
              spellcheck="false"
            />
          {/if}
        </div>
        <footer>
          {#if dialog.cancelLabel}
            <button type="button" class="btn" onclick={dialogCancel}>
              {dialog.cancelLabel}
            </button>
          {/if}
          <button type="submit"
                  class="btn {dialog.okVariant === 'danger' ? 'btn-danger' : 'btn-primary'}">
            {dialog.okLabel}
          </button>
        </footer>
      </form>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.6);
    backdrop-filter: blur(2px);
    display: grid; place-items: center;
    z-index: 1600;
  }
  .modal {
    width: min(460px, 92vw);
    background: var(--bg-panel);
    color: var(--fg-primary);
    border: 1px solid var(--border-strong);
    border-radius: 10px;
    box-shadow: var(--shadow-md);
    display: flex; flex-direction: column;
    overflow: hidden;
  }
  header {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 14px;
    background: var(--bg-elev);
    border-bottom: 1px solid var(--border);
  }
  header > i { color: var(--accent); font-size: 16px; }
  header h2 { margin: 0; font-size: 15px; flex: 1; }
  .x {
    background: transparent; border: none; color: var(--fg-muted);
    cursor: pointer; padding: 4px 8px; border-radius: 4px;
  }
  .x:hover { color: var(--fg-primary); background: var(--bg-panel); }
  .body { padding: 16px 16px 4px; }
  .msg { margin: 0 0 10px; line-height: 1.55; font-size: 14px; }
  .body input {
    width: 100%;
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--border-strong);
    border-radius: 6px;
    padding: 8px 10px;
    font: inherit;
  }
  .body input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-soft);
  }
  footer {
    padding: 12px 14px;
    display: flex; justify-content: flex-end; gap: 8px;
    background: var(--bg-sink);
    border-top: 1px solid var(--border);
  }
  .btn-danger { background: var(--danger); color: #fff; border-color: var(--danger); font-weight: 600; }
  .btn-danger:hover { filter: brightness(1.1); color: #fff; }
</style>
