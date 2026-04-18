<script>
  // Mini-Lautsprecher-Button zum Vorlesen von Text-Abschnitten.
  //
  // Benutzung:
  //   <SpeakButton text="Der Text der vorgelesen werden soll." />
  //
  // Oder text als Funktion (wenn der Text dynamisch ist):
  //   <SpeakButton text={() => aktuellerText()} />
  //
  // Design:
  //   - Icon-only, ~22x22 px, passt neben Fließtext
  //   - Klick: speakText -> Backend-Proxy /api/speak
  //   - Während Laden: Spin-Icon
  //   - Während Wiedergabe: Pause-Icon
  //   - Erneuter Klick während Wiedergabe: stoppt (Toggle)
  //   - Klick auf anderen Button: stoppt alten, startet neuen

  import { speak, speakText, stopSpeaking, statusFor } from '../lib/speak.svelte.js';
  import { toast } from '../lib/toast.svelte.js';

  let {
    text = '',
    size = 'sm',      // 'sm' | 'md'
    label = null,     // optionaler sichtbarer Label-Text
  } = $props();

  const resolvedText = $derived(typeof text === 'function' ? text() : text);
  const status = $derived(statusFor(resolvedText));
  const active = $derived(status === 'playing' || status === 'loading');

  function onClick(e) {
    e.stopPropagation();
    if (active) {
      stopSpeaking();
      return;
    }
    void speakText(resolvedText, { toast });
  }
</script>

<button
  type="button"
  class="speak-btn"
  class:is-md={size === 'md'}
  class:is-active={active}
  class:is-loading={status === 'loading'}
  onclick={onClick}
  aria-label={active ? 'Vorlesen stoppen' : 'Vorlesen starten'}
  title={active
    ? 'Vorlesen stoppen'
    : 'Diesen Abschnitt vorlesen lassen (mit der Zeit-Stimme)'}
>
  {#if status === 'loading'}
    <i class="fa-solid fa-circle-notch fa-spin"></i>
  {:else if status === 'playing'}
    <i class="fa-solid fa-pause"></i>
  {:else}
    <i class="fa-solid fa-volume-low"></i>
  {/if}
  {#if label}<span class="lbl">{label}</span>{/if}
</button>

<style>
  .speak-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: 22px;
    height: 22px;
    padding: 0;
    border: 1px solid var(--border);
    background: var(--bg-elev);
    color: var(--fg-muted);
    border-radius: 4px;
    cursor: pointer;
    font-size: 10px;
    line-height: 1;
    transition: background 120ms, color 120ms, border-color 120ms;
    flex-shrink: 0;
    vertical-align: middle;
  }
  .speak-btn.is-md {
    width: 28px; height: 28px; font-size: 12px; border-radius: 6px;
  }
  .speak-btn:hover {
    background: var(--bg-panel);
    color: var(--accent);
    border-color: color-mix(in oklab, var(--accent) 40%, var(--border));
  }
  .speak-btn.is-active {
    background: var(--accent-soft);
    color: var(--accent);
    border-color: color-mix(in oklab, var(--accent) 50%, var(--border));
  }
  .speak-btn.is-loading {
    color: var(--fg-muted);
  }
  .speak-btn .lbl {
    font-size: 11px;
    white-space: nowrap;
  }
  .speak-btn:has(.lbl) {
    width: auto;
    padding: 0 10px;
  }
</style>
