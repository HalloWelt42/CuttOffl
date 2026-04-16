<script>
  // Footer-Status-Leiste: fuer jeden ueberwachten Dienst eine LED mit
  // Farb-Punkt und sprechendem Namen. Beim Hover zeigt der Browser den
  // Detail-Tooltip (title-Attribut). Eine Farbe pro level:
  //   ok      gruen    -- Dienst ist einsatzbereit
  //   warn    gelb     -- funktioniert eingeschraenkt, Aufmerksamkeit nicht zwingend
  //   err     rot      -- Dienst ausgefallen oder nicht eingerichtet
  //   unknown grau     -- Status wird noch ermittelt

  import { onMount } from 'svelte';
  import { health, startHealth } from '../lib/health.svelte.js';

  // feste Reihenfolge, damit die LEDs nicht springen
  const order = ['backend', 'ws', 'transcription'];
  const items = $derived(order.map((k) => health[k]).filter(Boolean));

  onMount(() => { startHealth(); });
</script>

<div class="leds" role="group" aria-label="Dienste-Status">
  {#each items as s (s.key)}
    <span class="led lvl-{s.level}"
          title="{s.label}: {s.detail}">
      <span class="dot"></span>
      <span class="lbl">{s.label}</span>
    </span>
  {/each}
</div>

<style>
  .leds {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .led {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 2px 8px 2px 6px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--bg-panel);
    font-size: 11px;
    color: var(--fg-muted);
    line-height: 1.4;
    cursor: help;
  }
  .led .dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--fg-faint);
    box-shadow: 0 0 0 0 currentColor;
  }
  .led .lbl { font-weight: 500; }

  .lvl-ok .dot {
    background: var(--success);
    box-shadow: 0 0 6px color-mix(in oklab, var(--success) 50%, transparent);
  }
  .lvl-warn .dot {
    background: var(--warning);
    box-shadow: 0 0 6px color-mix(in oklab, var(--warning) 50%, transparent);
  }
  .lvl-err .dot {
    background: var(--danger);
    box-shadow: 0 0 6px color-mix(in oklab, var(--danger) 55%, transparent);
    animation: pulse-err 2s ease-in-out infinite;
  }
  .lvl-unknown .dot {
    background: var(--fg-faint);
  }
  @keyframes pulse-err {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.55; }
  }

  .lvl-ok  .lbl { color: var(--fg-primary); }
  .lvl-err .lbl { color: var(--danger); }
</style>
