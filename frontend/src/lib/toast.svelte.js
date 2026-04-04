// Toast-Store -- einfache FIFO-Liste, auto-dismiss per Default.

let nextId = 1;
export const toasts = $state({ list: [] });

function push(kind, msg, ttl = 3500) {
  const id = nextId++;
  toasts.list = [...toasts.list, { id, kind, msg }];
  if (ttl > 0) setTimeout(() => dismiss(id), ttl);
  return id;
}

export function dismiss(id) {
  toasts.list = toasts.list.filter((t) => t.id !== id);
}

export const toast = {
  success: (msg, ttl) => push('success', msg, ttl),
  info:    (msg, ttl) => push('info', msg, ttl),
  warn:    (msg, ttl) => push('warning', msg, ttl),
  error:   (msg, ttl = 6000) => push('error', msg, ttl),
};
