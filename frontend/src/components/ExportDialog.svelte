<script>
  // Export-Dialog -- Tabs fuer Video und Audio, Toggle-Buttons statt
  // Checkboxen, Segment-Switch fuer Qualitaet (CRF / feste Bitrate).
  // Profile-Schnellwahl und Groessenabschaetzung kommen in einem
  // weiteren Commit.

  import { onMount } from 'svelte';
  import { editor, setOutput, startRender } from '../lib/editor.svelte.js';
  import { api } from '../lib/api.js';
  import { toast } from '../lib/toast.svelte.js';

  let { open = $bindable(false) } = $props();

  // --- State (jedes Feld wird beim Oeffnen aus dem EDL gezogen) ---
  let codec         = $state(editor.edl?.output?.codec || 'h264');
  let container     = $state(editor.edl?.output?.container || 'mp4');
  let resolution    = $state(editor.edl?.output?.resolution || 'source');
  let crf           = $state(editor.edl?.output?.crf ?? 23);
  let bitrate       = $state(editor.edl?.output?.bitrate || '');
  // Qualitaetsmodus: 'crf' oder 'bitrate' (Zielgroesse kommt in C dazu)
  let qualityMode   = $state(editor.edl?.output?.bitrate ? 'bitrate' : 'crf');

  // Audio
  let audioCodec     = $state(editor.edl?.output?.audio_codec || 'aac');
  let audioBitrate   = $state(editor.edl?.output?.audio_bitrate || '160k');
  let audioNormalize = $state(!!editor.edl?.output?.audio_normalize);
  let audioMono      = $state(!!editor.edl?.output?.audio_mono);
  let audioMute      = $state(!!editor.edl?.output?.audio_mute);

  let codecInfo  = $state(null);
  let activeTab  = $state('video');   // 'video' | 'audio'

  onMount(async () => {
    try { codecInfo = await api.systemCodecs(); } catch {}
  });

  // Beim Oeffnen: EDL -> State synchronisieren
  $effect(() => {
    if (!open || !editor.edl) return;
    const o = editor.edl.output;
    codec = o.codec;
    container = o.container;
    resolution = o.resolution;
    crf = o.crf ?? 23;
    bitrate = o.bitrate || '';
    qualityMode = o.bitrate ? 'bitrate' : 'crf';
    audioCodec     = o.audio_codec || 'aac';
    audioBitrate   = o.audio_bitrate || '160k';
    audioNormalize = !!o.audio_normalize;
    audioMono      = !!o.audio_mono;
    audioMute      = !!o.audio_mute;
  });

  const hintForCodec = $derived.by(() => {
    if (!codecInfo?.recommendations) return null;
    return codecInfo.recommendations.find((r) => r.codec === codec) ?? null;
  });

  const defaultRec = $derived.by(() =>
    codecInfo?.recommendations?.find((r) => r.default) ?? null
  );

  const stats = $derived.by(() => {
    const tl = editor.edl?.timeline ?? [];
    const total = tl.reduce((s, c) => s + (c.src_end - c.src_start), 0);
    const copyN = tl.filter((c) => c.mode === 'copy').length;
    const reN   = tl.filter((c) => c.mode === 'reencode').length;
    return { total, copyN, reN, count: tl.length };
  });

  // Wenn ein Audio-Filter aktiv ist, laufen alle Clips automatisch als
  // reencode durch -- das muss sichtbar sein, damit der User versteht,
  // warum "copy" vielleicht nicht mehr greift.
  const filtersForceReencode = $derived(
    audioNormalize || audioMono || audioMute,
  );

  // --- Dropdown-Optionen ---
  const AUDIO_BITRATE_OPTIONS = [
    { v: '64k',  label: '64 kbit/s  · klein, Stimme' },
    { v: '96k',  label: '96 kbit/s  · schlank' },
    { v: '128k', label: '128 kbit/s · Standard' },
    { v: '160k', label: '160 kbit/s · gut (Default)' },
    { v: '192k', label: '192 kbit/s · sehr gut' },
    { v: '256k', label: '256 kbit/s · Musik' },
    { v: '320k', label: '320 kbit/s · Premium' },
  ];

  function crfLabel(v) {
    const n = Number(v);
    if (n <= 16) return 'Archiv';
    if (n <= 20) return 'Sehr gut';
    if (n <= 24) return 'Standard';
    if (n <= 28) return 'Web';
    return 'Klein';
  }

  async function onStart() {
    setOutput({
      codec, container, resolution,
      bitrate: qualityMode === 'bitrate' ? bitrate : null,
      crf:     qualityMode === 'crf'     ? Number(crf) : null,
      audio_codec:     audioCodec,
      audio_bitrate:   audioBitrate,
      audio_normalize: audioNormalize,
      audio_mono:      audioMono,
      audio_mute:      audioMute,
    });
    const jobId = await startRender();
    if (jobId) {
      toast.info('Render gestartet');
      open = false;
    }
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="backdrop" onclick={() => (open = false)} role="presentation">
    <div class="modal" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" tabindex="-1">
      <header>
        <i class="fa-solid fa-film"></i>
        <h2>Rendern & Exportieren</h2>
        <button class="x" onclick={() => (open = false)} aria-label="Schließen">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </header>

      <div class="summary mono">
        <div><b>{stats.count}</b> Clips · <b>{stats.total.toFixed(2)}</b> s gesamt</div>
        <div class="dim">copy: {stats.copyN} · reencode: {stats.reN}{filtersForceReencode ? ' (Audio-Filter aktiv → alles re-encodes)' : ''}</div>
      </div>

      <!-- Tab-Leiste -->
      <div class="tabs" role="tablist">
        <button class="tab" role="tab" aria-selected={activeTab === 'video'}
                class:active={activeTab === 'video'}
                onclick={() => (activeTab = 'video')}>
          <i class="fa-solid fa-film"></i> Video
        </button>
        <button class="tab" role="tab" aria-selected={activeTab === 'audio'}
                class:active={activeTab === 'audio'}
                onclick={() => (activeTab = 'audio')}>
          <i class="fa-solid fa-volume-high"></i> Audio
        </button>
      </div>

      <div class="body">
        {#if activeTab === 'video'}
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
            {@const h = hintForCodec}
            <div class="codec-hint" class:is-default={h?.default}>
              <div class="hint-head">
                <i class="fa-solid {h?.default ? 'fa-bolt' : 'fa-circle-info'}"></i>
                <span class="hint-title">
                  {#if h}
                    {h.label}
                    {#if h.default}
                      <span class="badge-rec">empfohlen für {codecInfo.platform.env_label}</span>
                    {/if}
                  {:else}
                    Codec {codec.toUpperCase()}
                  {/if}
                </span>
                {#if h?.tag}
                  <span class="hint-tag hint-tag-{h.speed ?? 'medium'}">{h.tag}</span>
                {/if}
              </div>
              {#if h}
                <p class="hint-note">{h.note}</p>
              {/if}
              {#if !h?.default && defaultRec}
                <p class="hint-swap">
                  Empfehlung für dieses Gerät:
                  <button class="linklike" type="button"
                          onclick={() => (codec = defaultRec.codec)}
                          title="Zum empfohlenen Codec wechseln">
                    {defaultRec.label}
                  </button>
                </p>
              {/if}
            </div>
          {/if}

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

          <!-- Qualitaetsmodus als Segment-Switch (kein Checkbox) -->
          <div class="seg-switch" role="group" aria-label="Qualitaetsmodus">
            <button class="seg" class:active={qualityMode === 'crf'}
                    onclick={() => (qualityMode = 'crf')}
                    title="Konstante Qualität -- Dateigröße variiert je nach Szene">
              Qualität (CRF)
            </button>
            <button class="seg" class:active={qualityMode === 'bitrate'}
                    onclick={() => (qualityMode = 'bitrate')}
                    title="Feste Bitrate -- Dateigröße vorhersehbar">
              Feste Bitrate
            </button>
          </div>

          {#if qualityMode === 'crf'}
            <label>Qualität (CRF {crf} · {crfLabel(crf)})
              <input type="range" min="14" max="32" step="1" bind:value={crf} />
              <span class="scale-ends">
                <span>14 Archiv</span><span>23 Standard</span><span>32 Klein</span>
              </span>
            </label>
          {:else}
            <label>Bitrate
              <input type="text" placeholder="z. B. 8M, 2500k" bind:value={bitrate} />
              <span class="dim small">Format: Zahl + K oder M (z. B. 8M = 8 Mbit/s)</span>
            </label>
          {/if}

        {:else if activeTab === 'audio'}
          <div class="row">
            <label>Audio-Codec
              <select bind:value={audioCodec} disabled={audioMute}>
                <option value="aac">AAC (weit kompatibel)</option>
                <option value="mp3">MP3</option>
                <option value="opus">Opus (effizienter)</option>
                <option value="copy">Quelle 1:1 übernehmen</option>
              </select>
            </label>
            <label>Bitrate
              <select bind:value={audioBitrate} disabled={audioMute || audioCodec === 'copy'}>
                {#each AUDIO_BITRATE_OPTIONS as opt (opt.v)}
                  <option value={opt.v}>{opt.label}</option>
                {/each}
              </select>
            </label>
          </div>

          <!-- Audio-Filter als Toggle-Buttons, keine Checkboxen -->
          <div class="filters">
            <div class="filters-label">Filter</div>
            <div class="filters-row">
              <button class="btn-toggle" class:is-on={audioNormalize}
                      disabled={audioMute}
                      onclick={() => (audioNormalize = !audioNormalize)}
                      title="EBU R128 loudnorm -- bringt den Pegel auf eine vergleichbare Lautheit (gut fuer Social Media). Zwingt auf reencode.">
                <i class="fa-solid fa-wave-square"></i>
                Lautheit normalisieren
              </button>
              <button class="btn-toggle" class:is-on={audioMono}
                      disabled={audioMute}
                      onclick={() => (audioMono = !audioMono)}
                      title="Stereo auf Mono herunter mischen. Spart Platz, oft besser bei Sprache. Zwingt auf reencode.">
                <i class="fa-solid fa-compact-disc"></i>
                Mono-Downmix
              </button>
              <button class="btn-toggle" class:is-on={audioMute}
                      onclick={() => (audioMute = !audioMute)}
                      title="Tonspur komplett stumm schalten -- nur Video bleibt. Zwingt auf reencode.">
                <i class="fa-solid fa-volume-xmark"></i>
                Stumm
              </button>
            </div>
            {#if filtersForceReencode}
              <p class="filter-note">
                <i class="fa-solid fa-circle-info"></i>
                Audio-Filter sind aktiv -- alle Clips werden neu kodiert,
                auch die, die sonst im verlustfreien copy-Modus laufen würden.
              </p>
            {/if}
          </div>
        {/if}
      </div>

      <footer>
        <button class="btn" onclick={() => (open = false)}>Abbrechen</button>
        <button class="btn btn-primary" onclick={onStart} disabled={!stats.count}>
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
    width: min(560px, 94vw);
    max-height: 92vh;
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
  header > i { color: var(--accent); }
  header h2 { margin: 0; font-size: 16px; flex: 1; }
  .x { background: transparent; border: none; color: var(--fg-muted); cursor: pointer; font-size: 16px; }
  .x:hover { color: var(--fg-primary); }

  .summary {
    padding: 10px 16px;
    background: var(--bg-sink);
    font-size: 13px;
    border-bottom: 1px solid var(--border);
  }
  .summary b { color: var(--fg-primary); }
  .dim { color: var(--fg-muted); }

  /* Tabs */
  .tabs {
    display: flex;
    gap: 2px;
    padding: 6px 12px 0;
    background: var(--bg-panel);
    border-bottom: 1px solid var(--border);
  }
  .tab {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 14px;
    background: transparent;
    border: none;
    color: var(--fg-muted);
    font: inherit;
    font-size: 13px;
    cursor: pointer;
    border-radius: 6px 6px 0 0;
    border-bottom: 2px solid transparent;
  }
  .tab:hover { color: var(--fg-primary); background: var(--bg-elev); }
  .tab.active {
    color: var(--accent);
    background: var(--bg-elev);
    border-bottom-color: var(--accent);
  }
  .tab i { font-size: 13px; }

  .body {
    padding: 16px;
    display: flex; flex-direction: column; gap: 14px;
    overflow-y: auto;
  }
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
  select:disabled, input[type="text"]:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  input[type="range"] { width: 100%; }
  .small { font-size: 11px; }
  .scale-ends {
    display: flex; justify-content: space-between;
    font-size: 10px; color: var(--fg-faint);
    margin-top: 2px;
  }

  /* Segment-Switch */
  .seg-switch {
    display: inline-flex;
    gap: 0;
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 2px;
    align-self: flex-start;
  }
  .seg {
    background: transparent;
    border: none;
    color: var(--fg-muted);
    padding: 6px 14px;
    cursor: pointer;
    font: inherit;
    font-size: 12px;
    border-radius: 6px;
    transition: background 120ms, color 120ms;
  }
  .seg:hover { color: var(--fg-primary); }
  .seg.active {
    background: var(--bg-panel);
    color: var(--accent);
    box-shadow: 0 1px 2px rgba(0,0,0,0.15);
    font-weight: 600;
  }

  /* Codec-Hinweis */
  .codec-hint {
    background: var(--bg-sink);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px 12px;
    font-size: 12px;
  }
  .codec-hint.is-default {
    background: var(--accent-soft);
    border-color: var(--accent);
  }
  .hint-head {
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 4px;
  }
  .hint-head i { color: var(--fg-muted); }
  .codec-hint.is-default .hint-head i { color: var(--accent); }
  .hint-title { font-weight: 600; color: var(--fg-primary); }
  .hint-tag {
    margin-left: auto;
    font-size: 10px;
    letter-spacing: 0.4px;
    padding: 2px 8px;
    border-radius: 10px;
    background: var(--bg-panel);
    color: var(--fg-muted);
    border: 1px solid var(--border);
  }
  .hint-tag-fast   { color: var(--success); border-color: color-mix(in oklab, var(--success) 35%, var(--border)); }
  .hint-tag-medium { color: var(--fg-muted); }
  .hint-tag-slow   { color: var(--warning); border-color: color-mix(in oklab, var(--warning) 35%, var(--border)); }
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

  /* Audio-Filter */
  .filters {
    display: flex; flex-direction: column; gap: 6px;
  }
  .filters-label {
    font-size: 12px; color: var(--fg-muted);
    letter-spacing: 0.3px;
  }
  .filters-row {
    display: flex; flex-wrap: wrap; gap: 6px;
  }
  .filter-note {
    display: flex; align-items: center; gap: 8px;
    margin: 6px 0 0;
    font-size: 12px;
    color: var(--fg-muted);
    padding: 6px 10px;
    background: var(--accent-soft);
    border: 1px solid color-mix(in oklab, var(--accent) 30%, var(--border));
    border-radius: 6px;
  }
  .filter-note i { color: var(--accent); }

  footer {
    padding: 12px 16px;
    border-top: 1px solid var(--border);
    display: flex; justify-content: flex-end; gap: 8px;
    background: var(--bg-sink);
  }
</style>
