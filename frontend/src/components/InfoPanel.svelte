<script>
  // Kontextabhaengiges Hilfe-Panel. Inhalt wechselt je nach aktiver View:
  // im Editor gibt es Tastaturkürzel, in der Bibliothek Hinweise zu
  // Ordnern und Drag & Drop, im Export die Erklärung zum Zurückschicken
  // in die Bibliothek, usw. Das Fenster ist frei verschiebbar und
  // schaltbar über den Sidebar-Eintrag "Info".

  import FloatingPanel from './FloatingPanel.svelte';
  import SpeakButton from './SpeakButton.svelte';
  import { infoPanel, closeInfo, persistInfoGeometry } from '../lib/panels.svelte.js';
  import { nav } from '../lib/nav.svelte.js';

  const TITLE_BY_VIEW = {
    dashboard:  'Schnelleinstieg ins Dashboard',
    library:    'Bibliothek -- Tipps und Tastaturkürzel',
    editor:     'Editor -- Tastaturkürzel und Hinweise',
    exports:    'Fertige Videos -- Hinweise',
    settings:   'Einstellungen -- Hinweise',
  };

  const currentTitle = $derived(TITLE_BY_VIEW[nav.view] ?? 'Information');

  // Editor-Shortcuts bleiben die wichtigsten Info-Inhalte
  const EDITOR_SHORTCUTS = [
    ['Leertaste',            'Play / Pause'],
    ['Shift + Leertaste',    'Timeline abspielen (alle Clips)'],
    ['J / L',                '5 s zurück / vor'],
    ['← / →',                '1 Frame zurück / vor (+ Shift = 10 Frames)'],
    [', / .',                'vorheriger / nächster Keyframe'],
    ['I / O',                'In- / Out-Punkt setzen'],
    ['P',                    'Auswahl oder Clip vorspielen'],
    ['Enter',                'Clip aus In/Out erzeugen'],
    ['S',                    'Clip am Playhead teilen'],
    ['Esc',                  'Vorschau / Dialog stoppen'],
    ['Entf / ⌫',             'ausgewählten Clip löschen'],
    ['⌘/Ctrl + Z',           'Undo · + Shift = Redo'],
    ['⌘/Ctrl + Mausrad',     'Timeline zoomen'],
  ];
</script>

<FloatingPanel
  geometry={infoPanel}
  title={currentTitle}
  icon="fa-circle-info"
  dataPanel="info"
  onClose={closeInfo}
  onChange={(p) => Object.assign(infoPanel, p)}
  onPersist={persistInfoGeometry}
>
  {#if nav.view === 'editor'}
    <p class="lead">
      <SpeakButton text="Mit der Tastatur läuft der Schnitt am schnellsten. Die wichtigsten Tasten bleiben auch beim Bewegen dieses Fensters erreichbar -- Escape schließt nur den Hinweis, nicht die Vorschau." />
      Mit der Tastatur läuft der Schnitt am schnellsten. Die wichtigsten
      Tasten bleiben auch beim Bewegen dieses Fensters erreichbar -- Esc
      schließt nur den Hinweis, nicht die Vorschau.
    </p>
    <dl class="kbd">
      {#each EDITOR_SHORTCUTS as [k, desc] (k)}
        <dt><kbd>{k}</kbd></dt>
        <dd>{desc}</dd>
      {/each}
    </dl>

  {:else if nav.view === 'library'}
    <p class="lead">
      <SpeakButton text="Die Bibliothek verwaltet alle hochgeladenen Videos. Ordner sind virtuell -- Dateien bleiben flach im Originale-Verzeichnis, die Baumstruktur lebt nur im Anzeigenamen." />
      Die Bibliothek verwaltet alle hochgeladenen Videos. Ordner sind
      virtuell -- Dateien bleiben flach im Originale-Verzeichnis, die
      Baumstruktur lebt nur im Anzeigenamen.
    </p>
    <h4>Drag &amp; Drop</h4>
    <ul>
      <li>OS-Datei ins Panel ziehen startet den Upload in den aktuellen Ordner.</li>
      <li>Eine oder mehrere markierte Kacheln auf einen Ordner ziehen verschiebt alle.</li>
      <li>Auf den Pfeil nach oben oder eine Breadcrumb-Stufe droppen verschiebt eine Ebene höher.</li>
    </ul>
    <h4>Filter &amp; Suche</h4>
    <ul>
      <li>Suche greift im Dateinamen (Teilstring, Groß-/Kleinschreibung egal).</li>
      <li>Filter nach Status, Codec, Auflösung und Tag sind kombinierbar.</li>
      <li>Mehrfachauswahl per Checkbox erlaubt Verschieben und Löschen in einem Rutsch.</li>
    </ul>
    <h4>Weiteres</h4>
    <ul>
      <li>Beim Hover über einer Kachel scrollt das Thumbnail durch die Sprite-Frames.</li>
      <li>ZIP-Symbol im Kopf lädt den aktuellen Ordner rekursiv als ZIP.</li>
      <li>Duplikate werden per SHA-256 erkannt und bei Bedarf übersprungen.</li>
    </ul>

  {:else if nav.view === 'exports'}
    <p class="lead">
      Hier liegen die fertig gerenderten Clips. Jeder Eintrag hat drei
      typische Aktionen: Vorschau, Download und "In den Editor
      zurückspringen", um das zugehörige Projekt weiter zu bearbeiten.
    </p>
    <h4>Aktionen</h4>
    <ul>
      <li><b>Play</b> spielt das fertige Video direkt im Overlay ab.</li>
      <li><b>Download</b> liefert die Datei mit lesbarem Namen.</li>
      <li><b>Scheren-Symbol</b> öffnet das Ursprungsprojekt im Editor.</li>
      <li><b>Pfeil in die Bibliothek</b> übernimmt den fertigen Clip als neue Quelle.</li>
      <li><b>Papierkorb</b> entfernt nur den Export, das Projekt bleibt.</li>
    </ul>

  {:else if nav.view === 'dashboard'}
    <p class="lead">
      Das Dashboard ist die Übersicht. Kennzahlen und Speicher beziehen
      sich auf den aktuell konfigurierten Datenbereich -- siehe
      Einstellungen für die Pfade.
    </p>
    <ul>
      <li><b>Dateien</b>, <b>Projekte</b> und <b>Fertige Videos</b> zählen den Bestand.</li>
      <li>Fehlgeschlagene Jobs erscheinen nur, wenn welche vorliegen.</li>
      <li>Die Codec-Empfehlung richtet sich nach der erkannten Hardware (VideoToolbox auf dem Mac, V4L2 auf dem Pi, sonst Software).</li>
    </ul>

  {:else if nav.view === 'settings'}
    <p class="lead">
      In den Einstellungen werden nur Dinge gehalten, die an den eigenen
      Rechner gekoppelt sind -- vor allem die Verzeichnisse für Originale
      und fertige Videos. Alles andere an UI-Präferenzen bleibt
      automatisch im Browser.
    </p>
    <ul>
      <li>Pfade brauchen einen Backend-Neustart, damit sie aktiv werden.</li>
      <li>Bereits vorhandene Dateien bleiben am alten Ort.</li>
      <li>Ein leerer Eintrag setzt den jeweiligen Pfad auf den Default zurück.</li>
    </ul>

  {:else}
    <p class="lead">
      Dieses Fenster zeigt Hinweise zur jeweils aktiven Ansicht. Wechsle
      in Bibliothek, Editor oder Fertige Videos -- die Inhalte hier
      passen sich automatisch an.
    </p>
  {/if}
</FloatingPanel>

<style>
  .lead {
    margin: 0 0 14px;
    font-size: 15px;
    line-height: 1.65;
    color: var(--fg-primary);
  }
  h4 {
    margin: 16px 0 6px;
    font-size: 13px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: var(--fg-muted);
  }
  ul {
    margin: 0 0 10px;
    padding-left: 20px;
    line-height: 1.7;
    font-size: 14.5px;
    color: var(--fg-primary);
  }
  ul li { margin-bottom: 4px; }
  ul li b { color: var(--accent); }

  .kbd {
    display: grid;
    grid-template-columns: max-content 1fr;
    column-gap: 18px;
    row-gap: 8px;
    margin: 0;
    font-size: 14px;
  }
  .kbd dt {
    margin: 0;
    display: flex;
    justify-content: flex-end;
  }
  .kbd dd {
    margin: 0;
    color: var(--fg-primary);
    line-height: 1.5;
  }
  kbd {
    display: inline-block;
    padding: 2px 8px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 12px;
    color: var(--fg-primary);
    background: var(--bg-elev);
    border: 1px solid var(--border-strong);
    border-bottom-width: 2px;
    border-radius: 4px;
    white-space: nowrap;
  }
</style>
