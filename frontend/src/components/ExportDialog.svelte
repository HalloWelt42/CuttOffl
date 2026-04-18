<script>
  // Export-Dialog -- Tabs für Profil / Video / Audio, Toggle-Buttons
  // statt Checkboxen, Segment-Switch für Qualität (CRF / feste
  // Bitrate). Profile-Schnellwahl und Größen-Abschätzung sind in
  // Renderer B dazugekommen.

  import { onMount, untrack } from 'svelte';
  import { editor, setOutput, startRender, cancelRender } from '../lib/editor.svelte.js';
  import { api } from '../lib/api.js';
  import { toast } from '../lib/toast.svelte.js';
  import {
    RENDER_PRESETS,
    estimateFilesizeBytes,
    estimateVideoBitrateKbps,
    parseBitrateKbps,
    formatBytes,
  } from '../lib/renderPresets.js';

  let { open = $bindable(false) } = $props();

  // --- State (jedes Feld wird beim Öffnen aus dem EDL gezogen) ---
  let codec         = $state(editor.edl?.output?.codec || 'h264');
  let container     = $state(editor.edl?.output?.container || 'mp4');
  let resolution    = $state(editor.edl?.output?.resolution || 'source');
  let crf           = $state(editor.edl?.output?.crf ?? 23);
  let bitrate       = $state(editor.edl?.output?.bitrate || '');
  // qualityMode: 'crf' | 'bitrate' | 'size' -- size rechnet eine
  // Ziel-Bitrate aus der gewünschten Dateigröße aus.
  let qualityMode   = $state(editor.edl?.output?.bitrate ? 'bitrate' : 'crf');
  let targetSizeMb  = $state(50);  // Default für Zielgrößen-Modus

  // Audio
  let audioCodec     = $state(editor.edl?.output?.audio_codec || 'aac');
  let audioBitrate   = $state(editor.edl?.output?.audio_bitrate || '160k');
  let audioNormalize = $state(!!editor.edl?.output?.audio_normalize);
  let audioMono      = $state(!!editor.edl?.output?.audio_mono);
  let audioMute      = $state(!!editor.edl?.output?.audio_mute);

  let codecInfo      = $state(null);
  let activeTab      = $state('profile');   // 'profile' | 'video' | 'audio'
  let activePresetId = $state(null);

  onMount(async () => {
    try { codecInfo = await api.systemCodecs(); } catch {}
  });

  // Beim Öffnen: EDL -> State synchronisieren. WICHTIG: untrack um
  // den Inhalt des Lesens, sonst wird der Effect bei jeder EDL-
  // Änderung erneut ausgeführt und setzt qualityMode zurück --
  // der Segment-Switch ließe sich dadurch nicht mehr umschalten.
  $effect(() => {
    if (!open) return;
    untrack(() => {
      if (!editor.edl) return;
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
      // Wenn der aktuelle Profil-Satz exakt einem Preset entspricht,
      // markieren wir das -- sonst bleibt die Karte passiv.
      activePresetId = matchPreset();
    });
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

  // Wenn Zielgrößen-Modus aktiv: Bitrate aus (MB - Audio) / Dauer
  // rechnen. 8192 = 8 bit/Byte * 1024 (kbit/MB). Mit etwas Puffer
  // für Container-Overhead (~2 %) auf die sichere Seite.
  const sizeBasedBitrateK = $derived.by(() => {
    const dur = stats.total;
    if (!dur || dur <= 0) return 0;
    const totalKbitsAvail = (targetSizeMb * 8192) / 1.02;
    const audioKbps = audioMute ? 0 : parseBitrateKbps(audioBitrate);
    const videoKbps = Math.max(200, totalKbitsAvail / dur - audioKbps);
    return Math.round(videoKbps);
  });
  const sizeBasedBitrateStr = $derived(`${sizeBasedBitrateK}k`);

  // Aktueller OutputProfile-Snapshot für Abschätzungen + Preset-
  // Abgleich. Neu berechnet, wenn eines der Felder sich ändert.
  const currentProfile = $derived({
    codec, container, resolution,
    bitrate: qualityMode === 'bitrate' ? bitrate
           : qualityMode === 'size'    ? sizeBasedBitrateStr
           : null,
    crf:     qualityMode === 'crf'     ? Number(crf) : null,
    audio_codec:     audioCodec,
    audio_bitrate:   audioBitrate,
    audio_normalize: audioNormalize,
    audio_mono:      audioMono,
    audio_mute:      audioMute,
  });

  // Größe schätzen -- Hausnummer, keine Messung.
  const estimatedBytes = $derived(
    estimateFilesizeBytes(currentProfile, stats.total),
  );
  const estimatedLabel = $derived(formatBytes(estimatedBytes));
  const videoMbps = $derived(
    (estimateVideoBitrateKbps(currentProfile) / 1000).toFixed(
      estimateVideoBitrateKbps(currentProfile) >= 10_000 ? 0 : 1
    )
  );
  const audioKbps = $derived(
    audioMute ? 0 : parseBitrateKbps(audioBitrate),
  );

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

  function applyPreset(preset) {
    const p = preset.profile;
    codec = p.codec;
    container = p.container;
    resolution = p.resolution;
    if (p.bitrate) {
      bitrate = p.bitrate;
      qualityMode = 'bitrate';
    } else {
      bitrate = '';
      crf = p.crf;
      qualityMode = 'crf';
    }
    audioCodec     = p.audio_codec;
    audioBitrate   = p.audio_bitrate;
    audioNormalize = p.audio_normalize;
    audioMono      = p.audio_mono;
    audioMute      = p.audio_mute;
    activePresetId = preset.id;
  }

  // Haben die aktuellen Felder genau die Werte eines bekannten
  // Presets? -> Id zurückgeben. Nützlich für die Karten-Markierung.
  // Im Zielgrößen-Modus matcht bewusst nie ein Preset, weil die
  // Bitrate dort aus Dauer und MB berechnet ist.
  function matchPreset() {
    if (qualityMode === 'size') return null;
    for (const preset of RENDER_PRESETS) {
      const p = preset.profile;
      const same =
        p.codec === codec &&
        p.container === container &&
        p.resolution === resolution &&
        (p.bitrate ?? null) === (qualityMode === 'bitrate' ? (bitrate || null) : null) &&
        (p.crf ?? null) === (qualityMode === 'crf' ? Number(crf) : null) &&
        p.audio_codec === audioCodec &&
        p.audio_bitrate === audioBitrate &&
        p.audio_normalize === audioNormalize &&
        p.audio_mono === audioMono &&
        p.audio_mute === audioMute;
      if (same) return preset.id;
    }
    return null;
  }

  // Bei jeder Änderung im Dialog: aktive Preset-Markierung aktualisieren.
  $effect(() => {
    // eslint-disable-next-line no-unused-expressions
    codec; container; resolution; crf; bitrate; qualityMode;
    audioCodec; audioBitrate; audioNormalize; audioMono; audioMute;
    activePresetId = matchPreset();
  });

  async function onStart() {
    setOutput(currentProfile);
    // Reset der Rendering-View-Felder, damit alte Einträge aus einem
    // vorherigen Render nicht durchblitzen.
    editor.renderInfo = null;
    editor.renderHistory = [];
    editor.renderLastStep = null;
    editor.renderProgress = 0;
    editor.renderPhase = 'queued';
    editor.renderStartedAt = Date.now();
    const jobId = await startRender();
    if (jobId) {
      editor.renderJobId = jobId;
      toast.info('Render gestartet');
      // Dialog bleibt offen -- wechselt in die Rendering-View.
    }
  }

  // Formatiert Millisekunden-Deltas als "0:12 min" / "1:34 min".
  function fmtDelta(ms) {
    const s = Math.max(0, Math.round(ms / 1000));
    const mm = Math.floor(s / 60);
    const ss = s % 60;
    return `${mm}:${String(ss).padStart(2, '0')} min`;
  }

  // Dauer seit Render-Start als tickender Zähler. Nur aktiv, solange
  // der Dialog in der Rendering-View steht.
  let now = $state(Date.now());
  let tickHandle = null;
  $effect(() => {
    if (editor.rendering && editor.renderStartedAt) {
      if (tickHandle) clearInterval(tickHandle);
      tickHandle = setInterval(() => { now = Date.now(); }, 500);
      return () => { if (tickHandle) { clearInterval(tickHandle); tickHandle = null; } };
    }
    if (tickHandle) { clearInterval(tickHandle); tickHandle = null; }
  });

  const elapsedMs = $derived(
    editor.renderStartedAt ? (now - editor.renderStartedAt) : 0,
  );
  const etaMs = $derived.by(() => {
    const p = editor.renderProgress || 0;
    if (p <= 0.01 || p >= 0.999) return 0;
    return (elapsedMs / p) * (1 - p);
  });

  const STEP_LABELS = {
    preparing: 'Vorbereiten',
    encoding_clip: 'Clip kodieren',
    clip_done: 'Clip fertig',
    merging: 'Zusammenfügen',
    done: 'Fertig',
    cancelled: 'Abgebrochen',
    failed: 'Fehler',
  };

  async function onCancel() {
    await cancelRender();
  }

  function onClose() {
    // Dialog schließen -- wenn ein Render noch läuft, läuft der im
    // Hintergrund weiter. Das ist Absicht; der Render-Status bleibt
    // im Footer-Fortschrittsbalken sichtbar.
    open = false;
  }

  // Wenn der Render-Abschluss reinkommt, bleibt der Dialog offen und
  // zeigt das Ergebnis (done / failed / cancelled). Der User sieht
  // die komplette Pipeline und kann dann selbst schließen.
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="backdrop" onclick={onClose} role="presentation">
    <div class="modal" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" tabindex="-1">
      <header>
        <i class="fa-solid {editor.rendering ? 'fa-circle-notch fa-spin' : 'fa-film'}"></i>
        <h2>
          {#if editor.rendering}
            Rendern läuft
          {:else if editor.renderPhase === 'done'}
            Render fertig
          {:else if editor.renderPhase === 'failed'}
            Render fehlgeschlagen
          {:else if editor.renderPhase === 'cancelled'}
            Render abgebrochen
          {:else}
            Rendern & Exportieren
          {/if}
        </h2>
        <button class="x" onclick={onClose} aria-label="Schließen">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </header>

      {#if editor.rendering || ['done', 'failed', 'cancelled'].includes(editor.renderPhase)}
        <!-- Rendering-View: bleibt offen, zeigt Pipeline + Log + Zeiten -->
        <div class="render-body">
          <div class="render-progress">
            <div class="progress-track">
              <div class="progress-fill"
                   class:is-done={editor.renderPhase === 'done'}
                   class:is-failed={editor.renderPhase === 'failed'}
                   class:is-cancelled={editor.renderPhase === 'cancelled'}
                   style="width: {((editor.renderProgress || 0) * 100).toFixed(1)}%"></div>
            </div>
            <div class="progress-meta mono">
              <span class="pct">{((editor.renderProgress || 0) * 100).toFixed(1)} %</span>
              {#if editor.renderInfo?.clip_index}
                <span class="dim">
                  · Clip {editor.renderInfo.clip_index}/{editor.renderInfo.clip_total}
                </span>
              {/if}
              <span class="dim">· Zeit {fmtDelta(elapsedMs)}</span>
              {#if etaMs > 0 && editor.rendering}
                <span class="dim">· ETA {fmtDelta(etaMs)}</span>
              {/if}
            </div>
          </div>

          <!-- Aktueller Status in einem prominenten Label -->
          <div class="current-step" data-phase={editor.renderPhase}>
            <i class="fa-solid {editor.renderPhase === 'done' ? 'fa-circle-check'
                              : editor.renderPhase === 'failed' ? 'fa-circle-exclamation'
                              : editor.renderPhase === 'cancelled' ? 'fa-ban'
                              : 'fa-gears fa-spin'}"></i>
            <div class="current-text">
              <div class="current-title">
                {#if editor.renderInfo?.step}
                  {STEP_LABELS[editor.renderInfo.step] ?? editor.renderInfo.step}
                {:else if editor.renderPhase === 'queued'}
                  In der Warteschlange
                {:else if editor.renderPhase === 'done'}
                  Fertig
                {:else if editor.renderPhase === 'failed'}
                  Fehlgeschlagen
                {:else if editor.renderPhase === 'cancelled'}
                  Abgebrochen
                {:else}
                  Rendern
                {/if}
              </div>
              {#if editor.renderInfo?.note}
                <div class="current-note mono">{editor.renderInfo.note}</div>
              {/if}
            </div>
          </div>

          <!-- Pipeline-History -->
          {#if editor.renderHistory.length > 0}
            <div class="pipeline">
              <div class="pipeline-label">Pipeline</div>
              <ul class="pipeline-list mono">
                {#each editor.renderHistory as h (h.t)}
                  <li>
                    <span class="p-time">
                      {#if editor.renderStartedAt}
                        +{fmtDelta(h.t - editor.renderStartedAt)}
                      {/if}
                    </span>
                    <span class="p-step">{STEP_LABELS[h.step] ?? h.step}</span>
                    <span class="p-note dim">{h.note}</span>
                  </li>
                {/each}
              </ul>
            </div>
          {/if}
        </div>

        <footer class="render-footer">
          {#if editor.rendering}
            <button class="btn btn-danger" onclick={onCancel}>
              <i class="fa-solid fa-stop"></i> Abbrechen
            </button>
            <button class="btn" onclick={onClose} title="Dialog schließen -- Render läuft im Hintergrund weiter">
              Schließen
            </button>
          {:else}
            <button class="btn btn-primary" onclick={onClose}>
              <i class="fa-solid fa-check"></i> Schließen
            </button>
          {/if}
        </footer>
      {:else}
        <div class="summary mono">
          <div><b>{stats.count}</b> Clips · <b>{stats.total.toFixed(2)}</b> s gesamt</div>
          <div class="dim">copy: {stats.copyN} · reencode: {stats.reN}{filtersForceReencode ? ' (Audio-Filter aktiv → alles re-encodes)' : ''}</div>
        </div>

      <!-- Tab-Leiste -->
      <div class="tabs" role="tablist">
        <button class="tab" role="tab" aria-selected={activeTab === 'profile'}
                class:active={activeTab === 'profile'}
                onclick={() => (activeTab = 'profile')}>
          <i class="fa-solid fa-sliders"></i> Profil
        </button>
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
        {#if activeTab === 'profile'}
          <div class="presets-label">
            Schnellwahl -- ein Klick setzt passende Video- und Audio-Werte.
            In den Tabs <i class="fa-solid fa-film"></i> <b>Video</b> und
            <i class="fa-solid fa-volume-high"></i> <b>Audio</b> lassen sich
            die Werte danach feintunen.
          </div>
          <div class="presets-grid">
            {#each RENDER_PRESETS as preset (preset.id)}
              <button class="preset" class:is-active={activePresetId === preset.id}
                      onclick={() => applyPreset(preset)}
                      title={preset.hint ?? preset.note}>
                <i class={preset.icon} style:color={preset.color}></i>
                <div class="preset-body">
                  <div class="preset-title">{preset.title}</div>
                  <div class="preset-note">{preset.note}</div>
                </div>
                {#if activePresetId === preset.id}
                  <i class="fa-solid fa-check check"></i>
                {/if}
              </button>
            {/each}
          </div>
          {#if activePresetId}
            {@const active = RENDER_PRESETS.find((p) => p.id === activePresetId)}
            {#if active?.hint}
              <div class="preset-hint">
                <i class="fa-solid fa-circle-info"></i>
                <span>{active.hint}</span>
              </div>
            {/if}
          {/if}

        {:else if activeTab === 'video'}
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

          <!-- Qualitätsmodus als Segment-Switch (kein Checkbox) -->
          <div class="seg-switch" role="group" aria-label="Qualitätsmodus">
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
            <button class="seg" class:active={qualityMode === 'size'}
                    onclick={() => (qualityMode = 'size')}
                    title="Zielgröße -- passende Bitrate wird aus Dauer und Audio berechnet">
              Zielgröße
            </button>
          </div>

          {#if qualityMode === 'crf'}
            <label>Qualität (CRF {crf} · {crfLabel(crf)})
              <input type="range" min="14" max="32" step="1" bind:value={crf} />
              <span class="scale-ends">
                <span>14 Archiv</span><span>23 Standard</span><span>32 Klein</span>
              </span>
            </label>
          {:else if qualityMode === 'bitrate'}
            <label>Bitrate
              <input type="text" placeholder="z. B. 8M, 2500k" bind:value={bitrate} />
              <span class="dim small">Format: Zahl + K oder M (z. B. 8M = 8 Mbit/s)</span>
            </label>
          {:else}
            <label>Zielgröße (MB)
              <input type="number" min="1" max="10000" step="1" bind:value={targetSizeMb} />
              <span class="dim small">
                Berechnete Video-Bitrate: <b>{sizeBasedBitrateK} kbit/s</b>
                {#if sizeBasedBitrateK <= 400}
                  · sehr knapp, Qualität kann sichtbar leiden
                {:else if sizeBasedBitrateK <= 1000}
                  · sparsam
                {:else if sizeBasedBitrateK <= 5000}
                  · okay für Web
                {:else}
                  · reichlich
                {/if}
              </span>
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
                      title="EBU R128 loudnorm -- bringt den Pegel auf eine vergleichbare Lautheit (gut für Social Media). Zwingt auf reencode.">
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

      <!-- Abschätzung direkt über dem Footer -->
      <div class="estimate mono" title="Grobschätzung der Dateigröße. Je nach Bildmaterial kann das Ergebnis 20-30 % abweichen.">
        <i class="fa-solid fa-weight-hanging"></i>
        <span class="est-label">Circa</span>
        <span class="est-size">{estimatedLabel}</span>
        <span class="dim">
          · Video {videoMbps} Mbit/s
          {#if audioKbps > 0}
            · Audio {audioKbps} kbit/s
          {:else if audioMute}
            · kein Ton
          {/if}
        </span>
      </div>

      <footer>
        <button class="btn" onclick={() => (open = false)}>Abbrechen</button>
        <button class="btn btn-primary" onclick={onStart} disabled={!stats.count}>
          <i class="fa-solid fa-play"></i> Render starten
        </button>
      </footer>
      {/if}
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
    width: min(820px, 96vw);
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

  /* Presets */
  .presets-label {
    font-size: 12px;
    color: var(--fg-muted);
    line-height: 1.55;
  }
  .presets-label b { color: var(--fg-primary); font-weight: 600; }
  .presets-label i { color: var(--accent); }
  .presets-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 8px;
  }
  .preset {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 14px;
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--fg-primary);
    cursor: pointer;
    font: inherit;
    text-align: left;
    transition: background 120ms, border-color 120ms;
    position: relative;
  }
  .preset:hover { background: var(--bg-panel); border-color: var(--border-strong); }
  .preset.is-active {
    background: var(--accent-soft);
    border-color: var(--accent);
  }
  .preset > i:first-child {
    font-size: 22px;
    width: 30px;
    flex: 0 0 auto;
    text-align: center;
    /* Farbe kommt aus preset.color per inline style:color */
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.3));
  }
  .preset-body { flex: 1; min-width: 0; }
  .preset-title { font-weight: 600; font-size: 13px; }
  .preset-note {
    font-size: 11px;
    color: var(--fg-muted);
    margin-top: 2px;
    line-height: 1.4;
  }
  .preset .check {
    color: var(--accent);
    font-size: 14px;
    flex: 0 0 auto;
  }
  .preset-hint {
    display: flex; gap: 8px; align-items: flex-start;
    padding: 8px 12px;
    background: color-mix(in oklab, var(--warning) 15%, var(--bg-elev));
    border: 1px solid color-mix(in oklab, var(--warning) 35%, var(--border));
    border-radius: 6px;
    font-size: 12px;
    line-height: 1.45;
    color: var(--fg-primary);
  }
  .preset-hint i { color: var(--warning); margin-top: 2px; }

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

  /* Abschätzung */
  .estimate {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 16px;
    background: var(--bg-sink);
    border-top: 1px solid var(--border);
    font-size: 12px;
  }
  .estimate > i { color: var(--fg-muted); }
  .est-label { color: var(--fg-muted); }
  .est-size {
    font-weight: 700;
    color: var(--accent);
    font-size: 14px;
  }

  footer {
    padding: 12px 16px;
    border-top: 1px solid var(--border);
    display: flex; justify-content: flex-end; gap: 8px;
    background: var(--bg-sink);
  }

  /* Rendering-View */
  .render-body {
    padding: 20px;
    display: flex; flex-direction: column; gap: 18px;
    overflow-y: auto;
  }
  .render-progress {
    display: flex; flex-direction: column; gap: 6px;
  }
  .progress-track {
    height: 10px;
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: var(--accent);
    transition: width 200ms ease-out;
  }
  .progress-fill.is-done { background: var(--success); }
  .progress-fill.is-failed { background: var(--danger); }
  .progress-fill.is-cancelled { background: var(--warning); }
  .progress-meta {
    font-size: 12px;
    display: flex; flex-wrap: wrap; gap: 4px;
  }
  .progress-meta .pct {
    color: var(--accent);
    font-weight: 700;
    font-size: 14px;
  }

  .current-step {
    display: flex; align-items: center; gap: 14px;
    padding: 14px 16px;
    background: var(--accent-soft);
    border: 1px solid color-mix(in oklab, var(--accent) 35%, var(--border));
    border-radius: 8px;
  }
  .current-step[data-phase="done"] {
    background: color-mix(in oklab, var(--success) 18%, var(--bg-elev));
    border-color: color-mix(in oklab, var(--success) 40%, var(--border));
  }
  .current-step[data-phase="failed"] {
    background: color-mix(in oklab, var(--danger) 15%, var(--bg-elev));
    border-color: color-mix(in oklab, var(--danger) 40%, var(--border));
  }
  .current-step[data-phase="cancelled"] {
    background: color-mix(in oklab, var(--warning) 15%, var(--bg-elev));
    border-color: color-mix(in oklab, var(--warning) 40%, var(--border));
  }
  .current-step > i {
    font-size: 22px;
    color: var(--accent);
    flex: 0 0 auto;
    width: 28px;
    text-align: center;
  }
  .current-step[data-phase="done"] > i { color: var(--success); }
  .current-step[data-phase="failed"] > i { color: var(--danger); }
  .current-step[data-phase="cancelled"] > i { color: var(--warning); }
  .current-text { min-width: 0; flex: 1; }
  .current-title { font-weight: 600; font-size: 14px; }
  .current-note {
    font-size: 12px;
    color: var(--fg-muted);
    margin-top: 2px;
  }

  .pipeline {
    display: flex; flex-direction: column; gap: 6px;
  }
  .pipeline-label {
    font-size: 12px;
    color: var(--fg-muted);
    letter-spacing: 0.3px;
  }
  .pipeline-list {
    list-style: none;
    margin: 0; padding: 8px 12px;
    background: var(--bg-sink);
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 12px;
    max-height: 220px;
    overflow-y: auto;
  }
  .pipeline-list li {
    display: grid;
    grid-template-columns: 70px 140px 1fr;
    gap: 10px;
    padding: 3px 0;
    align-items: baseline;
  }
  .pipeline-list .p-time {
    color: var(--accent);
    font-weight: 600;
  }
  .pipeline-list .p-step {
    color: var(--fg-primary);
  }
  .pipeline-list .p-note {
    font-size: 11px;
  }

  .render-footer {
    padding: 12px 16px;
    border-top: 1px solid var(--border);
    display: flex; justify-content: flex-end; gap: 8px;
    background: var(--bg-sink);
  }
</style>
