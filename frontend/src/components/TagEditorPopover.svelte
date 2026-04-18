<script>
  // Inline-Tag-Editor als Popover. Öffnet sich direkt neben dem
  // Auslöse-Element, zeigt bestehende Tags als Chips (mit x zum Löschen),
  // ein Input-Feld zum Hinzufügen (Komma oder Enter bestaetigen) und
  // Autocomplete aus allen bereits bekannten Tags.
  //
  // Speichern passiert direkt bei jeder Änderung gegen das Backend,
  // kein separater "Speichern"-Knopf. Schließen per Esc, Klick ausserhalb
  // oder Return auf leerem Input.

  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { toast } from '../lib/toast.svelte.js';
  import { colorFor, parseTags } from '../lib/tags.js';

  let {
    fileId,
    initialTags = [],
    // Vorschlaege aus allen schon vorhandenen Tags
    suggestions = [],
    // Anker-Element relativ zu dem das Popover positioniert wird
    anchor,
    onClose = () => {},
    onChange = () => {},
  } = $props();

  // Snapshot beim Öffnen ist beabsichtigt: das Popover arbeitet danach
  // auf seiner eigenen Liste und speichert nach jeder Änderung zurück.
  // Damit kommen Tag-Aktualisierungen ausserhalb (z. B. anderer Nutzer)
  // erst beim nächsten Öffnen in diesen Editor -- gewolltes Verhalten.
  // svelte-ignore state_referenced_locally
  let tags = $state([...initialTags]);
  let draft = $state('');
  let saving = $state(false);
  // svelte-ignore non_reactive_update
  let hostEl;
  // svelte-ignore non_reactive_update
  let inputEl;
  let pos = $state({ left: 0, top: 0, placement: 'below' });

  function computePos() {
    if (!anchor || !hostEl) return;
    const r = anchor.getBoundingClientRect();
    const w = hostEl.offsetWidth || 320;
    const h = hostEl.offsetHeight || 180;
    let left = r.left;
    let top = r.bottom + 6;
    // Horizontal in den Viewport klemmen
    if (left + w > window.innerWidth - 8) left = window.innerWidth - w - 8;
    if (left < 8) left = 8;
    // Wenn unten kein Platz, nach oben
    if (top + h > window.innerHeight - 8) {
      top = r.top - h - 6;
      pos.placement = 'above';
    } else {
      pos.placement = 'below';
    }
    pos.left = Math.round(left);
    pos.top = Math.round(top);
  }

  async function save() {
    saving = true;
    try {
      const res = await api.setFileTags(fileId, tags);
      const accepted = res.accepted || [];
      const rejected = res.rejected || [];
      tags = accepted;   // zurück in den State, falls Backend weggefiltert hat
      if (rejected.length > 0) {
        toast.warn(`Verworfen: ${rejected.join(', ')}`);
      }
      onChange(accepted);
    } catch (e) {
      toast.error(e.message);
    } finally {
      saving = false;
    }
  }

  async function addDraft() {
    const parts = parseTags(draft);
    if (!parts.length) { draft = ''; return; }
    const lower = new Set(tags.map((t) => t.toLocaleLowerCase('de')));
    for (const p of parts) {
      if (!lower.has(p.toLocaleLowerCase('de'))) {
        tags = [...tags, p];
        lower.add(p.toLocaleLowerCase('de'));
      }
    }
    draft = '';
    await save();
  }

  async function removeTag(t) {
    tags = tags.filter((x) => x !== t);
    await save();
  }

  async function addSuggestion(s) {
    if (tags.some((t) => t.toLocaleLowerCase('de') === s.toLocaleLowerCase('de'))) return;
    tags = [...tags, s];
    await save();
    inputEl?.focus();
  }

  function onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); onClose(); return; }
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      if (draft.trim()) addDraft();
      else onClose();
      return;
    }
    if (e.key === 'Backspace' && !draft && tags.length > 0) {
      // letzten Chip entfernen
      const last = tags[tags.length - 1];
      e.preventDefault();
      removeTag(last);
    }
  }

  function onDocDown(e) {
    if (!hostEl) return;
    if (hostEl.contains(e.target)) return;
    if (anchor && anchor.contains(e.target)) return;
    onClose();
  }

  const filteredSuggestions = $derived.by(() => {
    const lower = new Set(tags.map((t) => t.toLocaleLowerCase('de')));
    const q = draft.trim().toLocaleLowerCase('de');
    return suggestions
      .filter((s) => !lower.has(s.toLocaleLowerCase('de')))
      .filter((s) => !q || s.toLocaleLowerCase('de').includes(q))
      .slice(0, 8);
  });

  onMount(() => {
    computePos();
    inputEl?.focus();
    window.addEventListener('resize', computePos);
    window.addEventListener('scroll', computePos, true);
    document.addEventListener('mousedown', onDocDown);
    return () => {
      window.removeEventListener('resize', computePos);
      window.removeEventListener('scroll', computePos, true);
      document.removeEventListener('mousedown', onDocDown);
    };
  });
</script>

<div class="pop {pos.placement}"
     bind:this={hostEl}
     role="dialog" aria-label="Tags bearbeiten"
     style:left="{pos.left}px" style:top="{pos.top}px">
  <div class="chips">
    {#each tags as t (t)}
      {@const c = colorFor(t)}
      <span class="chip" style="background: {c.bg}; color: {c.fg};">
        <span class="chip-label">{t}</span>
        <button class="chip-x" onclick={() => removeTag(t)}
                title="Diesen Tag entfernen">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </span>
    {/each}
    <input bind:this={inputEl}
           class="chip-input"
           type="text"
           placeholder={tags.length ? 'Weitere Tags...' : 'Tag eingeben, Enter oder Komma bestaetigt'}
           bind:value={draft}
           onkeydown={onKey} />
  </div>

  {#if filteredSuggestions.length > 0}
    <div class="suggest">
      <span class="suggest-label">Vorschläge</span>
      {#each filteredSuggestions as s (s)}
        {@const c = colorFor(s)}
        <button class="chip chip-ghost"
                style="--chip-bg: {c.bg};"
                onclick={() => addSuggestion(s)}
                title="Tag hinzufügen">
          {s}
        </button>
      {/each}
    </div>
  {/if}

  <div class="hint">
    <kbd>Enter</kbd> oder <kbd>,</kbd> hinzufügen  ·
    <kbd>Backspace</kbd> letzten entfernen  ·  <kbd>Esc</kbd> schließen
    {#if saving}  ·  <span class="saving">speichert...</span>{/if}
  </div>
</div>

<style>
  .pop {
    position: fixed;
    z-index: 1500;
    width: 340px;
    background: var(--bg-panel);
    border: 1px solid var(--accent);
    border-radius: 8px;
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.4);
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .chips {
    display: flex; flex-wrap: wrap; gap: 6px;
    padding: 4px;
    min-height: 30px;
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 6px;
    align-items: center;
  }
  .chip {
    display: inline-flex; align-items: center; gap: 2px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.2px;
    padding: 3px 4px 3px 8px;
    border-radius: 10px;
    line-height: 1.2;
    max-width: 220px;
  }
  .chip-label {
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .chip-x {
    background: transparent;
    border: none;
    color: inherit;
    cursor: pointer;
    padding: 1px 4px;
    border-radius: 50%;
    display: grid; place-items: center;
    opacity: 0.7;
  }
  .chip-x:hover { opacity: 1; background: rgba(0,0,0,0.25); }
  .chip-input {
    flex: 1 1 100px;
    min-width: 100px;
    background: transparent;
    border: none;
    outline: none;
    color: var(--fg-primary);
    font: inherit;
    font-size: 13px;
    padding: 3px 4px;
  }

  .suggest {
    display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
    padding: 2px 2px 0;
  }
  .suggest-label {
    font-size: 10px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: var(--fg-muted);
    margin-right: 4px;
  }
  .chip-ghost {
    background: transparent;
    color: var(--fg-primary);
    border: 1px dashed var(--chip-bg, var(--border-strong));
    cursor: pointer;
    font: inherit;
    font-size: 11px;
    font-weight: 500;
    padding: 2px 8px;
    border-radius: 10px;
  }
  .chip-ghost:hover {
    background: var(--chip-bg, var(--accent-soft));
    color: #fff;
  }

  .hint {
    font-size: 11px;
    color: var(--fg-muted);
    padding: 2px 4px 0;
    line-height: 1.5;
  }
  kbd {
    display: inline-block;
    padding: 1px 5px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 10px;
    background: var(--bg-elev);
    border: 1px solid var(--border-strong);
    border-bottom-width: 2px;
    border-radius: 3px;
    color: var(--fg-primary);
  }
  .saving { color: var(--accent); }
</style>
