<script>
  import { onMount } from 'svelte';

  let { open = $bindable(false), src = '', title = '' } = $props();

  // svelte-ignore non_reactive_update
  let videoEl;

  $effect(() => {
    if (open && videoEl) {
      videoEl.currentTime = 0;
      videoEl.play?.().catch(() => {});
    }
  });

  function close() {
    if (videoEl) { videoEl.pause?.(); }
    open = false;
  }

  function onKey(e) {
    if (!open) return;
    if (e.key === 'Escape') { e.preventDefault(); close(); }
    else if (e.key === ' ' && videoEl) {
      e.preventDefault();
      if (videoEl.paused) videoEl.play(); else videoEl.pause();
    }
  }

  onMount(() => {
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="backdrop" role="presentation" onclick={close}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="frame" role="dialog" aria-modal="true" tabindex="-1"
         onclick={(e) => e.stopPropagation()}>
      <header>
        <div class="title" title={title}>{title}</div>
        <button class="x" onclick={close}
                aria-label="Schließen" title="Schließen (Esc)">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </header>
      <div class="player-wrap">
        {#key src}
          <video
            bind:this={videoEl}
            src={src}
            controls
            preload="auto"
          >
            <track kind="captions" />
          </video>
        {/key}
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.8);
    backdrop-filter: blur(4px);
    display: grid; place-items: center;
    z-index: 1700;
  }
  .frame {
    width: min(1100px, 96vw);
    max-height: 92vh;
    background: var(--bg-panel);
    border: 1px solid var(--border-strong);
    border-radius: 10px;
    overflow: hidden;
    display: flex; flex-direction: column;
    box-shadow: var(--shadow-md);
  }
  header {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 14px;
    background: var(--bg-elev);
    border-bottom: 1px solid var(--border);
  }
  .title {
    flex: 1 1 auto; min-width: 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    font-weight: 600;
    font-size: 14px;
  }
  .x {
    background: transparent; border: none; color: var(--fg-muted);
    cursor: pointer; padding: 4px 8px; border-radius: 4px;
  }
  .x:hover { color: var(--fg-primary); background: var(--bg-panel); }
  .player-wrap {
    flex: 1 1 auto;
    background: #000;
    display: grid; place-items: center;
    min-height: 0;
  }
  video {
    max-width: 100%;
    max-height: 80vh;
    display: block;
  }
</style>
