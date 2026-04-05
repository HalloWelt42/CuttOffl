<script>
  import { onMount } from 'svelte';
  import { editor, setOutput, startRender } from '../lib/editor.svelte.js';
  import { api } from '../lib/api.js';
  import { toast } from '../lib/toast.svelte.js';

  let { open = $bindable(false) } = $props();

  let codec     = $state(editor.edl?.output?.codec || 'h264');
  let container = $state(editor.edl?.output?.container || 'mp4');
  let resolution = $state(editor.edl?.output?.resolution || 'source');
  let crf       = $state(editor.edl?.output?.crf ?? 23);
  let bitrate   = $state(editor.edl?.output?.bitrate || '');
  let useBitrate = $state(!!editor.edl?.output?.bitrate);
  let codecInfo  = $state(null);

  onMount(async () => {
    try { codecInfo = await api.systemCodecs(); } catch {}
  });

  $effect(() => {
    if (!open || !editor.edl) return;
    codec = editor.edl.output.codec;
    container = editor.edl.output.container;
    resolution = editor.edl.output.resolution;
    crf = editor.edl.output.crf ?? 23;
    bitrate = editor.edl.output.bitrate || '';
    useBitrate = !!editor.edl.output.bitrate;
  });

  const hintForCodec = $derived(() => {
    if (!codecInfo?.recommendations) return null;
    return codecInfo.recommendations.find((r) => r.codec === codec) ?? null;
  });

  const defaultRec = $derived(() =>
    codecInfo?.recommendations?.find((r) => r.default) ?? null
  );

  const stats = $derived(() => {
    const tl = editor.edl?.timeline ?? [];
    const total = tl.reduce((s, c) => s + (c.src_end - c.src_start), 0);
    const copyN = tl.filter((c) => c.mode === 'copy').length;
    const reN  = tl.filter((c) => c.mode === 'reencode').length;
    return { total, copyN, reN, count: tl.length };
  });

  async function onStart() {
    setOutput({
      codec, container, resolution,
      bitrate: useBitrate ? bitrate : null,
      crf: useBitrate ? null : Number(crf),
    });
    const jobId = await startRender();
    if (jobId) {
      toast.info('Render gestartet');
      open = false;
    }
  }
</script>

{#if open}
  <div class="backdrop" onclick={() => (open = false)} role="presentation">
    <div class="modal" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
      <header>
        <i class="fa-solid fa-film"></i>
        <h2>Rendern & Exportieren</h2>
        <button class="x" onclick={() => (open = false)} aria-label="Schließen">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </header>

      <div class="body">
        <div class="summary mono">
          <div><b>{stats().count}</b> Clips · <b>{stats().total.toFixed(2)}</b> s gesamt</div>
          <div class="dim">copy: {stats().copyN} · reencode: {stats().reN}</div>
        </div>

        <div class="row">
          <label>Codec
            <select bind:value={codec}
                    title="Videocodec für den Export. Der empfohlene Codec hängt von deinem Gerät ab.">
              <option value="h264">H.264 (weit kompatibel)</option>
              <option value="hevc">HEVC / H.265 (effizienter)</option>
            </select>
          </label>
          <label>Container
            <select bind:value={container}
                    title="Dateiformat. MP4 ist am weitesten kompatibel, MKV erlaubt mehr Codecs, MOV wird vor allem auf Apple-Systemen genutzt.">
              <option value="mp4">MP4</option>
              <option value="mkv">MKV</option>
              <option value="mov">MOV</option>
            </select>
          </label>
        </div>

        {#if codecInfo}
          <div class="codec-hint" class:is-default={hintForCodec()?.default}>
            <div class="hint-head">
              <i class="fa-solid {hintForCodec()?.default ? 'fa-bolt' : 'fa-circle-info'}"></i>
              <span class="hint-title">
                {#if hintForCodec()}
                  {hintForCodec().label}
                  {#if hintForCodec().default}
                    <span class="badge-rec">empfohlen für {codecInfo.platform.env_label}</span>
                  {/if}
                {:else}
                  Codec {codec.toUpperCase()}
                {/if}
              </span>
            </div>
            {#if hintForCodec()}
              <p class="hint-note">{hintForCodec().note}</p>
            {/if}
            {#if !hintForCodec()?.default && defaultRec()}
              <p class="hint-swap soft">
                Empfehlung für dieses Gerät:
                <button class="linklike" type="button"
                        onclick={() => (codec = defaultRec().codec)}
                        title="Zum empfohlenen Codec wechseln">
                  {defaultRec().label}
                </button>
              </p>
            {/if}
          </div>
        {/if}

        <div class="row">
          <label>Auflösung
            <select bind:value={resolution}>
              <option value="source">Quelle beibehalten</option>
              <option value="2160p">2160p (4K)</option>
              <option value="1440p">1440p</option>
              <option value="1080p">1080p</option>
              <option value="720p">720p</option>
              <option value="480p">480p</option>
            </select>
          </label>
          <label class="switch">
            <input type="checkbox" bind:checked={useBitrate} />
            <span>Bitrate statt Qualität (CRF)</span>
          </label>
        </div>

        {#if useBitrate}
          <div class="row">
            <label>Bitrate
              <input type="text" placeholder="z. B. 8M" bind:value={bitrate} />
            </label>
          </div>
        {:else}
          <div class="row">
            <label>Qualität (CRF {crf})
              <input type="range" min="14" max="32" step="1" bind:value={crf} />
            </label>
            <span class="dim small">niedriger = besser (14 sehr gut, 23 Standard, 32 klein)</span>
          </div>
        {/if}
      </div>

      <footer>
        <button onclick={() => (open = false)}>Abbrechen</button>
        <button class="primary" onclick={onStart} disabled={!stats().count}>
          <i class="fa-solid fa-play"></i> Render starten
        </button>
      </footer>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.6);
    display: grid; place-items: center;
    z-index: 1500;
    backdrop-filter: blur(2px);
  }
  .modal {
    width: min(520px, 92vw);
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
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-elev);
  }
  header i { color: var(--accent); }
  header h2 { margin: 0; font-size: 16px; flex: 1; }
  .x { background: transparent; border: none; color: var(--fg-muted); cursor: pointer; font-size: 16px; }
  .x:hover { color: var(--fg-primary); }
  .body { padding: 16px; display: flex; flex-direction: column; gap: 14px; }
  .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: end; }
  label {
    display: flex; flex-direction: column; gap: 4px;
    font-size: 12px; color: var(--fg-muted);
    flex: 1;
  }
  select, input[type="text"] {
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--border-strong);
    border-radius: 6px;
    padding: 7px 10px;
    font: inherit;
    min-width: 0;
  }
  input[type="range"] { width: 100%; }
  .switch { flex-direction: row; align-items: center; }
  .switch input { margin-right: 6px; }
  .summary {
    background: var(--bg-sink);
    padding: 10px 12px;
    border-radius: 6px;
    font-size: 13px;
  }
  .dim { color: var(--fg-muted); }
  .small { font-size: 11px; }

  .codec-hint {
    background: var(--bg-sink);
    border: 1px solid var(--border);
    border-left: 3px solid var(--fg-faint);
    border-radius: 6px;
    padding: 10px 12px;
    font-size: 12px;
  }
  .codec-hint.is-default { border-left-color: var(--accent); }
  .hint-head {
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 4px;
  }
  .hint-head i { color: var(--accent); }
  .hint-title { font-weight: 600; color: var(--fg-primary); }
  .badge-rec {
    background: var(--accent-soft);
    color: var(--accent);
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-left: 6px;
  }
  .hint-note { margin: 0; line-height: 1.5; color: var(--fg-muted); font-size: 12px; }
  .hint-swap { margin: 6px 0 0; font-size: 11px; color: var(--fg-muted); }
  .linklike {
    background: transparent; border: none; padding: 0;
    color: var(--accent); cursor: pointer; font: inherit; text-decoration: underline;
  }
  .linklike:hover { color: var(--accent-hover); }
  footer {
    padding: 12px 16px;
    border-top: 1px solid var(--border);
    display: flex; justify-content: flex-end; gap: 8px;
    background: var(--bg-sink);
  }
  footer button {
    padding: 8px 16px; border-radius: 6px; cursor: pointer;
    background: var(--bg-elev); color: var(--fg-primary);
    border: 1px solid var(--border); font: inherit;
  }
  footer button.primary { background: var(--accent); color: #0b0f14; border-color: var(--accent); font-weight: 600; }
  footer button.primary:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
