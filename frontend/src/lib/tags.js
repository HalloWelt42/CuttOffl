// Tag-Helpers: parse/stringify + stabile Farbe per Hash.

// Kuratierte Palette -- gut unterscheidbar in Hell und Dunkel.
const PALETTE = [
  { bg: '#58a6ff', fg: '#0b1220' },  // GitHub-Blau (Akzent)
  { bg: '#d29922', fg: '#1b1403' },  // Gold
  { bg: '#2ea043', fg: '#07140b' },  // Gruen
  { bg: '#f85149', fg: '#1a0707' },  // Rot
  { bg: '#a371f7', fg: '#130a1c' },  // Violett
  { bg: '#f778ba', fg: '#1a0a13' },  // Pink
  { bg: '#34d399', fg: '#07140d' },  // Mint
  { bg: '#fb923c', fg: '#1a0d03' },  // Orange
  { bg: '#22d3ee', fg: '#031217' },  // Cyan
  { bg: '#c084fc', fg: '#140a1c' },  // Flieder
];

// Einfache DJB2-Hash (stabil, für gleiche Strings gleiche Farbe)
function hash(str) {
  let h = 5381;
  for (let i = 0; i < str.length; i++) {
    h = ((h << 5) + h + str.charCodeAt(i)) | 0;
  }
  return h >>> 0;
}

export function colorFor(tag) {
  if (!tag) return PALETTE[0];
  const key = String(tag).toLocaleLowerCase('de').trim();
  return PALETTE[hash(key) % PALETTE.length];
}

/** Parst "foo, bar, baz" oder "foo bar baz" -> ['foo','bar','baz'] */
export function parseTags(input) {
  if (!input) return [];
  return String(input)
    .split(/[,;]\s*|\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export function joinTags(tags) {
  return (tags || []).join(', ');
}
