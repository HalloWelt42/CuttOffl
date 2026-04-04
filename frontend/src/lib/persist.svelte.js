// Kleine localStorage-Helfer -- fuer Sidebar-Breite, Theme, Font-Scale etc.

export function persisted(key, initial) {
  try {
    const raw = localStorage.getItem(key);
    if (raw !== null) return JSON.parse(raw);
  } catch {}
  return initial;
}

export function persist(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {}
}
