// Vorlese-Service (SpeakButton) -- ein Text pro Klick wird an das
// Backend geschickt (/api/speak), das einen TTS-Proxy zu txt2voice
// betreibt und die MP3 zurückschickt. Antwort wird direkt in einem
// zentralen <audio>-Element abgespielt.
//
// Kein Autoplay. Exakt ein Track läuft gleichzeitig: ein neuer Klick
// stoppt den vorigen sauber.

import { persisted, persist } from './persist.svelte.js';

// Einmaliges Hinweis-Flag fuer "Vorlese-Dienst offline" -- damit
// wir den User nicht bei jedem Klick mit dem gleichen Toast
// erschlagen. Bleibt persistent, bis der User Touren/App-Reset macht.
const OFFLINE_HINT_KEY = 'speak.offlineHintShown';

export const speak = $state({
  // id des aktuell laufenden Speech-Elements (beliebiger String -- wir
  // nutzen den sanitized Text-Hash), null wenn nichts läuft
  activeKey: null,
  // 'idle' | 'loading' | 'playing' | 'error'
  status: 'idle',
});

// Das globale Audio-Element. Wird beim ersten speak() erzeugt und
// wiederverwendet -- ein einzelner, browser-akzeptierter Audio-Kanal.
let audioEl = null;

function getAudio() {
  if (audioEl) return audioEl;
  audioEl = new Audio();
  audioEl.addEventListener('ended', () => {
    speak.activeKey = null;
    speak.status = 'idle';
  });
  audioEl.addEventListener('error', () => {
    speak.activeKey = null;
    speak.status = 'error';
  });
  return audioEl;
}

// Schnell-Hash für Button-State -- nicht sicherheitsrelevant, nur
// zum Unterscheiden welcher Button gerade "aktiv" ist.
function textKey(text) {
  let h = 2166136261;
  const s = (text || '').slice(0, 500);
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0).toString(36);
}

function sanitizeClient(text) {
  if (!text) return '';
  return String(text)
    // HTML-Tags raus (sollte nie vorkommen, aber sicher ist sicher)
    .replace(/<[^>]+>/g, ' ')
    // Emojis / Pfeile / Dingbats raus
    .replace(
      /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2190}-\u{21FF}\u{2700}-\u{27BF}\u{2B00}-\u{2BFF}]+/gu,
      ' ',
    )
    // doppelte/mehrfache Leerzeichen + Zeilenumbrüche normalisieren
    .replace(/\s+/g, ' ')
    .trim();
}

/** Stoppt die aktuelle Wiedergabe sauber. */
export function stopSpeaking() {
  if (!audioEl) return;
  try { audioEl.pause(); } catch {}
  audioEl.currentTime = 0;
  audioEl.removeAttribute('src');
  speak.activeKey = null;
  speak.status = 'idle';
}

/** Spricht einen Text aus. Wenn derselbe Text bereits läuft, wird
 *  gestoppt (Toggle-Verhalten). Wenn ein anderer Text läuft, wird
 *  dieser abgebrochen und der neue startet. */
export async function speakText(text, opts = {}) {
  const cleaned = sanitizeClient(text);
  if (!cleaned || cleaned.length < 2) return;
  const key = opts.key || textKey(cleaned);
  // Toggle-Verhalten: gleicher Button erneut -> stoppen
  if (speak.activeKey === key
      && (speak.status === 'playing' || speak.status === 'loading')) {
    stopSpeaking();
    return;
  }
  stopSpeaking();
  speak.activeKey = key;
  speak.status = 'loading';

  let resp;
  try {
    resp = await fetch('/api/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: cleaned }),
    });
  } catch (e) {
    speak.activeKey = null;
    speak.status = 'error';
    maybeShowOfflineHint(opts);
    return;
  }
  if (!resp.ok) {
    speak.activeKey = null;
    speak.status = 'error';
    if (resp.status === 503) maybeShowOfflineHint(opts);
    else if (opts.onError) opts.onError(`HTTP ${resp.status}`);
    return;
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const audio = getAudio();
  audio.src = url;
  try {
    await audio.play();
    speak.status = 'playing';
  } catch (e) {
    // Autoplay-Block -- der Klick selbst ist allerdings User-Gesture,
    // das sollte normalerweise reichen. Wenn nicht: Error-State.
    speak.activeKey = null;
    speak.status = 'error';
  }
}

function maybeShowOfflineHint(opts) {
  if (persisted(OFFLINE_HINT_KEY, false)) return;
  persist(OFFLINE_HINT_KEY, true);
  const toast = opts.toast;
  if (toast) {
    toast.info(
      'Vorlese-Dienst nicht erreichbar. Die Lautsprecher-Symbole '
      + 'neben Texten funktionieren, sobald das Schwester-Projekt '
      + 'txt2voice läuft (http://127.0.0.1:10031).',
      { duration: 8000 },
    );
  }
}

/** Gibt den aktuellen Status für einen Text zurück -- wird von der
 *  SpeakButton-Komponente genutzt, um Icon und Zustand zu rendern. */
export function statusFor(text) {
  const key = textKey(sanitizeClient(text));
  if (speak.activeKey !== key) return 'idle';
  return speak.status;
}
