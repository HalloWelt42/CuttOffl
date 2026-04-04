// CuttOffl WebSocket-Client -- verbindet /ws/jobs, haelt sich selbst am Leben.

const listeners = new Set();
let socket = null;
let reconnectTimer = null;
let currentUrl = null;

export const wsState = $state({ connected: false, lastError: null });

function computeUrl() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}/ws/jobs`;
}

function connect() {
  currentUrl = computeUrl();
  try {
    socket = new WebSocket(currentUrl);
  } catch (e) {
    wsState.lastError = e?.message ?? String(e);
    scheduleReconnect();
    return;
  }
  socket.onopen = () => {
    wsState.connected = true;
    wsState.lastError = null;
  };
  socket.onmessage = (evt) => {
    let msg = null;
    try { msg = JSON.parse(evt.data); } catch { return; }
    for (const fn of listeners) {
      try { fn(msg); } catch (e) { console.warn('WS-Listener Fehler', e); }
    }
  };
  socket.onerror = () => {
    wsState.lastError = 'WebSocket-Fehler';
  };
  socket.onclose = () => {
    wsState.connected = false;
    scheduleReconnect();
  };
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, 2000);
}

export function wsStart() {
  if (socket === null) connect();
}

export function wsOn(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
