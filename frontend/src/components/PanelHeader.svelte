<script>
  let {
    icon = null,
    iconImg = null,   // Alternative zu fa-Icon: SVG/PNG-Pfad (aus /public)
    title, subtitle = null, children,
  } = $props();
</script>

<header class="ph">
  <div class="left">
    {#if iconImg}
      <img class="ph-img" src={iconImg} alt="" aria-hidden="true" />
    {:else if icon}
      <i class="fa-solid {icon}"></i>
    {/if}
    <div class="titles">
      <span class="title">{title}</span>
      {#if subtitle}<span class="subtitle soft">{subtitle}</span>{/if}
    </div>
  </div>
  <div class="right">
    {@render children?.()}
  </div>
</header>

<style>
  .ph {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-panel);
    gap: 12px;
    min-height: 44px;
  }
  .left { display: flex; align-items: center; gap: 10px; }
  .left i { color: var(--accent); }
  .ph-img { width: 22px; height: 22px; object-fit: contain; flex-shrink: 0; }
  .titles { display: flex; flex-direction: column; line-height: 1.1; }
  .title { font-weight: 600; letter-spacing: 0.2px; }
  .subtitle { font-size: 11px; color: var(--fg-muted); }
  .right { display: flex; align-items: center; gap: 8px; }
</style>
