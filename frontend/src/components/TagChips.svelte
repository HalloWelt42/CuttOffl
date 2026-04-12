<script>
  import { colorFor } from '../lib/tags.js';

  let {
    tags = [],
    maxShown = 0,   // 0 = alle
    onClick = null, // (tag) => void | null
  } = $props();

  const visible = $derived.by(() => {
    if (!tags || tags.length === 0) return [];
    if (maxShown > 0 && tags.length > maxShown) {
      return { list: tags.slice(0, maxShown), hidden: tags.length - maxShown };
    }
    return { list: tags, hidden: 0 };
  });
</script>

{#if tags && tags.length > 0}
  <span class="chips">
    {#each visible.list as t (t)}
      {@const c = colorFor(t)}
      <button class="chip"
              disabled={!onClick}
              onclick={(e) => { if (onClick) { e.stopPropagation(); onClick(t); } }}
              style="background: {c.bg}; color: {c.fg};"
              title={onClick ? `Nur Dateien mit Tag "${t}" zeigen` : t}>
        {t}
      </button>
    {/each}
    {#if visible.hidden > 0}
      <span class="chip more" title={tags.slice(visible.list.length).join(', ')}>
        +{visible.hidden}
      </span>
    {/if}
  </span>
{/if}

<style>
  .chips { display: inline-flex; gap: 4px; flex-wrap: wrap; }
  .chip {
    font-size: 10px;
    letter-spacing: 0.3px;
    padding: 2px 8px;
    border-radius: 10px;
    border: none;
    cursor: pointer;
    font-family: inherit;
    font-weight: 600;
    line-height: 1.4;
    max-width: 160px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .chip:disabled { cursor: default; }
  .chip:not(:disabled):hover { filter: brightness(1.1); }
  .chip.more {
    background: var(--bg-elev);
    color: var(--fg-muted);
    border: 1px solid var(--border);
  }
</style>
