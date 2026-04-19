<script>
  import { TOURS } from '../lib/tours.js';
  import {
    tour, startTour, startAllTours, tourCompleted, registerTours,
  } from '../lib/tour.svelte.js';
  import PanelHeader from '../components/PanelHeader.svelte';
  import SpeakButton from '../components/SpeakButton.svelte';

  // Touren im Registry registrieren (idempotent)
  registerTours(TOURS);

  function hasBeenDone(id) {
    return tourCompleted.set.has(id);
  }

  // Gesamte Schritte + geschätzte Laufzeit über alle Touren (grobe
  // Summe der Audio-Annahme: im Schnitt ~25 s pro Schritt + 2 s
  // Puffer = 27 s; für Schritte ohne Audio wird DEMO_FALLBACK_MS
  // benutzt). Wir nehmen hier einen einfachen Mittelwert von 28 s
  // pro Schritt für die Anzeige.
  const totalSteps = TOURS.reduce((s, t) => s + t.steps.length, 0);
  const totalSecs = totalSteps * 28;
  const totalMinutes = Math.round(totalSecs / 60);
</script>

<section class="wrap">
  <PanelHeader iconImg="/tour-help-icon.svg" title="Hilfe & Touren"
               subtitle="Geführte Rundgänge durch die Funktionen" />

  <div class="body">
    <div class="intro">
      <div class="intro-head">
        <p>
          Du bist neu oder willst einen bestimmten Bereich noch einmal
          gezeigt bekommen? Die Touren hier führen dich Schritt für
          Schritt durch die App. Du kannst jederzeit mit
          <kbd>Esc</kbd> abbrechen oder mit den Pfeiltasten vor- und
          zurückspringen.
        </p>
      </div>
      <p class="dim">
        Kein Tour-Schritt löscht etwas, startet einen Render oder
        verändert deine Daten -- es wird nur geklickt und erklärt.
      </p>
    </div>

    <!-- Präsentations-Modus: alle fünf Touren nacheinander, komplett
         autoplayend mit Audio-gesteuertem Advance und Play/Pause. -->
    <article class="tour-card presentation">
      <header>
        <i class="fa-solid fa-circle-play"></i>
        <div class="hd">
          <h3>Kompletter Rundgang</h3>
          <div class="meta mono">
            {TOURS.length} Touren · {totalSteps} Schritte · ca. {totalMinutes} Min
          </div>
        </div>
      </header>
      <p class="desc">
        <SpeakButton text="Spielt alle fünf Touren direkt hintereinander ab, mit vollständiger Audio-Begleitung. Die Tour wartet, bis die Erklärung zu Ende gesprochen ist, und lässt dir noch einen Moment zum Nachlesen -- kein Satz wird abgeschnitten. Mit Pause kannst du jederzeit anhalten, mit Play weiterlaufen. Perfekt als Präsentation oder als Hintergrund-Demo." />
        Spielt alle fünf Touren direkt hintereinander ab, mit
        vollständiger Audio-Begleitung. Die Tour wartet, bis die
        Erklärung zu Ende gesprochen ist, und lässt dir noch einen
        Moment zum Nachlesen -- kein Satz wird abgeschnitten. Mit
        Pause kannst du jederzeit anhalten, mit Play weiterlaufen.
        Perfekt als Präsentation oder als Hintergrund-Demo.
      </p>
      <footer>
        <button class="btn btn-primary" onclick={() => startAllTours('demo')}
                title="Alle Touren nacheinander automatisch abspielen">
          <i class="fa-solid fa-circle-play"></i>
          Kompletten Rundgang starten
        </button>
      </footer>
    </article>

    <div class="tours-grid">
      {#each TOURS as t (t.id)}
        <article class="tour-card" style:border-color={t.color + '55'}>
          <header>
            <i class="fa-solid {t.icon}" style:color={t.color}></i>
            <div class="hd">
              <h3>{t.title}</h3>
              <div class="meta mono">
                {t.steps.length} Schritte · {t.duration}
                {#if hasBeenDone(t.id)}
                  <span class="done">
                    <i class="fa-solid fa-circle-check"></i> abgeschlossen
                  </span>
                {/if}
              </div>
            </div>
          </header>
          <p class="desc">
            {t.description}
          </p>
          <footer>
            {#if t.runnable}
              <button class="btn" onclick={() => startTour(t.id, 'guided')}
                      title="Schritt für Schritt selbst durchklicken">
                <i class="fa-solid fa-hand-pointer"></i>
                Selber klicken
              </button>
            {/if}
            <button class="btn btn-primary" onclick={() => startTour(t.id, 'demo')}
                    title={t.runnable
                      ? 'Tour läuft automatisch durch -- lehn dich zurück'
                      : 'Nur Demo-Modus: erklärt die Funktionen ohne echte Klicks'}>
              <i class="fa-solid fa-play"></i>
              Zeig es mir
            </button>
          </footer>
        </article>
      {/each}
    </div>
  </div>
</section>

<style>
  .wrap { display: flex; flex-direction: column; height: 100%; }
  .body {
    padding: 20px 24px;
    overflow-y: auto;
    flex: 1;
  }
  .intro {
    max-width: 720px;
    margin-bottom: 20px;
    line-height: 1.6;
  }
  .intro-head {
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }
  .intro-head p { flex: 1; }
  .intro p { margin: 0 0 8px; }
  .desc :global(.speak-btn) {
    margin-right: 4px;
    vertical-align: baseline;
  }
  .intro .dim { color: var(--fg-muted); font-size: 13px; }
  .intro kbd {
    background: var(--bg-elev);
    border: 1px solid var(--border-strong);
    border-radius: 4px;
    padding: 1px 6px;
    font-family: var(--font-mono);
    font-size: 11px;
  }

  .tours-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 14px;
    max-width: 1100px;
  }
  .tour-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 16px;
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    transition: transform 120ms, border-color 120ms;
  }
  .tour-card:hover {
    transform: translateY(-1px);
  }
  .tour-card header {
    display: flex;
    gap: 14px;
    align-items: flex-start;
  }
  .tour-card header > i {
    font-size: 24px;
    width: 32px;
    text-align: center;
    flex: 0 0 auto;
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.3));
  }
  .tour-card .hd h3 {
    margin: 0 0 4px;
    font-size: 15px;
    font-weight: 600;
  }
  .tour-card .meta {
    font-size: 11px;
    color: var(--fg-muted);
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }
  .done {
    color: var(--success);
    display: inline-flex;
    gap: 4px;
    align-items: center;
  }
  .tour-card .desc {
    margin: 4px 0 0;
    font-size: 13px;
    line-height: 1.5;
    color: var(--fg-muted);
    flex: 1;
  }
  .tour-card footer {
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }

  /* Präsentations-Karte: prominenter, volle Breite */
  .tour-card.presentation {
    margin-bottom: 18px;
    max-width: 1100px;
    background: linear-gradient(
      135deg,
      color-mix(in oklab, var(--accent) 18%, var(--bg-panel)) 0%,
      var(--bg-panel) 60%
    );
    border-color: color-mix(in oklab, var(--accent) 45%, var(--border));
  }
  .tour-card.presentation header > i {
    color: var(--accent);
    font-size: 30px;
  }
  .tour-card.presentation .desc {
    max-width: 720px;
  }
</style>
