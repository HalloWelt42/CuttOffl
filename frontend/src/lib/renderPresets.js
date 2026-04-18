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
];


// Heuristik für die Dateigrößen-Abschätzung im CRF-Modus. Die
// Zahl ist die erwartete Video-Bitrate in Mbit/s bei 1080p H.264 im
// Mittel über Alltagsmaterial (sprechender Kopf, bisschen Bewegung).
// Kein Referenzwert für Action-Filme -- bei 4K-Animation wirds
// deutlich mehr. Für die UI reicht das allemal als Hausnummer.
export function estimateVideoBitrateKbps(profile) {
  if (profile.bitrate) {
    return parseBitrateKbps(profile.bitrate);
  }
  const crf = Number(profile.crf ?? 23);
  // Basis: 1080p H.264. Formel so gewählt, dass CRF 14 -> ~50 Mbps,
  // CRF 23 -> ~6 Mbps, CRF 32 -> ~0.8 Mbps ergibt.
  let kbps = 50_000 / Math.pow(2, (crf - 14) / 3);
  // Auflösung skaliert quadratisch mit der Pixel-Anzahl.
  const resFactor = resolutionFactor(profile.resolution);
  kbps *= resFactor;
  // HEVC ist bei gleicher Qualität etwa 40 % effizienter.
  if (profile.codec === 'hevc') kbps *= 0.6;
  return kbps;
}

function resolutionFactor(resolution) {
  switch ((resolution || 'source').toLowerCase()) {
    case '480p':  return 0.25;
    case '720p':  return 0.50;
    case '1080p': return 1.00;
    case '1440p': return 1.75;
    case '2160p': return 4.00;
    case 'source': return 1.00;
    default: {
      const m = /^(\d+)x(\d+)$/.exec(resolution || '');
      if (m) {
        const px = Number(m[1]) * Number(m[2]);
        return px / (1920 * 1080);
      }
      return 1.0;
    }
  }
}

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

// Schätzt die resultierende Dateigröße in Bytes. Sehr bewusst als
// "circa"-Wert -- die echte Größe hängt vom Material ab.
export function estimateFilesizeBytes(profile, totalSeconds) {
  if (!totalSeconds || totalSeconds <= 0) return 0;
  const videoKbps = estimateVideoBitrateKbps(profile);
  const audioKbps = profile.audio_mute ? 0 : parseBitrateKbps(profile.audio_bitrate);
  const totalKbits = (videoKbps + audioKbps) * totalSeconds;
  // Container-Overhead: ~2 % für MP4, bisschen mehr für MKV/MOV.
  const overhead = profile.container === 'mp4' ? 1.02 : 1.04;
  return (totalKbits * 1000 / 8) * overhead;
}

export function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '-';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}
