<script>
  import PanelHeader from '../components/PanelHeader.svelte';
  import { toast } from '../lib/toast.svelte.js';

  let activeCrypto = $state(null);
  let copied = $state(null);

  const cryptos = [
    { id: 'btc',  label: 'Bitcoin',  symbol: 'BTC',  icon: 'fa-brands fa-bitcoin', color: '#f7931a',
      address: 'bc1qnd599khdkv3v3npmj9ufxzf6h4fzanny2acwqr' },
    { id: 'doge', label: 'Dogecoin', symbol: 'DOGE', icon: 'fa-solid fa-dog',      color: '#c3a634',
      address: 'DL7tuiYCqm3xQjMDXChdxeQxqUGMACn1ZV' },
    { id: 'eth',  label: 'Ethereum', symbol: 'ETH',  icon: 'fa-brands fa-ethereum', color: '#627eea',
      address: '0x8A28fc47bFFFA03C8f685fa0836E2dBe1CA14F27' },
  ];

  function selectCrypto(id) {
    activeCrypto = activeCrypto === id ? null : id;
  }

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
</script>

<section class="wrap">
  <PanelHeader icon="fa-heart" title="Danke & Über" subtitle="Projekt, Lizenz und Unterstützung" />

  <div class="body">
    <div class="card block intro">
      <div class="intro-icon"><i class="fa-solid fa-heart"></i></div>
      <h2>Danke, dass du CuttOffl nutzt!</h2>
      <p class="soft">
        CuttOffl ist ein kleines, selbstgehostetes Werkzeug, um Videos schnell und
        sauber zu schneiden. Offline, lokal, ohne Cloud, ohne Konto. Wenn dir das
        Programm hilft und du den Aufwand wertschätzen möchtest, kannst du die
        Weiterentwicklung mit einer Spende unterstützen. Das ist rein freiwillig.
      </p>
    </div>

    <div class="card block">
      <h3><i class="fa-solid fa-mug-hot"></i> Einen Kaffee spendieren</h3>
      <p class="soft">
        Am einfachsten geht es über Ko-fi. Beliebiger Betrag, keine Anmeldung nötig.
      </p>
      <a href="https://ko-fi.com/HalloWelt42" target="_blank" rel="noopener"
         class="btn btn-primary kofi"
         title="Ko-fi-Seite in neuem Tab öffnen">
        <i class="fa-solid fa-mug-hot"></i>
        Auf Ko-fi unterstützen
      </a>
    </div>

    <div class="card block">
      <h3><i class="fa-solid fa-bitcoin-sign"></i> Kryptowährung</h3>
      <p class="soft">Alternativ direkt per Wallet. Auf eine Karte klicken zum Einblenden der Adresse.</p>
      <div class="crypto-cards">
        {#each cryptos as c (c.id)}
          <button
            class="crypto-card" class:active={activeCrypto === c.id}
            onclick={() => selectCrypto(c.id)}
            title={`${c.label} (${c.symbol}) einblenden`}
          >
            <div class="crypto-icon" style="--cc: {c.color}">
              <i class={c.icon}></i>
            </div>
            <span class="crypto-symbol">{c.symbol}</span>
            <span class="crypto-label soft">{c.label}</span>
          </button>
        {/each}
      </div>

      {#each cryptos as c (c.id)}
        {#if activeCrypto === c.id}
          <div class="crypto-detail">
            <div class="detail-row">
              <span class="label soft">{c.label}-Adresse</span>
            </div>
            <code class="address mono">{c.address}</code>
            <button class="btn" onclick={() => copyAddress(c.address)}
                    title="Adresse in die Zwischenablage kopieren">
              <i class="fa-solid {copied === c.address ? 'fa-check' : 'fa-copy'}"></i>
              {copied === c.address ? 'Kopiert' : 'Adresse kopieren'}
            </button>
          </div>
        {/if}
      {/each}
    </div>

    <div class="card block">
      <h3><i class="fa-solid fa-file-contract"></i> Lizenz</h3>
      <p>
        CuttOffl steht unter der <b>Nicht-kommerziellen Lizenz v2.0</b>,
        basierend auf Creative Commons CC BY-NC-ND 4.0 mit Zusatzbestimmungen
        des Rechteinhabers (private Modifikation erlaubt, keine öffentliche
        Weiterverteilung).
      </p>
      <p class="soft">
        Den vollständigen Lizenztext findest du in der Datei
        <code>LICENSE</code> im Projekt-Repository.
      </p>
    </div>

    <div class="card block">
      <h3><i class="fa-solid fa-triangle-exclamation"></i> Haftungsausschluss</h3>
      <p class="soft">
        Die Software wird ohne Mängelgewähr bereitgestellt. Es wird keine Gewähr
        übernommen für Richtigkeit, Vollständigkeit oder Eignung für einen
        bestimmten Zweck. Jegliche Nutzung erfolgt auf eigenes Risiko. Der
        Rechteinhaber haftet nicht für direkte oder indirekte Schäden, die durch
        die Nutzung oder Nichtnutzbarkeit der Software entstehen.
      </p>
    </div>

    <div class="card block">
      <h3><i class="fa-brands fa-github"></i> Projekt</h3>
      <p class="soft">
        Quellcode, Dokumentation und Issues:
      </p>
      <a class="btn" href="https://github.com/HalloWelt42/CuttOffl"
         target="_blank" rel="noopener"
         title="CuttOffl-Repository auf GitHub öffnen">
        <i class="fa-brands fa-github"></i>
        github.com/HalloWelt42/CuttOffl
      </a>
    </div>
  </div>
</section>

<style>
  .wrap { display: flex; flex-direction: column; height: 100%; }
  .body {
    padding: 24px;
    overflow: auto;
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 760px;
  }
  .block { padding: 18px; }
  .block h2 { margin: 8px 0 6px; font-size: 18px; }
  .block h3 {
    margin: 0 0 10px; font-size: 14px; color: var(--fg-primary);
    display: flex; align-items: center; gap: 8px;
  }
  .block h3 i { color: var(--accent); }
  .block p { margin: 0 0 10px; line-height: 1.6; font-size: 13px; color: var(--fg-muted); }
  .block p b { color: var(--fg-primary); }

  .intro { text-align: center; padding: 24px; }
  .intro-icon {
    width: 56px; height: 56px; border-radius: 50%;
    background: var(--bg-elev);
    display: grid; place-items: center; margin: 0 auto 10px;
    color: var(--danger);
    font-size: 22px;
    border: 1px solid var(--border);
  }

  .kofi { padding: 0 22px; height: 38px; font-size: 13px; }

  .crypto-cards {
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 10px; margin: 8px 0 4px;
  }
  .crypto-card {
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 8px;
    display: flex; flex-direction: column; align-items: center; gap: 6px;
    cursor: pointer; font: inherit;
    transition: border-color 120ms, background 120ms, transform 120ms;
  }
  .crypto-card:hover { border-color: var(--border-strong); transform: translateY(-1px); }
  .crypto-card.active { border-color: var(--accent); background: var(--accent-soft); }
  .crypto-icon {
    width: 44px; height: 44px; border-radius: 50%;
    background: var(--bg-panel);
    display: grid; place-items: center;
    font-size: 22px;
    color: var(--cc);
  }
  .crypto-symbol { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 12px; }
  .crypto-label { font-size: 11px; color: var(--fg-muted); }

  .crypto-detail {
    margin-top: 12px;
    padding: 12px;
    background: var(--bg-sink);
    border: 1px solid var(--border);
    border-radius: 8px;
    display: flex; flex-direction: column; gap: 8px;
  }
  .crypto-detail .label {
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
  code {
    background: var(--bg-elev);
    padding: 1px 5px;
    border-radius: 3px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
  }
</style>
