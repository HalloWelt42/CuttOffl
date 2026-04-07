// CuttOffl REST-Client (Backend auf /api via Vite-Proxy bzw. gleiche Origin).

const BASE = '/api';

async function request(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Accept: 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) {
    let detail = '';
    try {
      const j = await res.json();
      detail = j?.detail ? `: ${j.detail}` : '';
    } catch {}
    throw new Error(`${res.status} ${res.statusText}${detail}`);
  }
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return res.json();
  return res;
}

export const api = {
  ping: () => request('/ping'),

  // Files
  listFiles: () => request('/files'),
  getFile: (id) => request(`/files/${id}`),
  renameFile: (id, original_name) =>
    request(`/files/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ original_name }),
    }),
  deleteFile: (id) => request(`/files/${id}`, { method: 'DELETE' }),
  fileDownloadUrl: (id) => `${BASE}/files/${id}/download`,

  // System
  systemOverview: () => request('/system/overview'),
  systemStorage:  () => request('/system/storage'),
  systemCodecs:   () => request('/system/codecs'),

  // Upload
  upload: async (file, onProgress) => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${BASE}/upload`);
      xhr.responseType = 'json';
      if (onProgress) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) onProgress(e.loaded / e.total);
        };
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response);
        else reject(new Error(`Upload ${xhr.status}: ${xhr.response?.detail || xhr.statusText}`));
      };
      xhr.onerror = () => reject(new Error('Netzwerkfehler beim Upload'));
      const fd = new FormData();
      fd.append('file', file);
      xhr.send(fd);
    });
  },

  // Proxy
  keyframes: (id) => request(`/proxy/${id}/keyframes`),
  proxyUrl: (id) => `${BASE}/proxy/${id}`,
  regenerateProxy: (id) => request(`/proxy/${id}/generate`, { method: 'POST' }),

  // Thumbnails
  thumbUrl: (id) => `${BASE}/thumbnail/${id}`,

  // Timeline-Visualisierung
  spriteUrl:  (id) => `${BASE}/sprite/${id}`,
  spriteMeta: (id) => request(`/sprite/${id}/meta`),
  waveform:   (id) => request(`/waveform/${id}`),

  // Jobs
  listJobs: (limit = 50) => request(`/jobs?limit=${limit}`),
  activeJob: () => request('/jobs/active'),
  getJob: (id) => request(`/jobs/${id}`),

  // Probe
  probe: (id) => request(`/probe/${id}`),

  // Snap (Keyframe-Magnet)
  snap: (id, t, mode = 'nearest') =>
    request(`/proxy/${id}/snap?t=${encodeURIComponent(t)}&mode=${mode}`),

  // Projekte / EDL
  listProjects: () => request('/projects'),
  getProject: (id) => request(`/projects/${id}`),
  createProject: (body) =>
    request('/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  updateProject: (id, body) =>
    request(`/projects/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  deleteProject: (id) => request(`/projects/${id}`, { method: 'DELETE' }),
  startRender: (id) =>
    request(`/projects/${id}/render`, { method: 'POST' }),

  // Exports
  listExports: () => request('/exports'),
  exportDownloadUrl: (jobId) => `${BASE}/exports/${jobId}/download`,
  deleteExport: (jobId) => request(`/exports/${jobId}`, { method: 'DELETE' }),
};
