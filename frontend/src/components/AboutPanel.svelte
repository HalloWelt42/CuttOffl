<script>
  // Ueber-Panel: Projekt-Info, Lizenz und Haftungshinweise. Verhaelt sich
  // wie das Info-Panel (verschiebbar, schaltbar), hat aber dauerhaften
  // Inhalt. Sidebar-Eintrag "Ueber" oeffnet dieses Fenster.

  import FloatingPanel from './FloatingPanel.svelte';
  import { aboutPanel, closeAbout, persistAboutGeometry } from '../lib/panels.svelte.js';
  import { REPO_URL } from '../lib/meta.js';
  import { openThanks } from '../lib/ui.svelte.js';
</script>

<FloatingPanel
  state={aboutPanel}
  title="Über CuttOffl"
  icon="fa-circle-info"
  onClose={closeAbout}
  onPersist={persistAboutGeometry}
>
  <section class="intro">
    <h2>CuttOffl</h2>
    <p>
      Offline-first Video-Cutter für große Dateien und zügiges Schneiden.
      Läuft lokal, ohne Cloud und ohne Konto. Fokus auf Keyframe-genaues
      verlustfreies Schneiden, mit Option auf frame-genaue Clips bei Bedarf.
    </p>
    <div class="actions">
      <a class="btn" href={REPO_URL} target="_blank" rel="noopener"
         title="CuttOffl-Repository auf GitHub öffnen">
        <i class="fa-brands fa-github"></i> Projekt auf GitHub
      </a>
      <button class="btn btn-primary" onclick={openThanks}
              title="Unterstützungs-Möglichkeiten anzeigen">
        <i class="fa-solid fa-heart"></i> Unterstützen
      </button>
    </div>
  </section>

  <section>
    <h3><i class="fa-solid fa-file-contract"></i> Lizenz</h3>
    <p>
      CuttOffl steht unter der <b>Nicht-kommerziellen Lizenz v2.0</b>,
      basierend auf Creative Commons CC BY-NC-ND 4.0 mit Zusatzbestimmungen
      des Rechteinhabers (private Modifikation erlaubt, keine öffentliche
      Weiterverteilung).
    </p>
    <p>
      Den vollständigen Lizenztext findest du in der Datei
      <code>LICENSE</code> im Projekt-Repository.
    </p>
  </section>

  <section>
    <h3><i class="fa-solid fa-triangle-exclamation"></i> Haftungsausschluss</h3>

    <p><b>Privates, nicht-kommerzielles Projekt.</b></p>
    <p>
      CuttOffl ist ein privat entwickeltes Werkzeug und wird ohne jede
      Gewährleistung bereitgestellt. Es besteht kein Anspruch auf Support,
      Fehlerbehebung, Updates oder Weiterentwicklung. Die Nutzung erfolgt
      ausschließlich auf eigenes Risiko.
    </p>

    <p><b>Keine Gewährleistung.</b></p>
    <p>
      Die Software wird "wie sie ist" ohne Mängelgewähr zur Verfügung gestellt.
      Es wird keine Garantie für Funktionsfähigkeit, Fehlerfreiheit,
      ununterbrochene Verfügbarkeit, Sicherheit oder Eignung für einen
      bestimmten Zweck übernommen.
    </p>

    <p><b>Keine Haftung für Schäden.</b></p>
    <p>
      Der Rechteinhaber haftet in keinem Fall für direkte oder indirekte
      Schäden, entgangene Gewinne, Datenverluste, Ausfallzeiten oder sonstige
      mittelbare Schäden, die aus der Nutzung oder Nichtnutzbarkeit der
      Software entstehen, soweit dies gesetzlich zulässig ist. Bitte
      regelmäßig eigene Sicherungskopien der Originale und Projekte anlegen.
    </p>

    <p><b>Inhalte liegen in deiner Verantwortung.</b></p>
    <p>
      Du bist für alle Videos, Bilder, Tonspuren und sonstigen Inhalte, die
      du mit CuttOffl verarbeitest, selbst verantwortlich. Das betrifft
      insbesondere Urheberrechte, Persönlichkeitsrechte, Markenrechte und
      die Rechte der dargestellten Personen. CuttOffl stellt nur ein Werkzeug
      bereit und prüft keine Inhalte.
    </p>

    <p><b>Nicht für kommerziellen Einsatz.</b></p>
    <p>
      Die Lizenz gestattet ausschließlich private, nicht-kommerzielle Nutzung
      (siehe Abschnitt Lizenz). Für den Einsatz in Unternehmen, Behörden oder
      im Rahmen einer Erwerbstätigkeit ist eine gesonderte Vereinbarung
      erforderlich.
    </p>

    <p><b>Drittkomponenten.</b></p>
    <p>
      CuttOffl greift auf externe Programme zurück (insbesondere FFmpeg/FFprobe).
      Für diese gelten die Lizenzen und Haftungsregelungen der jeweiligen
      Hersteller.
    </p>
  </section>
</FloatingPanel>

<style>
  section { margin-bottom: 18px; }
  section:last-child { margin-bottom: 0; }

  h2 { margin: 0 0 8px; font-size: 22px; font-weight: 700; }
  h3 {
    margin: 0 0 10px;
    font-size: 15px;
    font-weight: 600;
    color: var(--fg-primary);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  h3 i { color: var(--accent); }

  p {
    margin: 0 0 10px;
    font-size: 15px;
    line-height: 1.7;
    color: var(--fg-primary);
  }
  p b { font-weight: 600; }
  code {
    background: var(--bg-elev);
    padding: 1px 6px;
    border-radius: 3px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 13px;
  }
  .intro .actions {
    display: flex;
    gap: 10px;
    margin-top: 12px;
    flex-wrap: wrap;
  }
</style>
