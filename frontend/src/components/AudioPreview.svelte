<script>
  // Live-Preview der Audio-Override-Spur im Editor.
  //
  // Pro AudioClip wird ein unsichtbares <audio>-Element im DOM
  // gehalten. Anhand von editor.playhead, editor.isPlaying und den
  // Clip-Zeiten (timeline_start, src_start, src_end, gain_db) wird
  // fuer jedes Element aktuell:
  //   - die currentTime auf die passende Source-Zeit gesetzt,
  //   - play()/pause() je nach "Playhead-faellt-in-Clip",
  //   - die Lautstaerke aus gain_db berechnet.
  //
  // Mehrere Clips koennen gleichzeitig laufen (Ueberlappungen werden
  // vom Browser natuerlich gemischt).

  import { api } from '../lib/api.js';
  import { editor } from '../lib/editor.svelte.js';

  // Map: clip.id -> HTMLAudioElement (non-reactive, per-key)
  const players = new Map();

  // Svelte-5-Action: registriert das <audio>-Element unter clip.id
  // und raeumt beim Unmount auf.
  function track(node, id) {
    players.set(id, node);
    return {
      update(newId) {
        if (newId !== id) {
          players.delete(id);
          id = newId;
          players.set(id, node);
        }
      },
      destroy() { players.delete(id); },
    };
  }

  function gainToVolume(db) {
    const d = Number(db) || 0;
    // HTML-Audio volume ist 0..1, keine dB-Skala.
    return Math.max(0, Math.min(1, 10 ** (d / 20)));
  }

  // Reaktiv: wann immer Playhead, Play-Zustand, mute_original oder die
  // Clip-Liste sich aendern, Player-Zustand nachziehen.
  $effect(() => {
    const track = editor.edl?.audio_track ?? [];
    const t = editor.playhead || 0;
    const playing = !!editor.isPlaying;

    for (const clip of track) {
      const el = players.get(clip.id);
      if (!el) continue;
      const dur = clip.src_end - clip.src_start;
      const inRange = t >= clip.timeline_start
                   && t < clip.timeline_start + dur;
      el.volume = gainToVolume(clip.gain_db);
      if (inRange && playing) {
        const srcT = clip.src_start + (t - clip.timeline_start);
        // Nur resync wenn Drift > 150 ms, sonst verursacht jedes
        // Browser-timeupdate unnoetigen Seek-Sprung.
        if (Math.abs(el.currentTime - srcT) > 0.15) el.currentTime = srcT;
        if (el.paused) { el.play().catch(() => {}); }
      } else {
        if (!el.paused) el.pause();
      }
    }
  });
</script>

<!-- Headless: keine sichtbare UI, nur Audio-Elemente im DOM. -->
<div class="audio-preview-host" aria-hidden="true">
  {#each editor.edl?.audio_track ?? [] as clip (clip.id)}
    <audio
      preload="auto"
      src={api.audioUrl(clip.file_id)}
      use:track={clip.id}
    ></audio>
  {/each}
</div>

<style>
  .audio-preview-host {
    position: absolute;
    width: 0; height: 0;
    overflow: hidden;
    pointer-events: none;
  }
</style>
