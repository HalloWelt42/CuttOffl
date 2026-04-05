<script>
  import PanelHeader from '../components/PanelHeader.svelte';
  import { REPO_URL } from '../lib/meta.js';
  import { openThanks } from '../lib/ui.svelte.js';
</script>

<section class="wrap">
  <PanelHeader icon="fa-circle-info" title="Über" subtitle="Projekt, Lizenz und Rechtliches" />

  <div class="body">
    <div class="card block intro">
      <h2>CuttOffl</h2>
      <p class="soft">
        Offline-first Video-Cutter für große Dateien und zügiges Schneiden.
        Läuft lokal, ohne Cloud und ohne Konto. Fokus auf Keyframe-genaues
        verlustfreies Schneiden, mit Option auf frame-genaue Clips bei Bedarf.
      </p>
      <div class="intro-actions">
        <a class="btn" href={REPO_URL} target="_blank" rel="noopener"
           title="CuttOffl-Repository auf GitHub öffnen">
          <i class="fa-brands fa-github"></i> Projekt auf GitHub
        </a>
        <button class="btn btn-primary" onclick={openThanks}
                title="Unterstützungs-Möglichkeiten anzeigen">
          <i class="fa-solid fa-heart"></i> Unterstützen
        </button>
      </div>
    </div>

    <div class="card block">
      <h3><i class="fa-solid fa-file-contract"></i> Lizenz</h3>
      <p>
        CuttOffl steht unter der <b>Nicht-kommerziellen Lizenz v2.0</b>,
        basierend auf Creative Commons CC BY-NC-ND 4.0 mit Zusatzbestimmungen
        des Rechteinhabers (private Modifikation erlaubt, keine öffentliche
        Weiterverteilung).
      </p>
      <p class="soft">
        Den vollständigen Lizenztext findest du in der Datei
        <code>LICENSE</code> im Projekt-Repository.
      </p>
    </div>

    <div class="card block">
      <h3><i class="fa-solid fa-triangle-exclamation"></i> Haftungsausschluss</h3>

      <p><b>Privates, nicht-kommerzielles Projekt.</b></p>
      <p class="soft">
        CuttOffl ist ein privat entwickeltes Werkzeug und wird ohne jede
        Gewährleistung bereitgestellt. Es besteht kein Anspruch auf Support,
        Fehlerbehebung, Updates oder Weiterentwicklung. Die Nutzung erfolgt
        ausschließlich auf eigenes Risiko.
      </p>

      <p><b>Keine Gewährleistung.</b></p>
      <p class="soft">
        Die Software wird „wie sie ist" ohne Mängelgewähr zur Verfügung gestellt.
        Es wird keine Garantie für Funktionsfähigkeit, Fehlerfreiheit,
        ununterbrochene Verfügbarkeit, Sicherheit oder Eignung für einen
        bestimmten Zweck übernommen.
      </p>

      <p><b>Keine Haftung für Schäden.</b></p>
      <p class="soft">
        Der Rechteinhaber haftet in keinem Fall für direkte oder indirekte
        Schäden, entgangene Gewinne, Datenverluste, Ausfallzeiten oder sonstige
        mittelbare Schäden, die aus der Nutzung oder Nichtnutzbarkeit der
        Software entstehen, soweit dies gesetzlich zulässig ist. Bitte
        regelmäßig eigene Sicherungskopien der Originale und Projekte anlegen.
      </p>

      <p><b>Inhalte liegen in deiner Verantwortung.</b></p>
      <p class="soft">
        Du bist für alle Videos, Bilder, Tonspuren und sonstigen Inhalte, die
        du mit CuttOffl verarbeitest, selbst verantwortlich. Das betrifft
        insbesondere Urheberrechte, Persönlichkeitsrechte, Markenrechte und
        die Rechte der dargestellten Personen. CuttOffl stellt nur ein Werkzeug
        bereit und prüft keine Inhalte.
      </p>

      <p><b>Nicht für kommerziellen Einsatz.</b></p>
      <p class="soft">
        Die Lizenz gestattet ausschließlich private, nicht-kommerzielle Nutzung
        (siehe Abschnitt Lizenz). Für den Einsatz in Unternehmen, Behörden oder
        im Rahmen einer Erwerbstätigkeit ist eine gesonderte Vereinbarung
        erforderlich.
      </p>

      <p><b>Drittkomponenten.</b></p>
      <p class="soft">
        CuttOffl greift auf externe Programme zurück (insbesondere FFmpeg/FFprobe).
        Für diese gelten die Lizenzen und Haftungsregelungen der jeweiligen
        Hersteller.
      </p>
    </div>
  </div>
</section>

<style>
  .wrap { display: flex; flex-direction: column; height: 100%; }
  .body {
    padding: 24px;
    overflow: auto;
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 760px;
  }
  .block { padding: 18px; }
  .block h2 { margin: 0 0 8px; font-size: 20px; }
  .block h3 {
    margin: 0 0 10px; font-size: 14px; color: var(--fg-primary);
    display: flex; align-items: center; gap: 8px;
  }
  .block h3 i { color: var(--accent); }
  .block p { margin: 0 0 10px; line-height: 1.6; font-size: 13px; color: var(--fg-muted); }
  .block p b { color: var(--fg-primary); }

  .intro-actions { display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }

  code {
    background: var(--bg-elev);
    padding: 1px 5px;
    border-radius: 3px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
  }
</style>
