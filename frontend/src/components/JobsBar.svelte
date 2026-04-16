<script>
  import { onMount } from 'svelte';
  import { wsState, wsOn, wsStart } from '../lib/ws.svelte.js';
  import StatusLeds from './StatusLeds.svelte';

  const jobs = $state({ map: new Map() });

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
    <span class="idle">keine aktiven Jobs</span>
  {:else}
    {#each active as j (j.id)}
      <span class="job" class:failed={j.status === 'failed'}>
        <i class="fa-solid {j.kind === 'proxy' ? 'fa-film' : j.kind === 'thumbnail' ? 'fa-image' : 'fa-gears'}"></i>
        <span>{j.kind}</span>
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
