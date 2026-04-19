<script>
  // Library-Picker fuer Audio-Dateien. Listet alle Library-Files mit
  // is_audio_only=true als klickbare Kacheln; ein Klick fuegt einen
  // AudioClip in editor.edl.audio_track am aktuellen Playhead ein
  // und schliesst den Dialog.

  import { api } from '../lib/api.js';
  import { editor, addAudioClip } from '../lib/editor.svelte.js';
  import { toast } from '../lib/toast.svelte.js';

  let { open = $bindable(false) } = $props();

  let files = $state([]);
  let loading = $state(false);
  let error = $state(null);

  $effect(() => {
    if (!open) return;
    void loadFiles();
  });

  async function loadFiles() {
    loading = true;
    error = null;
    try {
      const all = await api.listFiles();
      files = (all || []).filter((f) => f.is_audio_only);
    } catch (e) {
      error = e.message || String(e);
    } finally {
      loading = false;
    }
  }

  function pick(f) {
    const dur = f.duration_s || 0;
    if (!dur) {
      toast.warn('Audio-Datei hat keine Dauer-Info');
      return;
    }
    const id = addAudioClip(f.id, dur, editor.playhead || 0);
    if (id) toast.success(`Audio hinzugefuegt: ${f.original_name}`);
    open = false;
  }

  function close() { open = false; }
  function onBackdrop(e) { if (e.target === e.currentTarget) close(); }
  function onKey(e) {
    if (e.key === 'Escape') close();
  }

  function fmtDur(s) {
    if (!s || s < 0) return '-';
    const m = Math.floor(s / 60);
    const ss = Math.floor(s % 60);
    return `${m}:${String(ss).padStart(2, '0')}`;
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="backdrop" onclick={onBackdrop} onkeydown={onKey} role="presentation">
    <div class="modal" role="dialog" aria-modal="true" aria-label="Audio-Datei hinzufuegen">
      <header>
        <i class="fa-solid fa-music"></i>
        <h2>Audio-Datei hinzufügen</h2>
        <button class="x" onclick={close} aria-label="Schließen">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </header>

      <div class="body">
        {#if loading}
          <div class="status">Lade Audio-Dateien...</div>
        {:else if error}
          <div class="status error">Fehler: {error}</div>
        {:else if files.length === 0}
          <div class="status">
            Keine Audio-Dateien in der Bibliothek. Lade zuerst eine
            WAV/MP3/M4A/FLAC/AAC/OGG/OPUS-Datei in der Bibliothek hoch.
          </div>
        {:else}
          <ul class="grid">
            {#each files as f (f.id)}
              <li>
                <button class="tile" onclick={() => pick(f)}>
                  <div class="icon"><i class="fa-solid fa-music"></i></div>
                  <div class="meta">
                    <div class="name" title={f.original_name}>{f.original_name}</div>
                    <div class="row mono">
                      <span>{fmtDur(f.duration_s)}</span>
                      <span>{f.audio_codec ?? 'audio'}</span>
                    </div>
                  </div>
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      </div>

      <footer>
        <div class="hint dim mono">
          Wird am Playhead ({(editor.playhead || 0).toFixed(2)} s) eingefügt.
        </div>
        <button class="btn" onclick={close}>Abbrechen</button>
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
    width: min(640px, 92vw);
    max-height: 82vh;
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
  header > i { color: var(--audio-color); }
  header h2 { margin: 0; font-size: 16px; flex: 1; }
  .x { background: transparent; border: none; color: var(--fg-muted);
       cursor: pointer; font-size: 16px; }
  .x:hover { color: var(--fg-primary); }

  .body { padding: 12px 16px; overflow-y: auto; flex: 1; min-height: 120px; }
  .status { padding: 12px; color: var(--fg-muted); font-size: 13px; }
  .status.error { color: var(--danger); }

  .grid {
    list-style: none;
    margin: 0; padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 8px;
  }
  .tile {
    display: flex; align-items: center; gap: 10px;
    width: 100%;
    padding: 10px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg-sink);
    color: var(--fg-primary);
    cursor: pointer;
    text-align: left;
  }
  .tile:hover { background: var(--bg-elev); border-color: var(--audio-color); }
  .icon {
    width: 36px; height: 36px;
    display: grid; place-items: center;
    background: var(--bg-panel);
    border-radius: 4px;
    color: var(--audio-color);
    flex: 0 0 auto;
  }
  .meta { flex: 1; min-width: 0; }
  .name {
    font-size: 13px;
    white-space: nowrap; text-overflow: ellipsis; overflow: hidden;
  }
  .row { font-size: 11px; color: var(--fg-muted); display: flex; gap: 8px; }

  footer {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 16px;
    border-top: 1px solid var(--border);
    background: var(--bg-elev);
  }
  .hint { flex: 1; font-size: 11px; }
  .btn {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--fg-primary);
    padding: 6px 12px;
    border-radius: 4px;
    cursor: pointer;
  }
  .btn:hover { border-color: var(--audio-color); }
</style>
