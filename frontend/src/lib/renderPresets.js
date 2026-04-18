// Render-Helper (nur Formatierung). Presets und Render-Analyse-Logik
// leben ausschliesslich im Backend (/api/render/presets und
// /api/render/analyze). Frontend laedt und rendert -- keine eigenen
// Regeln mehr.

export function parseBitrateKbps(s) {
  if (!s) return 0;
  const str = String(s).trim().toLowerCase();
  const m = /^(\d+(?:\.\d+)?)([km]?)$/.exec(str);
  if (!m) return 0;
  const n = Number(m[1]);
  const unit = m[2];
  if (unit === 'm') return n * 1000;
  if (unit === 'k') return n;
  // Nackte Zahl: bit/s (ffmpeg-Konvention)
  return n / 1000;
}

export function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '-';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}
