<script>
  import { onMount } from 'svelte';
  import { wsState, wsOn, wsStart } from '../lib/ws.svelte.js';
  import StatusLeds from './StatusLeds.svelte';

  const jobs = $state({ map: new Map() });

  // Laien-verstaendliche Bezeichnung pro Job-Typ. Die rohen kinds
  // (proxy, thumbnail, sprite, ...) sind Entwickler-Jargon und
  // gehoeren nicht in die UI.
  const KIND_INFO = {
    proxy:      { label: 'Vorschau-Video wird erstellt',  icon: 'fa-film' },
    thumbnail:  { label: 'Vorschaubild wird erzeugt',     icon: 'fa-image' },
    sprite:     { label: 'Timeline-Miniaturen',           icon: 'fa-table-cells' },
    waveform:   { label: 'Audio-Wellenform',              icon: 'fa-wave-square' },
    keyframes:  { label: 'Schnittpunkte werden erfasst',  icon: 'fa-flag' },
    transcribe: { label: 'Untertitel werden transkribiert', icon: 'fa-closed-captioning' },
    render:     { label: 'Video wird gerendert',          icon: 'fa-clapperboard' },
  };
  function labelFor(k)  { return KIND_INFO[k]?.label ?? k ?? 'Aufgabe'; }
  function iconFor(k)   { return KIND_INFO[k]?.icon  ?? 'fa-gears'; }

  onMount(() => {
    wsStart();
    return wsOn((msg) => {
      if (msg.type === 'job_event' || msg.type === 'job_progress') {
        const j = msg.job ?? { id: msg.job_id, kind: msg.kind, progress: msg.progress, file_id: msg.file_id, status: 'running' };
        const prev = jobs.map.get(j.id) ?? {};
        const merged = { ...prev, ...j };
        // Fertige/fehlerhafte nach 2.5s entfernen
        jobs.map = new Map(jobs.map).set(j.id, merged);
        if (merged.status === 'completed' || merged.status === 'failed') {
          setTimeout(() => {
            const next = new Map(jobs.map);
            next.delete(j.id);
            jobs.map = next;
          }, 2500);
        }
      }
    });
  });

  const active = $derived(Array.from(jobs.map.values()));
</script>

<div class="bar mono">
  <!-- LEDs fuer alle Dienste, die ausfallen koennen. Ersetzt die
       frueher einzelne "verbunden"-Anzeige, die nur den WebSocket
       bedeutete und bei Backend- oder Transkriptions-Ausfall nichts
       sagte. -->
  <StatusLeds />
  <span class="sep"></span>

  {#if active.length === 0}
    <span class="idle">keine Aufgaben in Arbeit</span>
  {:else}
    {#each active as j (j.id)}
      <span class="job" class:failed={j.status === 'failed'}
            title={labelFor(j.kind)}>
        <i class="fa-solid {iconFor(j.kind)}"></i>
        <span class="lbl">{labelFor(j.kind)}</span>
        {#if j.status === 'failed'}
          <span class="err">fehlgeschlagen</span>
        {:else}
          <span class="pct">{Math.round((j.progress ?? 0) * 100)} %</span>
          <div class="prog"><div class="fill" style:width={`${(j.progress ?? 0) * 100}%`}></div></div>
        {/if}
      </span>
    {/each}
  {/if}
</div>

<style>
  .bar {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 6px 14px;
    border-top: 1px solid var(--border);
    background: var(--bg-sink);
    color: var(--fg-muted);
    font-size: 12px;
    flex-wrap: wrap;
    min-height: 32px;
  }
  .sep {
    width: 1px;
    height: 16px;
    background: var(--border);
    margin: 0 2px;
    display: inline-block;
  }
  .idle { color: var(--fg-faint); font-style: italic; }
  .job {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--fg-primary);
  }
  .job.failed { color: var(--danger); }
  .job .lbl {
    max-width: 260px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .err { color: var(--danger); }
  .pct { min-width: 38px; text-align: right; color: var(--fg-muted); }
  .prog {
    width: 80px;
    height: 4px;
    background: var(--bg-elev);
    border-radius: 2px;
    overflow: hidden;
  }
  .fill {
    height: 100%;
    background: var(--accent);
    transition: width 150ms linear;
  }
</style>
