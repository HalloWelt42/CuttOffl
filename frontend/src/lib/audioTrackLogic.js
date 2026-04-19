// Reine Logik-Operationen auf der Audio-Track-Liste (keine Svelte-
// Runes, kein State). Wird von editor.svelte.js fuer addAudioClip,
// splitAudioAtPlayhead, setAudioClipOffset etc. genutzt und ist
// isoliert mit Vitest testbar.
//
// Alle Funktionen sind pur: sie nehmen die aktuelle Clip-Liste +
// Parameter und geben die neue Clip-Liste zurueck. State-Bezug,
// Undo/Redo und Persistenz liegen beim Aufrufer.

const MIN_DUR = 0.05;

function round3(v) { return Number((Number(v) || 0).toFixed(3)); }

function uid() {
  return 'c' + Math.random().toString(36).slice(2, 10);
}

function sortByStart(list) {
  return [...list].sort((a, b) => a.timeline_start - b.timeline_start);
}

/** Neuen AudioClip erzeugen und am gegebenen Platz in die Liste
 *  einfuegen. duration_s ist die Dauer der Quelldatei (Obergrenze
 *  fuer src_end). */
export function addClip(list, file_id, duration_s, timeline_start = 0) {
  const dur = Math.max(MIN_DUR, Number(duration_s) || MIN_DUR);
  const clip = {
    id: uid(),
    file_id,
    src_start: 0,
    src_end: round3(dur),
    timeline_start: Math.max(0, round3(timeline_start)),
    gain_db: 0,
    fade_in_s: 0,
    fade_out_s: 0,
  };
  return { list: sortByStart([...(list || []), clip]), clip };
}

/** Teilt den Clip, der unter `playhead` (in Video-Timeline-Sekunden)
 *  liegt, in zwei Teile. Der rechte Teil erbt src-Offsets nahtlos,
 *  so dass der Inhalt an der Schnittkante nicht springt. Gibt
 *  { list, rightId } zurueck oder null, wenn kein Clip getroffen. */
export function splitAtPlayhead(list, playhead) {
  if (!Array.isArray(list)) return null;
  const t = Number(playhead) || 0;
  const idx = list.findIndex((c) => {
    const dur = c.src_end - c.src_start;
    return t > c.timeline_start + 0.01
        && t < c.timeline_start + dur - 0.01;
  });
  if (idx < 0) return null;
  const orig = list[idx];
  const offsetInClip = t - orig.timeline_start;
  const cutSrc = round3(orig.src_start + offsetInClip);
  const left = {
    ...orig,
    src_end: cutSrc,
    fade_out_s: 0,     // Fade-out wandert auf den rechten Teil
  };
  const right = {
    id: uid(),
    file_id: orig.file_id,
    src_start: cutSrc,
    src_end: orig.src_end,
    timeline_start: round3(t),
    gain_db: orig.gain_db,
    fade_in_s: 0,
    fade_out_s: orig.fade_out_s,
  };
  const newList = sortByStart([
    ...list.slice(0, idx),
    left,
    right,
    ...list.slice(idx + 1),
  ]);
  return { list: newList, rightId: right.id };
}

/** timeline_start eines Clips aendern. Negative Werte werden auf 0
 *  geklemmt (wir erlauben keinen Audio-Vorlauf vor Video-Start). */
export function setClipOffset(list, id, timeline_start) {
  if (!Array.isArray(list)) return list;
  const next = list.map((c) => {
    if (c.id !== id) return c;
    return { ...c, timeline_start: Math.max(0, round3(timeline_start)) };
  });
  return sortByStart(next);
}

/** src_start / src_end trimmen. Erzwingt eine Mindest-Dauer von 50 ms
 *  und stellt sicher, dass src_start <= src_end. */
export function setClipRange(list, id, src_start, src_end) {
  if (!Array.isArray(list)) return list;
  return list.map((c) => {
    if (c.id !== id) return c;
    const s = Math.max(0, Math.min(Number(src_start), Number(src_end)));
    const eMax = Math.max(Number(src_start), Number(src_end));
    const e = Math.max(s + MIN_DUR, eMax);
    return { ...c, src_start: round3(s), src_end: round3(e) };
  });
}

/** Gain in dB, geklemmt auf -30..+12. */
export function setClipGain(list, id, gain_db) {
  if (!Array.isArray(list)) return list;
  const g = Math.max(-30, Math.min(12, Number(gain_db) || 0));
  return list.map((c) => c.id === id ? { ...c, gain_db: g } : c);
}

/** Fade-In / Fade-Out in Sekunden (0..10). Nur die definierten
 *  Parameter werden angefasst; der jeweils andere bleibt stehen. */
export function setClipFades(list, id, fade_in_s, fade_out_s) {
  if (!Array.isArray(list)) return list;
  return list.map((c) => {
    if (c.id !== id) return c;
    const next = { ...c };
    if (fade_in_s != null) {
      next.fade_in_s = Math.max(0, Math.min(10, Number(fade_in_s) || 0));
    }
    if (fade_out_s != null) {
      next.fade_out_s = Math.max(0, Math.min(10, Number(fade_out_s) || 0));
    }
    return next;
  });
}

/** Clip aus der Liste entfernen. */
export function deleteClip(list, id) {
  if (!Array.isArray(list)) return list;
  return list.filter((c) => c.id !== id);
}
