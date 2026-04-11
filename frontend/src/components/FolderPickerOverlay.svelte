<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { folderPicker, pickerOk, pickerCancel } from '../lib/folderPicker.svelte.js';

  let folders = $state([]);
  let loading = $state(false);
  let newName = $state('');

  async function refresh() {
    loading = true;
    try {
      const raw = await api.listFolders();
      // Sortieren nach Pfad, Wurzel zuerst
      folders = raw.sort((a, b) => (a.path || '').localeCompare(b.path || ''));
    } catch {}
    finally { loading = false; }
  }

  $effect(() => {
    if (folderPicker.open) refresh();
  });

  function depthOf(path) {
    if (!path) return 0;
    return path.split('/').length;
  }

  function select(path) {
    folderPicker.selected = path;
  }

  async function createHere() {
    const clean = newName.trim();
    if (!clean) return;
    if (/[\/\\:]/.test(clean)) return;
    // Ordner sind virtuell -- Auswahl setzen, der Ordner entsteht beim
    // naechsten Move/Upload in diesen Pfad. Wir zeigen ihn sofort in der
    // Liste.
    const base = folderPicker.selected || '';
    const full = base ? `${base}/${clean}` : clean;
    folderPicker.selected = full;
    newName = '';
    // optimistic: als Pseudo-Eintrag in die Liste, falls noch nicht da
    if (!folders.find((f) => f.path === full)) {
      folders = [...folders, {
        path: full, name: clean, parent: base,
        direct_count: 0, total_count: 0, _virtual: true,
      }].sort((a, b) => (a.path || '').localeCompare(b.path || ''));
    }
  }

  function onKey(e) {
    if (!folderPicker.open) return;
    if (e.key === 'Escape') { e.preventDefault(); pickerCancel(); }
    else if (e.key === 'Enter' && !e.target?.matches?.('input')) {
      e.preventDefault();
      pickerOk();
    }
  }
  onMount(() => {
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });
</script>

{#if folderPicker.open}
  <div class="backdrop" role="presentation" onclick={pickerCancel}>
    <div class="modal" role="dialog" aria-modal="true"
         aria-labelledby="fp-title"
         onclick={(e) => e.stopPropagation()}>
      <header>
        <i class="fa-solid fa-folder-tree"></i>
        <h2 id="fp-title">{folderPicker.title}</h2>
        <button class="x" onclick={pickerCancel}
                aria-label="Schließen" title="Schließen (Esc)">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </header>

      <div class="body">
        {#if loading}
          <div class="empty soft">Lade Ordner…</div>
        {:else}
          <ul class="tree">
            {#each folders as f (f.path)}
              {@const d = depthOf(f.path)}
              <li
                class="item"
                class:selected={folderPicker.selected === f.path}
                style:padding-left="{12 + d * 18}px"
              >
                <button onclick={() => select(f.path)}
                        ondblclick={() => { select(f.path); pickerOk(); }}
                        title={f.path || 'Wurzel'}>
                  <i class="fa-solid {f.path ? 'fa-folder' : 'fa-house'}"></i>
                  <span class="name">{f.path ? f.name : 'Wurzel'}</span>
                  <span class="count mono">
                    {f.total_count || 0}
                  </span>
                  {#if f._virtual}<span class="new">neu</span>{/if}
                </button>
              </li>
            {/each}
          </ul>
        {/if}

        <div class="new-folder">
          <i class="fa-solid fa-folder-plus"></i>
          <input type="text" bind:value={newName}
                 placeholder={folderPicker.selected
                   ? `Neuer Unterordner in "${folderPicker.selected}"`
                   : 'Neuer Ordner auf Wurzel-Ebene'}
                 onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); createHere(); } }} />
          <button class="btn" type="button" onclick={createHere}
                  disabled={!newName.trim()}
                  title="Neuen Ordner innerhalb des ausgewählten Ordners anlegen">
            Hier anlegen
          </button>
        </div>
      </div>

      <footer>
        <div class="target">
          Ziel:
          <span class="path mono">{folderPicker.selected || '— Wurzel —'}</span>
        </div>
        <div class="actions">
          <button class="btn" onclick={pickerCancel}>Abbrechen</button>
          <button class="btn btn-primary" onclick={pickerOk}>
            <i class="fa-solid fa-check"></i> Hierhin verschieben
          </button>
        </div>
      </footer>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.6);
    backdrop-filter: blur(2px);
    display: grid; place-items: center;
    z-index: 1600;
  }
  .modal {
    width: min(560px, 94vw);
    max-height: 84vh;
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
    padding: 12px 14px;
    background: var(--bg-elev);
    border-bottom: 1px solid var(--border);
  }
  header > i { color: var(--accent); font-size: 16px; }
  header h2 { margin: 0; font-size: 15px; flex: 1; }
  .x {
    background: transparent; border: none; color: var(--fg-muted);
    cursor: pointer; padding: 4px 8px; border-radius: 4px;
  }
  .x:hover { color: var(--fg-primary); background: var(--bg-panel); }

  .body {
    padding: 10px 10px;
    display: flex; flex-direction: column; gap: 10px;
    overflow: auto;
    flex: 1 1 auto;
    min-height: 220px;
  }
  .empty { padding: 16px; text-align: center; color: var(--fg-faint); }

  .tree { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 2px; }
  .item button {
    display: flex; align-items: center; gap: 10px;
    width: 100%;
    background: transparent; border: 1px solid transparent; border-radius: 6px;
    color: var(--fg-primary);
    text-align: left; padding: 6px 8px;
    font: inherit; font-size: 13px;
    cursor: pointer;
  }
  .item button:hover { background: var(--bg-elev); border-color: var(--border); }
  .item.selected button {
    background: var(--accent-soft);
    border-color: var(--accent);
  }
  .item i { color: var(--accent); width: 16px; text-align: center; }
  .item .name { flex: 1 1 auto; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .item .count {
    font-size: 11px; color: var(--fg-muted);
    background: var(--bg-elev); padding: 1px 8px; border-radius: 10px;
  }
  .item .new {
    font-size: 10px; letter-spacing: 0.5px; text-transform: uppercase;
    background: color-mix(in oklab, var(--success) 25%, var(--bg-elev));
    color: var(--success);
    padding: 1px 6px; border-radius: 10px;
  }

  .new-folder {
    display: flex; align-items: center; gap: 8px;
    padding: 8px;
    border-top: 1px dashed var(--border);
    margin-top: 4px;
  }
  .new-folder > i { color: var(--fg-muted); }
  .new-folder input {
    flex: 1 1 auto;
    background: var(--bg-elev);
    color: var(--fg-primary);
    border: 1px solid var(--border-strong);
    border-radius: 6px;
    padding: 7px 10px;
    font: inherit;
  }
  .new-folder input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-soft);
  }

  footer {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 14px;
    background: var(--bg-sink);
    border-top: 1px solid var(--border);
  }
  .target { flex: 1 1 auto; font-size: 12px; color: var(--fg-muted); }
  .target .path { color: var(--fg-primary); font-size: 12px; margin-left: 6px; }
  .actions { display: flex; gap: 8px; }
</style>
