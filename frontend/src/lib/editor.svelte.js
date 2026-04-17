// Editor-State: EDL, Playhead, Selektion, Undo/Redo, Auto-Save ans Backend.

import { api } from './api.js';
import { toast } from './toast.svelte.js';
import { persisted, persist as persistLocal } from './persist.svelte.js';

const HIST_MAX = 80;

function uid() {
  return 'c' + Math.random().toString(36).slice(2, 10);
}

function emptyEdl(fileId) {
  return {
    source_file_id: fileId,
    timeline: [],
    output: { codec: 'h264', resolution: 'source', container: 'mp4', crf: 23,
              audio_codec: 'aac', audio_bitrate: '160k' },
  };
}

function cloneEdl(e) { return JSON.parse(JSON.stringify(e)); }

export const editor = $state({
  fileId: null,
  file: null,
  project: null,
  projectId: null,
  edl: null,
  keyframes: [],
  duration: 0,
  playhead: 0,
  isPlaying: false,
  selectedClipId: null,
  snapOn: persisted('editor.snapOn', true),
  dirty: false,
  saving: false,
  rendering: false,
  renderProgress: 0,
  renderPhase: '',
  history: [],
  future: [],
  // Preview / Playback-Steuerung
  preview: null,           // { kind: 'range'|'clip'|'timeline', start, end, clipIndex?, autoPlay? }
  playingClipId: null,     // id des aktuell abspielenden Clips (fuer Timeline-Highlight)
  // Timeline-Visualisierung
  spriteMeta: null,        // { interval, tile_w, tile_h, cols, rows, count }
  spriteImage: null,       // HTMLImageElement (wird bei load befuellt)
  waveform: null,          // { samples_per_second, count, peaks: [0..1] }
  // Timeline-Ansicht
  followOn: persisted('editor.followOn', true),
  // Timeline-Zoom in Pixel pro Sekunde. Die Timeline-Komponente spiegelt
  // diesen Wert in ihren lokalen Zustand und schreibt Mausrad-Zoom hierher
  // zurueck. So kann die Editor-Toolbar Zoom-Presets setzen.
  timelineZoom: persisted('editor.timelineZoom', 40),
  // Transkript -- Segmente aus SRT, aktiver Tab, Untertitel-Overlay
  transcript: null,          // { segments, language, model, has_transcript }
  transcribing: false,
  transcribePct: 0,
  rightTab: persisted('editor.rightTab', 'exports'),   // 'exports' | 'transcript'
  subtitlesOn: persisted('editor.subtitlesOn', true),
});

let saveTimer = null;

function pushHistory() {
  if (!editor.edl) return;
  editor.history.push(cloneEdl(editor.edl));
  if (editor.history.length > HIST_MAX) editor.history.shift();
  editor.future = [];
  editor.dirty = true;
  scheduleSave();
}

function scheduleSave() {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => void persist(), 600);
}

async function persist() {
  if (!editor.projectId || !editor.edl || editor.saving) return;
  editor.saving = true;
  try {
    await api.updateProject(editor.projectId, { edl: editor.edl });
    editor.dirty = false;
  } catch (e) {
    toast.error(`EDL-Speichern: ${e.message}`);
  } finally {
    editor.saving = false;
  }
}

// Public API -----------------------------------------------------------------

export async function loadFile(fileId) {
  if (editor.fileId === fileId && editor.edl) return;
  // reset
  Object.assign(editor, {
    fileId,
    file: null,
    project: null,
    projectId: null,
    edl: null,
    keyframes: [],
    duration: 0,
    playhead: 0,
    isPlaying: false,
    selectedClipId: null,
    dirty: false,
    history: [],
    future: [],
    rendering: false,
    renderProgress: 0,
    renderPhase: '',
    spriteMeta: null,
    spriteImage: null,
    waveform: null,
  });

  try {
    const [file, kf] = await Promise.all([
      api.getFile(fileId),
      api.keyframes(fileId).catch(() => ({ keyframes: [] })),
    ]);
    editor.file = file;
    editor.duration = file.duration_s || 0;
    editor.keyframes = kf.keyframes || [];

    // vorhandenes Projekt finden oder neu anlegen
    const projects = await api.listProjects();
    let p = projects.find((x) => x.source_file_id === fileId);
    if (!p) {
      p = await api.createProject({
        name: (file.original_name || fileId).replace(/\.[^.]+$/, '') + ' -- Schnitt',
        source_file_id: fileId,
        edl: emptyEdl(fileId),
      });
    }
    editor.project = p;
    editor.projectId = p.id;
    editor.edl = p.edl || emptyEdl(fileId);

    // Sprite + Waveform optional laden (gibt's nur nach Proxy-Fertigstellung)
    if (file.has_sprite) void loadSprite(fileId);
    if (file.has_waveform) void loadWaveform(fileId);
    void loadTranscript(fileId);
  } catch (e) {
    toast.error(`Projekt laden: ${e.message}`);
  }
}

export async function loadProject(projectId) {
  // Laedt ein bestimmtes Projekt (mit seiner Quelldatei). Anders als
  // loadFile, das fuer eine Datei automatisch das erste vorhandene Projekt
  // verwendet oder ein neues anlegt, wird hier genau dieses Projekt
  // verwendet -- wichtig fuer Export-Rueckkehr in den Editor.
  try {
    const project = await api.getProject(projectId);
    const fileId = project.source_file_id;
    if (!fileId) {
      toast.error('Projekt hat keine Quelldatei');
      return;
    }

    // Reset
    Object.assign(editor, {
      fileId,
      file: null,
      project: null,
      projectId: null,
      edl: null,
      keyframes: [],
      duration: 0,
      playhead: 0,
      isPlaying: false,
      selectedClipId: null,
      dirty: false,
      history: [],
      future: [],
      rendering: false,
      renderProgress: 0,
      renderPhase: '',
      spriteMeta: null,
      spriteImage: null,
      waveform: null,
    });

    const [file, kf] = await Promise.all([
      api.getFile(fileId),
      api.keyframes(fileId).catch(() => ({ keyframes: [] })),
    ]);
    editor.file = file;
    editor.duration = file.duration_s || 0;
    editor.keyframes = kf.keyframes || [];
    editor.project = project;
    editor.projectId = project.id;
    editor.edl = project.edl || emptyEdl(fileId);

    if (file.has_sprite) void loadSprite(fileId);
    if (file.has_waveform) void loadWaveform(fileId);
    void loadTranscript(fileId);
  } catch (e) {
    toast.error(`Projekt laden: ${e.message}`);
  }
}

export async function loadSprite(fileId) {
  try {
    const meta = await api.spriteMeta(fileId);
    const img = new Image();
    img.onload = () => {
      if (editor.fileId !== fileId) return;
      editor.spriteImage = img;
      editor.spriteMeta = meta;
    };
    img.onerror = () => {};
    img.src = api.spriteUrl(fileId);
  } catch {}
}

export async function loadWaveform(fileId) {
  try {
    const wf = await api.waveform(fileId);
    if (editor.fileId !== fileId) return;
    editor.waveform = wf;
  } catch {}
}

export function seek(t) {
  editor.playhead = Math.max(0, Math.min(editor.duration, t));
}

export function snapTime(t) {
  if (!editor.snapOn || editor.keyframes.length === 0) return t;
  let best = editor.keyframes[0];
  let bestD = Math.abs(t - best);
  for (const k of editor.keyframes) {
    const d = Math.abs(t - k);
    if (d < bestD) { best = k; bestD = d; }
  }
  return best;
}

export function jumpToPrevKeyframe() {
  if (!editor.keyframes.length) return;
  const eps = 0.05;
  const before = editor.keyframes.filter((k) => k < editor.playhead - eps);
  if (!before.length) { seek(editor.keyframes[0]); return; }
  seek(before[before.length - 1]);
}

export function jumpToNextKeyframe() {
  if (!editor.keyframes.length) return;
  const eps = 0.05;
  const after = editor.keyframes.find((k) => k > editor.playhead + eps);
  if (after == null) return;
  seek(after);
}

function insertSorted(clip) {
  const tl = editor.edl.timeline.slice();
  tl.push(clip);
  tl.sort((a, b) => a.src_start - b.src_start);
  editor.edl.timeline = tl;
}

export function addClipFromRange(start, end) {
  if (!editor.edl) return;
  if (end <= start) return;
  pushHistory();
  const s = editor.snapOn ? snapTime(start) : start;
  const e = editor.snapOn ? snapTime(end) : end;
  const clip = {
    id: uid(),
    src_start: Number(Math.min(s, e).toFixed(3)),
    src_end: Number(Math.max(s, e).toFixed(3)),
    mode: editor.snapOn ? 'copy' : 'reencode',
    effects: [],
  };
  if (clip.src_end - clip.src_start < 0.1) clip.src_end = clip.src_start + 0.1;
  insertSorted(clip);
  editor.selectedClipId = clip.id;
}

export function splitAtPlayhead() {
  if (!editor.edl) return;
  const t = editor.playhead;
  const clip = editor.edl.timeline.find(
    (c) => t > c.src_start + 0.01 && t < c.src_end - 0.01,
  );
  if (!clip) {
    toast.info('Playhead liegt in keinem Clip');
    return;
  }
  pushHistory();
  const cut = editor.snapOn ? snapTime(t) : t;
  const right = {
    id: uid(),
    src_start: cut,
    src_end: clip.src_end,
    mode: clip.mode,
    effects: [...(clip.effects || [])],
  };
  clip.src_end = cut;
  insertSorted(right);
  editor.selectedClipId = right.id;
}

export function deleteSelected() {
  if (!editor.edl || !editor.selectedClipId) return;
  pushHistory();
  editor.edl.timeline = editor.edl.timeline.filter((c) => c.id !== editor.selectedClipId);
  editor.selectedClipId = null;
}

export function setClipRange(id, start, end) {
  const c = editor.edl?.timeline.find((x) => x.id === id);
  if (!c) return;
  pushHistory();
  c.src_start = Math.max(0, Math.min(start, end));
  c.src_end = Math.min(editor.duration, Math.max(start, end));
  editor.edl.timeline = editor.edl.timeline.slice().sort((a, b) => a.src_start - b.src_start);
}

export function toggleClipMode(id) {
  const c = editor.edl?.timeline.find((x) => x.id === id);
  if (!c) return;
  pushHistory();
  c.mode = c.mode === 'copy' ? 'reencode' : 'copy';
}

export function selectClip(id) { editor.selectedClipId = id; }

export function undo() {
  if (!editor.history.length) return;
  editor.future.push(cloneEdl(editor.edl));
  editor.edl = editor.history.pop();
  editor.dirty = true;
  scheduleSave();
}

export function redo() {
  if (!editor.future.length) return;
  editor.history.push(cloneEdl(editor.edl));
  editor.edl = editor.future.pop();
  editor.dirty = true;
  scheduleSave();
}

export function setOutput(patch) {
  if (!editor.edl) return;
  pushHistory();
  editor.edl.output = { ...editor.edl.output, ...patch };
}

export function setSnap(v) {
  editor.snapOn = !!v;
  persistLocal('editor.snapOn', editor.snapOn);
}

export function setFollow(v) {
  editor.followOn = !!v;
  persistLocal('editor.followOn', editor.followOn);
}

// ---------------------------------------------------------------------------
// Preview-Playback: Bereich, einzelner Clip, oder ganze Timeline.
// Der Player-Component ruft tickPreview(t) bei jedem timeupdate auf.
// Dieser Callback entscheidet, ob der Player weiterspringen oder stoppen soll.
// Rueckgabe: { seekTo: number } oder { stop: true } oder null.
// ---------------------------------------------------------------------------

export function startRangePreview(start, end) {
  if (end <= start) return;
  editor.preview = { kind: 'range', start, end, autoPlay: true };
  editor.playingClipId = null;
  seek(start);
}

export function startClipPreview(clipId) {
  const clip = editor.edl?.timeline.find((c) => c.id === clipId);
  if (!clip) return;
  editor.preview = { kind: 'clip', start: clip.src_start, end: clip.src_end,
                     clipId, autoPlay: true };
  editor.playingClipId = clip.id;
  seek(clip.src_start);
}

export function startTimelinePreview() {
  if (!editor.edl?.timeline.length) return;
  const tl = editor.edl.timeline.slice().sort((a, b) => a.src_start - b.src_start);
  editor.preview = {
    kind: 'timeline',
    clipIndex: 0,
    clips: tl,
    start: tl[0].src_start,
    end: tl[0].src_end,
    autoPlay: true,
  };
  editor.playingClipId = tl[0].id;
  seek(tl[0].src_start);
}

export function stopPreview() {
  editor.preview = null;
  editor.playingClipId = null;
}

export function tickPreview(t) {
  const p = editor.preview;
  if (!p) return null;
  if (t < p.end - 0.02) return null;

  if (p.kind === 'timeline') {
    const next = p.clipIndex + 1;
    if (next < p.clips.length) {
      const c = p.clips[next];
      p.clipIndex = next;
      p.start = c.src_start;
      p.end = c.src_end;
      editor.playingClipId = c.id;
      return { seekTo: c.src_start };
    }
    stopPreview();
    return { stop: true };
  }

  // range oder clip → Ende erreicht
  stopPreview();
  return { stop: true };
}

export async function saveNow() { if (saveTimer) clearTimeout(saveTimer); await persist(); }

export async function startRender(clipId = null) {
  if (!editor.projectId) return null;
  if (!editor.edl?.timeline.length) {
    toast.warn('Timeline ist leer -- nichts zum Rendern');
    return null;
  }
  if (clipId && !editor.edl.timeline.find((c) => c.id === clipId)) {
    toast.error('Clip nicht mehr vorhanden');
    return null;
  }
  await saveNow();
  editor.rendering = true;
  editor.renderProgress = 0;
  editor.renderPhase = 'queued';
  try {
    const { job_id } = await api.startRender(editor.projectId, clipId);
    return job_id;
  } catch (e) {
    editor.rendering = false;
    toast.error(`Render-Start: ${e.message}`);
    return null;
  }
}

export function handleJobEvent(msg) {
  // vom WebSocket aufgerufen
  if (msg.type === 'job_progress' && msg.kind === 'render'
      && msg.project_id === editor.projectId) {
    editor.renderProgress = msg.progress || 0;
    editor.renderPhase = msg.phase || 'rendering';
  }
  if (msg.type === 'job_event' && msg.job?.kind === 'render'
      && msg.job.project_id === editor.projectId) {
    if (msg.event === 'completed') {
      editor.rendering = false;
      editor.renderProgress = 1;
      editor.renderPhase = 'done';
      toast.success('Render fertig');
    } else if (msg.event === 'failed') {
      editor.rendering = false;
      editor.renderPhase = 'failed';
      toast.error(`Render: ${msg.job.error || 'fehlgeschlagen'}`);
    }
  }
}


// --- Transkription ---------------------------------------------------------

export async function loadTranscript(fileId) {
  if (!fileId) return;
  try {
    const t = await api.getTranscript(fileId);
    editor.transcript = t;
  } catch {
    // Still: wenn das Backend nichts hat, ist das kein Fehler
    editor.transcript = { has_transcript: false, segments: [], language: null, model: null };
  }
}

export async function startTranscribe(fileId, opts = {}) {
  if (!fileId) return;
  editor.transcribing = true;
  editor.transcribePct = 0;
  try {
    await api.startTranscription(fileId, opts);
    toast.info('Transkription gestartet');
  } catch (e) {
    editor.transcribing = false;
    // Spezialfall 409: Server meldet "nicht verfuegbar" -- wir geben die
    // Meldung weiter, aber crashen nicht.
    toast.error(`Transkription: ${e.message}`);
  }
}

export function setRightTab(tab) {
  if (tab !== 'exports' && tab !== 'transcript') return;
  editor.rightTab = tab;
  persistLocal('editor.rightTab', tab);
}

export function toggleSubtitles() {
  editor.subtitlesOn = !editor.subtitlesOn;
  persistLocal('editor.subtitlesOn', editor.subtitlesOn);
}

// Reagiere auf Job-Events vom WebSocket (vom Editor aus aufrufen)
export function handleTranscribeEvent(msg) {
  if (!editor.fileId) return;
  if (msg.type === 'job_progress' && msg.kind === 'transcribe'
      && msg.file_id === editor.fileId) {
    editor.transcribePct = msg.progress || 0;
    editor.transcribing = true;
  }
  if (msg.type === 'job_event' && msg.job?.kind === 'transcribe'
      && msg.job.file_id === editor.fileId) {
    if (msg.event === 'completed') {
      editor.transcribing = false;
      editor.transcribePct = 1;
      void loadTranscript(editor.fileId);
      toast.success('Transkription fertig');
    } else if (msg.event === 'failed') {
      editor.transcribing = false;
      toast.error(`Transkription: ${msg.job.error || 'fehlgeschlagen'}`);
    }
  }
  if (msg.type === 'file_event' && msg.event === 'transcript_ready'
      && msg.file_id === editor.fileId) {
    void loadTranscript(editor.fileId);
  }
}

/** Segment anhand der aktuellen Abspielzeit finden (fuer Subtitle-Overlay
 *  und Highlighting im Panel). Liefert null, wenn keines passt. */
export function activeSegmentAt(t, segments) {
  if (!Array.isArray(segments) || segments.length === 0) return null;
  for (const s of segments) {
    if (t >= (s.start ?? 0) && t < (s.end ?? 0)) return s;
  }
  return null;
}


/** Setzt den Timeline-Zoom (Pixel pro Sekunde). Wird von der Editor-
 *  Toolbar (Preset-Dropdown) und von der Timeline selbst (Mausrad)
 *  gerufen. */
export function setTimelineZoom(pxPerSec) {
  const v = Math.max(4, Math.min(400, Number(pxPerSec) || 40));
  editor.timelineZoom = v;
  persistLocal('editor.timelineZoom', v);
}
