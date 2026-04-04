<script>
  import { onMount } from 'svelte';
  import { ui, closeThanks } from '../lib/ui.svelte.js';
  import { toast } from '../lib/toast.svelte.js';
  import { CRYPTO, KOFI_URL } from '../lib/meta.js';

  let activeCrypto = $state(null);
  let copied = $state(null);

  async function copyAddress(addr) {
    try {
      await navigator.clipboard.writeText(addr);
      copied = addr;
      toast.success('Adresse in die Zwischenablage kopiert');
      setTimeout(() => { copied = null; }, 2000);
    } catch {
      toast.error('Kopieren fehlgeschlagen');
    }
  }

  function onKey(e) {
    if (ui.thanksOpen && e.key === 'Escape') closeThanks();
  }

  onMount(() => {
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });
</script>

{#if ui.thanksOpen}
  <div class="backdrop" role="presentation" onclick={closeThanks}>
    <div class="modal" role="dialog" aria-modal="true"
         aria-labelledby="thanks-title"
         onclick={(e) => e.stopPropagation()}>
      <header>
        <div class="badge"><i class="fa-solid fa-heart"></i></div>
        <div class="titles">
          <h2 id="thanks-title">Danke!</h2>
          <span class="soft sub">Freiwillige Unterstützung für die Weiterentwicklung</span>
        </div>
        <button class="close" onclick={closeThanks}
                aria-label="Schließen" title="Dialog schließen (Esc)">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </header>

      <div class="body">
        <p class="intro">
          Schön, dass dir CuttOffl gefällt. Wenn du die Weiterentwicklung
          unterstützen möchtest: gerne, rein freiwillig, in jeder Höhe.
        </p>

        <a href={KOFI_URL} target="_blank" rel="noopener"
           class="btn btn-primary kofi"
           title="Ko-fi-Seite in neuem Tab öffnen">
          <i class="fa-solid fa-mug-hot"></i>
          Auf Ko-fi unterstützen
        </a>

        <div class="divider"><span></span><em class="soft">oder per Kryptowährung</em><span></span></div>

        <div class="crypto-cards">
          {#each CRYPTO as c (c.id)}
            <button
              class="crypto-card" class:active={activeCrypto === c.id}
              onclick={() => (activeCrypto = activeCrypto === c.id ? null : c.id)}
              title={`${c.label} (${c.symbol}) einblenden`}
            >
              <div class="crypto-icon" style="--cc: {c.color}">
                <i class={c.icon}></i>
              </div>
              <span class="crypto-symbol mono">{c.symbol}</span>
              <span class="crypto-label soft">{c.label}</span>
            </button>
          {/each}
        </div>

        {#each CRYPTO as c (c.id)}
          {#if activeCrypto === c.id}
            <div class="crypto-detail">
              <span class="label soft">{c.label}-Adresse</span>
              <code class="address mono">{c.address}</code>
              <button class="btn" onclick={() => copyAddress(c.address)}
                      title="Adresse in die Zwischenablage kopieren">
                <i class="fa-solid {copied === c.address ? 'fa-check' : 'fa-copy'}"></i>
                {copied === c.address ? 'Kopiert' : 'Adresse kopieren'}
              </button>
            </div>
          {/if}
        {/each}

        <p class="foot soft">
          <i class="fa-solid fa-heart"></i>
          Jeder Beitrag -- und sei es nur ein „Danke" -- hilft weiterzumachen.
        </p>
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed; inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(3px);
    display: grid; place-items: center;
    z-index: 1500;
    animation: fadein 140ms ease-out;
  }
  @keyframes fadein { from { opacity: 0 } to { opacity: 1 } }

  .modal {
    width: min(560px, 94vw);
    max-height: 90vh;
    background: var(--bg-panel);
    color: var(--fg-primary);
    border: 1px solid var(--border-strong);
    border-radius: 12px;
    box-shadow: var(--shadow-md);
    display: flex; flex-direction: column;
    overflow: hidden;
  }
  header {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 16px;
    background: var(--bg-elev);
    border-bottom: 1px solid var(--border);
  }
  .badge {
    width: 36px; height: 36px; border-radius: 50%;
    display: grid; place-items: center;
    background: var(--bg-panel);
    color: var(--danger);
    font-size: 16px;
    border: 1px solid var(--border);
    flex: 0 0 auto;
  }
  .titles { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  h2 { margin: 0; font-size: 18px; }
  .sub { font-size: 11px; color: var(--fg-muted); }
  .close {
    background: transparent; border: none; color: var(--fg-muted);
    cursor: pointer; padding: 4px 8px; border-radius: 4px;
    font-size: 16px;
  }
  .close:hover { color: var(--fg-primary); background: var(--bg-panel); }

  .body {
    padding: 18px 20px 20px;
    display: flex; flex-direction: column; gap: 14px;
    overflow: auto;
  }
  .intro { margin: 0; font-size: 13px; line-height: 1.55; color: var(--fg-muted); }
  .kofi { align-self: center; height: 40px; padding: 0 22px; font-size: 13px; }

  .divider {
    display: grid; grid-template-columns: 1fr auto 1fr;
    align-items: center; gap: 10px;
    color: var(--fg-faint);
    font-size: 11px;
    letter-spacing: 0.5px;
  }
  .divider span { height: 1px; background: var(--border); }
  .divider em { font-style: normal; }

  .crypto-cards {
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }
  .crypto-card {
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 8px;
    display: flex; flex-direction: column; align-items: center; gap: 4px;
    cursor: pointer; font: inherit;
    transition: border-color 120ms, background 120ms, transform 120ms;
  }
  .crypto-card:hover { border-color: var(--border-strong); transform: translateY(-1px); }
  .crypto-card.active { border-color: var(--accent); background: var(--accent-soft); }
  .crypto-icon {
    width: 40px; height: 40px; border-radius: 50%;
    background: var(--bg-panel);
    display: grid; place-items: center;
    font-size: 20px;
    color: var(--cc);
  }
  .crypto-symbol { font-weight: 700; font-size: 12px; }
  .crypto-label { font-size: 11px; color: var(--fg-muted); }

  .crypto-detail {
    padding: 12px;
    background: var(--bg-sink);
    border: 1px solid var(--border);
    border-radius: 8px;
    display: flex; flex-direction: column; gap: 8px;
  }
  .label {
    font-size: 11px; letter-spacing: 1px; text-transform: uppercase;
    color: var(--fg-muted);
  }
  .address {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 11px;
    color: var(--fg-primary);
    word-break: break-all;
    user-select: all;
  }
  .foot {
    text-align: center;
    font-size: 12px;
    color: var(--fg-muted);
    margin: 4px 0 0;
  }
  .foot i { color: var(--danger); margin-right: 4px; }
</style>
