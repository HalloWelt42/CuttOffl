<script>
  import { onMount } from 'svelte';
  import PanelHeader from '../components/PanelHeader.svelte';
  import { api } from '../lib/api.js';
  import { toast } from '../lib/toast.svelte.js';
  import { confirmDialog } from '../lib/dialog.svelte.js';
  import { nav, setSettingsTab, SETTINGS_TABS } from '../lib/nav.svelte.js';
  import { persisted, persist } from '../lib/persist.svelte.js';
  import { wsOn, wsStart } from '../lib/ws.svelte.js';

  // --- Modell-Download ---
  const WHISPER_SIZES = ['tiny', 'base', 'small', 'medium',
                         'large-v2', 'large-v3', 'large-v3-turbo'];
  let dlEngine = $state('');
  let dlModel  = $state('small');
  let dlJobId  = $state(null);
  let dlProgress = $state(0);
  let dlMessage  = $state('');

  // Aktiver Tab -- Quelle: URL (nav.settingsTab), sonst persistierter
  // Zuletzt-Tab, sonst Default.
  const DEFAULT_TAB = 'pfade';
  let activeTab = $state(
    nav.settingsTab || persisted('settings.tab', DEFAULT_TAB) || DEFAULT_TAB,
  );

  // Beim ersten Mount: URL-Tab ggf. ergänzen, damit Deeplink bestehen
  // bleibt (z. B. /settings ohne Tab bekommt ?tab=pfade).
  onMount(() => {
    if (!nav.settingsTab) setSettingsTab(activeTab);
  });

  // Auf URL-Änderungen reagieren (Back/Forward)
  $effect(() => {
    if (nav.settingsTab && nav.settingsTab !== activeTab) {
      activeTab = nav.settingsTab;
    }
  });

  function pickTab(t) {
    if (!SETTINGS_TABS.includes(t)) return;
    activeTab = t;
    persist('settings.tab', t);
    setSettingsTab(t);
  }

  const TABS = [
    { id: 'pfade',         label: 'Arbeits-Verzeichnisse', icon: 'fa-folder-tree' },
    { id: 'transkription', label: 'Transkription',         icon: 'fa-closed-captioning' },
    { id: 'system',        label: 'System-Info',           icon: 'fa-circle-info' },
    { id: 'reset',         label: 'Zurücksetzen',          icon: 'fa-rotate-left' },
  ];

  let ping = $state(null);
  let counts = $state({ files: 0, projects: 0, exports: 0 });
  let paths = $state(null);
  let txStatus = $state(null);
  let txScanning = $state(false);
  let txExtraPath = $state('');

  // Formular
  let originalsInput = $state('');
  let exportsInput = $state('');
  let saving = $state(false);

  async function loadAll() {
    try {
      const [p, files, projects, exports, pp, tx] = await Promise.all([
        api.ping(), api.listFiles(), api.listProjects(),
        api.listExports(), api.systemPaths(),
        api.transcriptionStatus().catch(() => null),
      ]);
      ping = p;
      counts = { files: files.length, projects: projects.length, exports: exports.length };
      paths = pp;
      originalsInput = pp.saved?.originals_dir ?? '';
      exportsInput   = pp.saved?.exports_dir   ?? '';
      txStatus = tx;
      // Default-Engine für den Download-Abschnitt: erste installierte
      if (!dlEngine) {
        const first = tx?.engines?.find((e) => e.installed);
        if (first) dlEngine = first.name;
      }
    } catch (e) { toast.error(e.message); }
  }

  async function useModel(m) {
    try {
      await api.setTranscriptionPreference(m.engine, m.model);
      txStatus = await api.transcriptionStatus();
      toast.success(`Aktiv: ${m.engine} / ${m.model}`);
    } catch (e) { toast.error(e.message); }
  }

  async function resetPreference() {
    try {
      await api.setTranscriptionPreference(null, null);
      txStatus = await api.transcriptionStatus();
      toast.info('Auswahl zurückgesetzt -- Auto-Vorschlag wird verwendet');
    } catch (e) { toast.error(e.message); }
  }

  // pip-Paketname je Engine -- fast immer identisch zum Engine-Namen,
  // aber openai-whisper heißt im Python-Import nur "whisper".
  function pipPackageFor(engine) {
    if (engine === 'mlx-whisper') return 'mlx-whisper';
    if (engine === 'faster-whisper') return 'faster-whisper';
    if (engine === 'openai-whisper') return 'openai-whisper';
    return engine;
  }

  async function copyCmd(cmd) {
    try {
      await navigator.clipboard.writeText(cmd);
      toast.success('In die Zwischenablage kopiert');
    } catch {
      toast.error('Kopieren nicht möglich -- bitte manuell markieren');
    }
  }

  async function copyPipCmd(engine) {
    const pkg = pipPackageFor(engine);
    const cmd = `cd backend && source .venv/bin/activate && pip install ${pkg}`;
    await copyCmd(cmd);
  }

  // Bei disabled-Modellen: kurzer Toast statt stummem Button, damit
  // der User weiß, was zu tun ist.
  function explainDisabled(model) {
    const engine = (txStatus?.engines || []).find((e) => e.name === model.engine);
    if (engine && !engine.installed) {
      toast.info(
        `Engine "${model.engine}" ist nicht installiert. `
        + `Kopiere oben bei "Installierte Pakete" den pip-Befehl und `
        + `starte das Backend neu.`,
        { duration: 8000 },
      );
    }
  }

  async function startModelDownload() {
    if (!dlEngine || !dlModel) return;
    try {
      const res = await api.downloadModel(dlEngine, dlModel);
      dlJobId = res?.job_id ?? null;
      dlProgress = 0;
      dlMessage = `${dlEngine} / ${dlModel} wird geladen...`;
      toast.info(`Download gestartet: ${dlEngine} / ${dlModel}`);
    } catch (e) {
      toast.error(e.message);
    }
  }

  async function cancelModelDownload() {
    if (!dlJobId) return;
    try {
      await api.cancelJob(dlJobId);
      toast.info('Abbruch angefordert');
    } catch (e) { toast.error(e.message); }
  }

  onMount(() => {
    wsStart();
    const off = wsOn(async (msg) => {
      if (msg.type === 'job_progress' && msg.kind === 'download_model'
          && msg.job_id === dlJobId) {
        dlProgress = msg.progress || 0;
      }
      if (msg.type === 'job_event' && msg.job?.kind === 'download_model'
          && msg.job.id === dlJobId) {
        if (msg.event === 'completed') {
          dlProgress = 1;
          dlMessage = `${dlEngine} / ${dlModel} fertig`;
          dlJobId = null;
          // Status neu laden, damit das neue Modell in der Liste erscheint
          try { txStatus = await api.transcriptionStatus(); } catch {}
          toast.success(`Modell ${dlEngine} / ${dlModel} heruntergeladen`);
        } else if (msg.event === 'failed') {
          dlMessage = `Fehler: ${msg.job.error || 'unbekannt'}`;
          dlJobId = null;
          toast.error(`Download: ${msg.job.error || 'fehlgeschlagen'}`);
        } else if (msg.event === 'cancelled') {
          dlMessage = 'Abgebrochen';
          dlJobId = null;
          toast.info('Download abgebrochen');
        }
      }
    });
    return off;
  });

  async function scanModels() {
    txScanning = true;
    try {
      const res = await api.transcriptionScan(
        txExtraPath ? [txExtraPath.trim()] : [],
      );
      // Kompletten Status neu laden, damit suggested_* aktualisiert wird
      txStatus = await api.transcriptionStatus();
      const n = res.models_found?.length || 0;
      toast.success(n ? `${n} Modelle gefunden` : 'Kein Whisper-Modell gefunden');
    } catch (e) { toast.error(e.message); }
    finally { txScanning = false; }
  }

  function fmtSizeB(n) {
    if (!n) return '-';
    const u = ['B','KB','MB','GB','TB'];
    let i = 0; while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
  }

  onMount(loadAll);

  // --- Resets -----------------------------------------------------------

  let resetBusy = $state('');      // 'caches' | 'transcripts' | ... | ''
  let demoProtected = $derived(
    paths ? false : false,   // reiner Platzhalter, echte Info folgt über listFiles
  );
  let demoVideoInfo = $state({ present: false, file: null });

  async function loadDemoInfo() {
    try {
      const files = await api.listFiles();
      const demo = (files || []).find((f) => f.protected);
      demoVideoInfo = demo
        ? { present: true, file: demo }
        : { present: false, file: null };
    } catch { demoVideoInfo = { present: false, file: null }; }
  }
  // Demo-Info beim ersten Besuch des Reset-Tabs laden
  $effect(() => {
    if (activeTab === 'reset' && !demoVideoInfo.present) {
      loadDemoInfo();
    }
  });

  async function runReset(target, confirmMsg) {
    if (resetBusy) return;
    const ok = await confirmDialog(confirmMsg, {
      title: 'Bestätigen',
      okLabel: 'Zurücksetzen',
      okVariant: 'danger',
    });
    if (!ok) return;
    resetBusy = target;
    try {
      const res = await api.systemReset(target);
      toast.success(`Zurückgesetzt: ${target}`);
      // Storage-Zahlen + Demo-Info neu laden
      await loadAll();
      await loadDemoInfo();
      return res;
    } catch (e) {
      toast.error(`${target}: ${e.message}`);
    } finally {
      resetBusy = '';
    }
  }

  function resetTours() {
    // rein clientseitig
    const keys = [
      'tour.completed', 'tour.firstRunOffered', 'tour.audioOn',
    ];
    keys.forEach((k) => localStorage.removeItem(k));
    toast.success(
      'Touren zurückgesetzt -- beim nächsten Dashboard-Besuch wird die '
      + 'Einsteiger-Tour wieder angeboten.',
    );
  }

  function resetAppPrefs() {
    // Alles unter app.*, editor.*, library.*, panel.* weg.
    // Transkriptions-Präferenz (user_config.json) und Pfade bleiben.
    const prefixes = ['app.', 'editor.', 'library.', 'panel.'];
    const toDelete = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && prefixes.some((p) => k.startsWith(p))) toDelete.push(k);
    }
    toDelete.forEach((k) => localStorage.removeItem(k));
    toast.success(
      `App-Einstellungen zurückgesetzt (${toDelete.length} Einträge). `
      + 'Lade die App neu, damit alles frisch greift.',
    );
  }

  async function savePaths() {
    saving = true;
    try {
      const body = {
        originals_dir: originalsInput.trim(),
        exports_dir:   exportsInput.trim(),
      };
      const res = await api.setSystemPaths(body);
      toast.success('Pfade gespeichert. Bitte Backend neu starten, damit sie aktiv werden.');
      paths = await api.systemPaths();
    } catch (e) { toast.error(e.message); }
    finally { saving = false; }
  }

  function resetOriginals() { originalsInput = ''; }
  function resetExports()   { exportsInput = ''; }
</script>

<section class="wrap view-readable">
  <PanelHeader icon="fa-gear" title="Einstellungen"
               subtitle={TABS.find((t) => t.id === activeTab)?.label ?? ''} />

  <!-- Tab-Leiste direkt unter dem Header. Deeplinks: /settings/<tab> -->
  <div class="tabs" role="tablist" aria-label="Einstellungs-Bereiche">
    {#each TABS as t (t.id)}
      <button class="tab" role="tab" aria-selected={activeTab === t.id}
              class:active={activeTab === t.id}
              onclick={() => pickTab(t.id)}
              title="Zum Bereich {t.label} wechseln">
        <i class="fa-solid {t.icon}"></i>
        <span>{t.label}</span>
      </button>
    {/each}
  </div>

  <div class="body">
    {#if activeTab === 'pfade'}
    <div class="card block">
      <h3><i class="fa-solid fa-folder-tree"></i> Arbeits-Verzeichnisse</h3>
      <p class="hint">
        Videos liegen standardmäßig im Projekt-Unterordner <code>data/</code>.
        Du kannst die Basis für <b>Originale</b> und <b>fertige Videos</b>
        auf einen beliebigen Ordner auf deinem Rechner legen -- zum Beispiel
        ein Verzeichnis auf einer größeren Festplatte oder einem Netzlaufwerk.
        Schreibrechte sind Pflicht. Der Pfad wird beim Speichern geprüft.
      </p>
      <p class="warn">
        <i class="fa-solid fa-triangle-exclamation"></i>
        Änderungen werden erst nach einem Neustart des Backends wirksam.
        Bereits vorhandene Dateien bleiben am alten Ort -- bei Bedarf
        manuell in den neuen Ordner verschieben.
      </p>

      <div class="field">
        <label for="p-orig">Originale (hochgeladene Videos)</label>
        <div class="row">
          <input id="p-orig" type="text" bind:value={originalsInput}
                 placeholder={paths?.default?.originals_dir || ''} />
          <button class="btn" type="button" onclick={resetOriginals}
                  title="Eintrag leeren -- nach Speichern wird wieder der Default verwendet">
            <i class="fa-solid fa-rotate-left"></i>
          </button>
        </div>
        <div class="meta mono">
          <span>aktuell aktiv: {paths?.active?.originals_dir ?? '…'}</span>
        </div>
      </div>

      <div class="field">
        <label for="p-exp">Fertige Videos (gerenderte Exports)</label>
        <div class="row">
          <input id="p-exp" type="text" bind:value={exportsInput}
                 placeholder={paths?.default?.exports_dir || ''} />
          <button class="btn" type="button" onclick={resetExports}
                  title="Eintrag leeren -- nach Speichern wird wieder der Default verwendet">
            <i class="fa-solid fa-rotate-left"></i>
          </button>
        </div>
        <div class="meta mono">
          <span>aktuell aktiv: {paths?.active?.exports_dir ?? '…'}</span>
        </div>
      </div>

      <div class="actions">
        <button class="btn btn-primary" onclick={savePaths} disabled={saving}
                title="Pfade speichern. Werden nach Backend-Neustart aktiv.">
          <i class="fa-solid fa-floppy-disk"></i>
          {saving ? 'Speichert…' : 'Speichern'}
        </button>
      </div>
    </div>

    {:else if activeTab === 'system'}
    <div class="card block">
      <h3><i class="fa-solid fa-circle-info"></i> System</h3>
      <!-- Zwei Spalten für die kurzen Info-Paare; bricht auf schmalen
           Fenstern auf eine Spalte um. -->
      <dl class="kv kv-two">
        <div><dt>Backend</dt><dd class="mono">{ping?.app ?? '-'} v{ping?.version ?? '-'}</dd></div>
        <div><dt>Host</dt><dd class="mono">{ping?.host ?? '-'}:{ping?.port ?? '-'}</dd></div>
        <div><dt>HW-Encoder</dt><dd class="mono">{ping?.hw_encoder ?? '-'}</dd></div>
        <div><dt>FFmpeg</dt><dd class="mono">{ping?.ffmpeg_version?.split(' ').slice(0,3).join(' ') ?? '-'}</dd></div>
        <div><dt>Dateien</dt><dd class="mono">{counts.files}</dd></div>
        <div><dt>Projekte</dt><dd class="mono">{counts.projects}</dd></div>
        <div><dt>Fertige Videos</dt><dd class="mono">{counts.exports}</dd></div>
      </dl>
    </div>

    {:else if activeTab === 'transkription'}
    <div class="card block">
      <h3><i class="fa-solid fa-closed-captioning"></i> Transkription (KI-Untertitel)</h3>
      <p class="hint">
        CuttOffl kann Videos mit Whisper transkribieren und daraus SRT-
        Untertitel erzeugen. Die Transkription läuft komplett lokal. Die
        Whisper-Pakete und -Modelle musst du einmal selbst installieren --
        die App entdeckt Modelle, die schon auf deinem Rechner liegen
        (HuggingFace-Cache, openai-whisper-Cache, Voice2Text-Cache).
      </p>

      {#if !txStatus}
        <p class="meta">Lade Status …</p>
      {:else if !txStatus.available}
        <div class="tx-offline">
          <div class="tx-row">
            <span class="tx-dot off"></span>
            <b>Nicht einsatzbereit</b>
          </div>
          {#each txStatus.notes as n}
            <p class="note">{n}</p>
          {/each}
          <details class="install">
            <summary>Installationshinweise anzeigen</summary>
            <pre>{@html `# Variante A -- einmalig im Setup mitinstallieren:
./setup.sh --with-transcription

# Variante B -- in die bestehende Backend-venv nachinstallieren:
cd backend && source .venv/bin/activate
pip install -r requirements-transcription.txt

# Variante C -- einzelne Engine selbst wählen:
#   Apple Silicon:   pip install mlx-whisper
#   Pi/Linux/Intel:  pip install faster-whisper
#   Referenz:        pip install openai-whisper

# Danach Backend einmal neu starten:
./start.sh restart backend`}</pre>
          </details>
        </div>
      {:else}
        <div class="tx-ready">
          <div class="tx-row">
            <span class="tx-dot on"></span>
            <b>Einsatzbereit</b>
          </div>
          <dl class="kv kv-two">
            <div><dt>Aktive Engine</dt><dd class="mono">{txStatus.active_engine}</dd></div>
            <div><dt>Aktives Modell</dt><dd class="mono">{txStatus.active_model}</dd></div>
          </dl>
          {#if (txStatus.active_engine !== txStatus.suggested_engine
                || txStatus.active_model !== txStatus.suggested_model)}
            <p class="meta">
              Auto-Vorschlag wäre: {txStatus.suggested_engine} / {txStatus.suggested_model}
              <button class="btn btn-sm" onclick={resetPreference}
                      title="Eigene Modellwahl verwerfen und wieder dem Vorschlag folgen">
                <i class="fa-solid fa-rotate-left"></i> Auf Vorschlag zurück
              </button>
            </p>
          {/if}
        </div>
      {/if}

      <h4 class="sub">Installierte Pakete</h4>
      <ul class="engines">
        {#each (txStatus?.engines || []) as e (e.name)}
          <li>
            <span class="tx-dot {e.installed ? 'on' : 'off'}"></span>
            <span class="name mono">{e.name}</span>
            {#if e.preferred}<span class="tag preferred">empfohlen</span>{/if}
            {#if !e.installed}
              <span class="reason">{e.reason}</span>
              <button class="btn btn-sm pip-copy" onclick={() => copyPipCmd(e.name)}
                      title={`pip-Befehl für ${e.name} kopieren`}>
                <i class="fa-solid fa-copy"></i>
                <span class="pip-cmd mono">pip install {pipPackageFor(e.name)}</span>
              </button>
            {/if}
          </li>
        {/each}
      </ul>
      {#if (txStatus?.engines || []).some((e) => !e.installed)}
        <p class="meta pip-hint">
          <i class="fa-solid fa-circle-info"></i>
          Fehlende Engines in der Backend-venv installieren, danach
          <button class="linklike" onclick={() => copyCmd('./start.sh restart backend')}>
            <code>./start.sh restart backend</code>
          </button>.
        </p>
      {/if}

      <h4 class="sub">Gefundene Modelle auf der Platte</h4>
      {#if (txStatus?.models_found?.length || 0) === 0}
        <p class="meta">Bisher keine Modelle gefunden. Scanne weiter unten.</p>
      {:else}
        <ul class="models">
          {#each txStatus.models_found as m (m.engine + m.path)}
            {@const isActive = m.engine === txStatus.active_engine
                               && m.model === txStatus.active_model}
            {@const engineInstalled = txStatus.engines.find(
              (e) => e.name === m.engine)?.installed}
            <li class:active={isActive}>
              <div class="m-head">
                <span class="name mono">{m.engine} / {m.model}</span>
                {#if isActive}
                  <span class="badge-active">
                    <i class="fa-solid fa-check"></i> Aktiv
                  </span>
                {:else if engineInstalled}
                  <button class="btn btn-sm"
                          onclick={() => useModel(m)}
                          title="Dieses Modell für die Transkription verwenden">
                    <i class="fa-solid fa-check"></i>
                    Auswählen
                  </button>
                {:else}
                  <button class="btn btn-sm btn-warn-soft"
                          onclick={() => explainDisabled(m)}
                          title={`Engine ${m.engine} ist nicht installiert -- klick für Installationshinweis`}>
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    Engine fehlt
                  </button>
                {/if}
                <span class="size mono">{fmtSizeB(m.size_bytes)}</span>
              </div>
              <div class="path mono" title={m.path}>{m.path}</div>
            </li>
          {/each}
        </ul>
      {/if}

      <h4 class="sub">Weiteres Modell herunterladen</h4>
      <p class="meta">
        Lädt direkt vom offiziellen HuggingFace-Repo in den Cache der
        gewählten Engine. Downloads laufen im Hintergrund, Fortschritt
        erscheint unten.
      </p>
      <div class="scan-row">
        <select class="sort-select" bind:value={dlEngine}
                title="Für welche Engine soll das Modell geladen werden?">
          {#each (txStatus?.engines || []).filter((e) => e.installed) as e (e.name)}
            <option value={e.name}>{e.name}</option>
          {/each}
          {#if (txStatus?.engines || []).every((e) => !e.installed)}
            <option value="">— keine Engine installiert —</option>
          {/if}
        </select>
        <select class="sort-select" bind:value={dlModel}
                title="Modellgröße. Größere Modelle sind genauer, brauchen aber mehr Platz und Zeit.">
          {#each WHISPER_SIZES as s (s)}
            <option value={s}>{s}</option>
          {/each}
        </select>
        <button class="btn btn-primary" onclick={startModelDownload}
                disabled={!dlEngine || !!dlJobId}
                title="Modell in den Cache herunterladen">
          <i class="fa-solid fa-download"></i>
          Herunterladen
        </button>
      </div>
      {#if dlJobId || dlMessage}
        <div class="dl-progress">
          <div class="dl-head">
            <span class="mono">{dlMessage}</span>
            {#if dlJobId}
              <span class="mono dim">{Math.round((dlProgress || 0) * 100)} %</span>
              <button class="btn btn-sm btn-danger" onclick={cancelModelDownload}
                      title="Download abbrechen">
                <i class="fa-solid fa-stop"></i>
              </button>
            {/if}
          </div>
          {#if dlJobId}
            <div class="dl-bar">
              <div class="dl-fill" style:width={`${Math.round((dlProgress || 0) * 100)}%`}></div>
            </div>
          {/if}
        </div>
      {/if}

      <h4 class="sub">Auf der Platte scannen</h4>
      <div class="scan-row">
        <input type="text" class="scan-input"
               placeholder="Optional: zusätzlichen Ordner zum Scannen …"
               bind:value={txExtraPath} />
        <button class="btn" onclick={scanModels} disabled={txScanning}
                title="Bekannte Cache-Ordner und den angegebenen Pfad nach Whisper-Modellen absuchen">
          <i class="fa-solid fa-magnifying-glass"></i>
          {txScanning ? 'Scanne …' : 'Festplatte scannen'}
        </button>
      </div>
    </div>

    {:else if activeTab === 'reset'}
    <!-- Reset-Tab: lokale Dinge (Touren, App-Prefs) und Server-Reste
         (Caches, Transkripte, Job-Historie, Demo-Video). Jeder Block
         als eigene Karte mit Bestätigungsdialog. -->
    <div class="tab-body reset-body">
      <p class="lead">
        Hier setzt du einzelne Bereiche zurück -- kein Bereich reißt
        andere mit. Originale und Projekte bleiben immer erhalten.
      </p>

      <article class="reset-card">
        <header>
          <i class="fa-solid fa-life-ring"></i>
          <h4>Touren</h4>
        </header>
        <p>
          Setzt die Fortschritts-Merker aller Touren zurück. Das
          First-Run-Modal erscheint beim nächsten Dashboard-Besuch
          wieder, alle Touren gelten als "noch nicht gesehen". Die
          MP3-Dateien der Sprecher-Stimme bleiben natürlich liegen.
        </p>
        <button class="btn" onclick={resetTours}>
          <i class="fa-solid fa-rotate-left"></i> Touren zurücksetzen
        </button>
      </article>

      <article class="reset-card">
        <header>
          <i class="fa-solid fa-sliders"></i>
          <h4>App-Einstellungen</h4>
        </header>
        <p>
          Theme, Sidebar-Breite, Panel-Positionen, Editor-Präferenzen
          (Snap, Follow, Zoom), Bibliotheks-Ansicht &amp; Filter, Tab-
          Deeplinks -- alles was lokal im Browser liegt, wird auf
          Default zurückgesetzt. <b>Bleibt:</b> deine Arbeits-
          Verzeichnisse und die Transkriptions-Modellwahl (die stehen
          serverseitig).
        </p>
        <button class="btn" onclick={resetAppPrefs}>
          <i class="fa-solid fa-rotate-left"></i> App-Einstellungen zurücksetzen
        </button>
      </article>

      <h3 class="group-head">Speicher</h3>

      <article class="reset-card">
        <header>
          <i class="fa-solid fa-broom"></i>
          <h4>Vorschau-Caches leeren</h4>
        </header>
        <p>
          Löscht Proxy-Videos, Thumbnails, Frame-Streifen und
          Wellenformen -- die werden bei Bedarf neu erzeugt. Originale,
          Projekte und Transkripte bleiben unberührt. Danach müssen die
          Vorschauen einmal neu gerechnet werden (dauert, je nach
          Menge).
        </p>
        <button class="btn btn-danger" disabled={!!resetBusy}
                onclick={() => runReset('caches',
                  'Alle Proxy-Vorschauen, Thumbnails, Sprite-Streifen '
                  + 'und Wellenformen werden gelöscht. Die Dateien selbst '
                  + 'bleiben, aber Vorschauen müssen neu erzeugt werden. '
                  + 'Fortfahren?')}>
          <i class="fa-solid fa-broom"></i>
          {resetBusy === 'caches' ? 'Leere …' : 'Caches leeren'}
        </button>
      </article>

      <article class="reset-card">
        <header>
          <i class="fa-solid fa-closed-captioning"></i>
          <h4>Transkripte löschen</h4>
        </header>
        <p>
          Alle erzeugten SRT-Transkripte werden entfernt. Videos und
          Projekte bleiben unberührt. Danach kannst du bei Bedarf neu
          transkribieren lassen.
        </p>
        <button class="btn btn-danger" disabled={!!resetBusy}
                onclick={() => runReset('transcripts',
                  'Alle SRT-Transkripte werden gelöscht. Videos bleiben '
                  + 'erhalten. Sicher?')}>
          <i class="fa-solid fa-trash"></i>
          {resetBusy === 'transcripts' ? 'Lösche …' : 'Transkripte löschen'}
        </button>
      </article>

      <article class="reset-card">
        <header>
          <i class="fa-solid fa-list-check"></i>
          <h4>Job-Historie leeren</h4>
        </header>
        <p>
          Abgeschlossene und fehlgeschlagene Jobs werden aus der
          Historie entfernt. Render-Jobs mit noch existierenden
          Export-Dateien bleiben erhalten, damit die Liste der fertigen
          Videos vollständig bleibt.
        </p>
        <button class="btn btn-danger" disabled={!!resetBusy}
                onclick={() => runReset('jobs-history',
                  'Die Job-Historie (abgeschlossene + fehlgeschlagene '
                  + 'Jobs) wird geleert. Fortfahren?')}>
          <i class="fa-solid fa-eraser"></i>
          {resetBusy === 'jobs-history' ? 'Räume …' : 'Historie leeren'}
        </button>
      </article>

      <h3 class="group-head">Demo-Video</h3>

      <article class="reset-card reset-card-demo">
        <header>
          <i class="fa-solid fa-circle-play"></i>
          <h4>
            Big Buck Bunny -- Demo-Video
            {#if demoVideoInfo.present}
              <span class="mini-badge">in Bibliothek</span>
            {:else}
              <span class="mini-badge off">nicht importiert</span>
            {/if}
          </h4>
        </header>
        <p>
          Das Demo-Video ist in der Bibliothek geschützt und kann dort
          nicht versehentlich gelöscht werden. Hier ist der einzige
          Weg, es zu entfernen oder (bei Bedarf) neu zu holen.
          Lizenz: © Blender Foundation, CC BY 3.0.
        </p>
        <div class="reset-actions">
          <button class="btn btn-danger" disabled={!!resetBusy || !demoVideoInfo.present}
                  onclick={() => runReset('demo-video-remove',
                    'Das Demo-Video wird aus der Bibliothek entfernt '
                    + '(DB-Eintrag + abgeleitete Vorschauen). Die '
                    + 'Quelldatei in data/demo/ bleibt liegen, du '
                    + 'kannst das Demo jederzeit neu laden. Fortfahren?')}>
            <i class="fa-solid fa-trash"></i>
            {resetBusy === 'demo-video-remove' ? 'Entferne …' : 'Aus Bibliothek entfernen'}
          </button>
          <button class="btn btn-primary" disabled={!!resetBusy}
                  onclick={() => runReset('demo-video-reload',
                    'Das Demo-Video wird neu geladen. Wenn die Quelle '
                    + 'fehlt, wird sie bei bestehender Internet-Verbindung '
                    + 'neu von download.blender.org geholt -- das kann '
                    + 'ein paar Minuten dauern. Fortfahren?')}>
            <i class="fa-solid fa-rotate-right"></i>
            {resetBusy === 'demo-video-reload' ? 'Lade …' : 'Neu laden'}
          </button>
        </div>
      </article>
    </div>

    {/if}

    <!-- Tab-unabhaengiger Hinweis -- bleibt immer am unteren Rand -->
    <p class="hint-to-panel">
      <i class="fa-solid fa-circle-info"></i>
      Tastaturkürzel und kontextbezogene Hinweise findest du jetzt im
      <b>Info</b>-Fenster (linke Seitenleiste, Hilfe-Bereich). Der Inhalt
      passt sich automatisch an die aktive Ansicht an.
    </p>
  </div>
</section>

<style>
  .wrap { display: flex; flex-direction: column; height: 100%; }

  /* Tab-Leiste direkt unter dem Panel-Header. Layout wie die Info-/
     Exports-Tabs im Editor: Aktiver Tab akzent-eingefärbt mit unterer
     Linie. */
  .tabs {
    display: flex;
    gap: 2px;
    padding: 6px 20px 0;
    background: var(--bg-panel);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }
  .tab {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border: none;
    background: transparent;
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
    padding: 24px; display: flex; flex-direction: column; gap: 18px;
    max-width: 900px;
    overflow: auto;
  }
  .block { padding: 20px; }
  h3 {
    display: flex; align-items: center; gap: 8px;
    margin: 0 0 10px; font-size: 17px; color: var(--fg-primary);
    font-weight: 600;
  }
  h3 i { color: var(--accent); }

  /* Lesetexte bewusst größer als die dichte Cutter-UI */
  .hint {
    font-size: 15px;
    margin: 0 0 12px;
    color: var(--fg-primary);
    line-height: 1.7;
  }
  .warn {
    color: var(--warning);
    font-size: 14px;
    line-height: 1.7;
    display: flex;
    gap: 10px;
    align-items: flex-start;
  }
  .warn i { padding-top: 3px; flex: 0 0 auto; }

  .field { margin-top: 16px; }
  .field label {
    display: block;
    font-size: 14px;
    color: var(--fg-primary);
    letter-spacing: 0.2px;
    margin-bottom: 6px;
    font-weight: 600;
  }
  .field .row { display: flex; gap: 8px; }
  .field input {
    flex: 1 1 auto;
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--border-strong);
    border-radius: 6px;
    padding: 10px 12px;
    /* Pfade profitieren trotzdem von Monospace, aber etwas größer */
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 14px;
  }
  .field input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-soft);
  }
  .meta { margin-top: 6px; font-size: 12px; color: var(--fg-faint); }
  .meta.mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }

  .actions { margin-top: 16px; display: flex; justify-content: flex-end; }

  /* System-Info als Key-Value-Raster, standardmaessig zweispaltig. Label
     in Basis-Schrift, Werte in Mono (damit Versionen und IPs sauber
     ausgerichtet aussehen). */
  .kv {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 8px 16px;
    margin: 0;
    font-size: 14.5px;
  }
  .kv dt {
    color: var(--fg-muted);
    font-weight: 500;
  }
  .kv dd { margin: 0; color: var(--fg-primary); }
  .kv dd.mono {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 13.5px;
  }

  .kv-two {
    grid-template-columns: 1fr 1fr;
    gap: 10px 24px;
  }
  .kv-two > div {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 4px 12px;
    align-items: baseline;
  }
  @media (max-width: 640px) {
    .kv-two { grid-template-columns: 1fr; }
  }

  /* Transkriptions-Block */
  .sub {
    margin: 16px 0 8px;
    font-size: 12px;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: var(--fg-muted);
  }
  .note { margin: 4px 0; font-size: 14px; color: var(--fg-primary); line-height: 1.6; }
  .tx-row { display: flex; align-items: center; gap: 8px; font-size: 14px; }
  .tx-dot {
    width: 10px; height: 10px; border-radius: 50%;
    display: inline-block;
    background: var(--fg-faint);
  }
  .tx-dot.on  { background: var(--success); }
  .tx-dot.off { background: var(--danger); }
  .tx-ready, .tx-offline { padding: 4px 0 2px; }

  .engines {
    list-style: none; padding: 0; margin: 0;
    display: flex; flex-direction: column; gap: 6px;
    font-size: 13px;
  }
  .engines li {
    display: flex; align-items: center; gap: 8px;
    flex-wrap: wrap;
  }
  .engines .reason { color: var(--fg-muted); font-size: 12px; }
  .tag.preferred {
    background: var(--accent-soft);
    color: var(--accent);
    font-size: 10px; font-weight: 700;
    padding: 1px 6px; border-radius: 4px;
    text-transform: uppercase; letter-spacing: 0.5px;
  }
  .pip-copy {
    display: inline-flex; align-items: center; gap: 6px;
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 11px;
  }
  .pip-copy .pip-cmd {
    color: var(--fg-muted);
  }
  .pip-hint {
    margin-top: 8px;
    display: flex; align-items: center; gap: 8px;
    flex-wrap: wrap;
  }
  .pip-hint i { color: var(--accent); }
  .pip-hint code {
    font-family: var(--font-mono);
    background: var(--bg-elev);
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 12px;
    color: var(--fg-primary);
  }
  .btn-warn-soft {
    background: color-mix(in oklab, var(--warning) 12%, var(--bg-elev));
    border-color: color-mix(in oklab, var(--warning) 35%, var(--border));
    color: var(--warning);
  }
  .btn-warn-soft:hover {
    background: color-mix(in oklab, var(--warning) 20%, var(--bg-elev));
  }

  .models {
    list-style: none; padding: 0; margin: 0;
    display: flex; flex-direction: column; gap: 6px;
  }
  .models li {
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 10px;
    transition: border-color 120ms, background 120ms;
  }
  .models li.active {
    background: var(--accent-soft);
    border-color: var(--accent);
  }
  .m-head {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
  }
  .m-head .name { font-weight: 600; flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
  .m-head .size { color: var(--fg-muted); font-size: 12px; flex: 0 0 auto; }
  .badge-active {
    display: inline-flex; align-items: center; gap: 4px;
    background: var(--accent);
    color: var(--accent-on);
    font-size: 11px; font-weight: 700;
    padding: 3px 8px; border-radius: 4px;
    text-transform: uppercase; letter-spacing: 0.5px;
  }
  .models .path {
    margin-top: 3px;
    font-size: 11px;
    color: var(--fg-faint);
    word-break: break-all;
    line-height: 1.4;
  }

  .scan-row {
    display: flex; gap: 8px; margin-top: 12px;
  }
  .scan-input {
    flex: 1 1 auto;
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--border-strong);
    border-radius: 6px;
    padding: 8px 10px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 13px;
  }
  .scan-input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-soft);
  }

  .dl-progress {
    margin-top: 10px;
    padding: 8px 10px;
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  .dl-head {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 12px;
  }
  .dl-head .mono { flex: 1 1 auto; }
  .dl-bar {
    margin-top: 6px;
    height: 6px;
    background: var(--bg-sink);
    border-radius: 3px;
    overflow: hidden;
    border: 1px solid var(--border);
  }
  .dl-fill {
    height: 100%;
    background: var(--accent);
    transition: width 200ms linear;
  }

  .install summary {
    cursor: pointer;
    color: var(--fg-muted);
    font-size: 13px;
    margin-top: 6px;
  }
  .install pre {
    margin: 8px 0 0;
    padding: 12px;
    background: var(--bg-sink);
    border: 1px solid var(--border);
    border-radius: 6px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 12px;
    color: var(--fg-primary);
    white-space: pre-wrap;
    line-height: 1.55;
  }

  .hint-to-panel {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    padding: 14px 18px;
    background: var(--accent-soft);
    border: 1px solid color-mix(in oklab, var(--accent) 40%, var(--border));
    border-radius: 8px;
    font-size: 15px;
    line-height: 1.7;
    color: var(--fg-primary);
  }
  .hint-to-panel i { color: var(--accent); padding-top: 4px; }
  .hint-to-panel b { color: var(--accent); }

  code {
    background: var(--bg-elev);
    padding: 1px 6px;
    border-radius: 3px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 13px;
  }

  /* ---- Reset-Tab ---- */
  .reset-body {
    max-width: 780px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .reset-body .lead {
    color: var(--fg-muted);
    line-height: 1.55;
    margin: 0 0 4px;
  }
  .reset-body .group-head {
    margin: 16px 0 2px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--fg-faint);
    font-weight: 600;
  }
  .reset-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 14px 16px;
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .reset-card header {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .reset-card header i {
    color: var(--accent);
    font-size: 18px;
    width: 24px;
    text-align: center;
  }
  .reset-card h4 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .reset-card p {
    margin: 0;
    color: var(--fg-muted);
    font-size: 13px;
    line-height: 1.5;
  }
  .reset-card button {
    align-self: flex-start;
    margin-top: 4px;
  }
  .reset-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 4px;
  }
  .reset-actions button { align-self: auto; margin-top: 0; }

  .reset-card-demo {
    background: linear-gradient(
      135deg,
      color-mix(in oklab, var(--accent) 14%, var(--bg-panel)) 0%,
      var(--bg-panel) 70%
    );
    border-color: color-mix(in oklab, var(--accent) 40%, var(--border));
  }
  .mini-badge {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 10px;
    background: var(--success);
    color: var(--accent-on);
  }
  .mini-badge.off {
    background: var(--bg-elev);
    color: var(--fg-muted);
    border: 1px solid var(--border);
  }
</style>
