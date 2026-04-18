// Export-Profile für schnellen Zugriff. Jedes Profil setzt einen
// vollständigen Satz OutputProfile-Felder. Der Nutzer kann danach
// immer noch feintunen -- die Presets sind nur "sinnvoller Startpunkt".
//
// Die Ziel-Bitraten orientieren sich an den offiziellen Empfehlungen
// von YouTube (SDR, 30 fps), Instagram und TikTok. Wo Empfehlungen
// fehlen (X, generisch), nehmen wir Werte, die in der Praxis gut
// aussehen und nicht unnötig Platz fressen.

// Die color-Angabe faerbt das Icon im Export-Dialog zum jeweiligen
// Markenwert (Brand-Recognition). Keine harte Brand-Imitation, nur
// ein deutlicher Wiedererkennungswert.
export const RENDER_PRESETS = [
  {
    id: 'youtube-1080',
    icon: 'fa-brands fa-youtube',
    color: '#FF0033',
    title: 'YouTube 1080p',
    note: '1920x1080, H.264, 8 Mbit/s -- YouTube-Standard',
    profile: {
      codec: 'h264', container: 'mp4', resolution: '1080p',
      bitrate: '8M', crf: null,
      audio_codec: 'aac', audio_bitrate: '192k',
      audio_normalize: false, audio_mono: false, audio_mute: false,
    },
  },
  {
    id: 'youtube-4k',
    icon: 'fa-brands fa-youtube',
    color: '#FF0033',
    title: 'YouTube 4K',
    note: '3840x2160, HEVC, 35 Mbit/s -- für hochaufgelöstes Material',
    profile: {
      codec: 'hevc', container: 'mp4', resolution: '2160p',
      bitrate: '35M', crf: null,
      audio_codec: 'aac', audio_bitrate: '192k',
      audio_normalize: false, audio_mono: false, audio_mute: false,
    },
  },
  {
    id: 'reel',
    icon: 'fa-brands fa-tiktok',
    color: '#25F4EE',   // TikTok-Cyan
    title: 'Reel / TikTok',
    note: '1080p, H.264, 6 Mbit/s, Lautheit normalisiert',
    profile: {
      codec: 'h264', container: 'mp4', resolution: '1080p',
      bitrate: '6M', crf: null,
      audio_codec: 'aac', audio_bitrate: '160k',
      audio_normalize: true, audio_mono: false, audio_mute: false,
    },
    hint: 'Schneide das Video vorher hochkant (9:16) im Editor zu -- '
        + 'CuttOffl dreht oder croppt noch nicht automatisch.',
  },
  {
    id: 'instagram-feed',
    icon: 'fa-brands fa-instagram',
    color: '#E4405F',   // Instagram-Pink
    title: 'Instagram Feed',
    note: '1080p, H.264, 5 Mbit/s -- auch für 1:1 geeignet',
    profile: {
      codec: 'h264', container: 'mp4', resolution: '1080p',
      bitrate: '5M', crf: null,
      audio_codec: 'aac', audio_bitrate: '160k',
      audio_normalize: true, audio_mono: false, audio_mute: false,
    },
  },
  {
    id: 'x-twitter',
    icon: 'fa-brands fa-x-twitter',
    color: '#E5E5E5',   // X: neutral hell, im Dark-Theme lesbar
    title: 'X / Twitter',
    note: '720p, H.264, 5 Mbit/s -- unter der 512-MB-Grenze',
    profile: {
      codec: 'h264', container: 'mp4', resolution: '720p',
      bitrate: '5M', crf: null,
      audio_codec: 'aac', audio_bitrate: '128k',
      audio_normalize: true, audio_mono: false, audio_mute: false,
    },
  },
  {
    id: 'podcast',
    icon: 'fa-solid fa-microphone',
    color: '#FF7043',   // warmes Orange für Sprache
    title: 'Podcast / Stimme',
    note: '480p, H.264, 800 kbit/s, Mono + Lautheit normalisiert',
    profile: {
      codec: 'h264', container: 'mp4', resolution: '480p',
      bitrate: '800k', crf: null,
      audio_codec: 'aac', audio_bitrate: '96k',
      audio_normalize: true, audio_mono: true, audio_mute: false,
    },
  },
  {
    id: 'web-compact',
    icon: 'fa-solid fa-leaf',
    color: '#10B981',   // Grün für "sparsam"
    title: 'Web kompakt',
    note: '720p, H.264 CRF 26 -- klein, lädt schnell',
    profile: {
      codec: 'h264', container: 'mp4', resolution: '720p',
      bitrate: null, crf: 26,
      audio_codec: 'aac', audio_bitrate: '128k',
      audio_normalize: false, audio_mono: false, audio_mute: false,
    },
  },
  {
    id: 'archive',
    icon: 'fa-solid fa-box-archive',
    color: '#D4A574',   // Bronze/Gold für "Archiv-Qualität"
    title: 'Archiv',
    note: 'Quell-Auflösung, HEVC CRF 18 -- sehr hohe Qualität',
    profile: {
      codec: 'hevc', container: 'mp4', resolution: 'source',
      bitrate: null, crf: 18,
      audio_codec: 'aac', audio_bitrate: '256k',
      audio_normalize: false, audio_mono: false, audio_mute: false,
    },
  },
  {
    id: 'passthrough',
    icon: 'fa-solid fa-scissors',
    color: '#94A3B8',
    title: 'Nur schneiden',
    note: 'Quelle unverändert durchreichen -- keyframe-genau, kein Reencode',
    // Die Werte dieses Profils stellen alle Felder auf "wie Quelle":
    // codec=source, kein Bitrate/CRF, Audio=copy, keine Filter. Der
    // Backend-Check analyze liefert daraufhin mode='copy'.
    profile: {
      codec: 'source', container: 'mp4', resolution: 'source',
      bitrate: null, crf: null,
      audio_codec: 'copy', audio_bitrate: '160k',
      audio_normalize: false, audio_mono: false, audio_mute: false,
    },
    hint: 'Schneidet nur an Keyframes. Kein Qualitätsverlust, '
        + 'sekundenschneller Export. Das Video bleibt 1:1 wie die Quelle.',
  },
];


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

// Render-Analyse (mode, reason, geschätzte Größe, kbps) lebt
// ausschließlich im Backend unter /api/render/analyze. Der
// ExportDialog ruft das per api.analyzeRender() ab. Dadurch gibt es
// nur EINEN Regelsatz -- der hier im Frontend gespiegelte Code von
// früher ist entfernt.

export function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '-';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}
