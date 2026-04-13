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
  listFiles: (folder = null, recursive = false) => {
    const params = new URLSearchParams();
    if (folder !== null) params.set('folder', folder);
    if (recursive) params.set('recursive', 'true');
    const qs = params.toString();
    return request(`/files${qs ? '?' + qs : ''}`);
  },
  getFile: (id) => request(`/files/${id}`),
  renameFile: (id, original_name) =>
    request(`/files/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ original_name }),
    }),
  setFileTags: (id, tags) =>
    request(`/files/${id}/tags`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tags }),
    }),
  moveFile: (id, folder_path) =>
    request(`/files/${id}/move`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path }),
    }),
  bulkMoveFiles: (file_ids, folder_path) =>
    request('/files/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_ids, folder_path }),
    }),
  bulkDeleteFiles: (file_ids) =>
    request('/files/bulk-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_ids }),
    }),
  deleteFile: (id) => request(`/files/${id}`, { method: 'DELETE' }),

  // Folders
  listFolders: () => request('/folders'),
  folderChildren: (folder = '') =>
    request(`/folders/children?folder=${encodeURIComponent(folder)}`),
  folderTree: () => request('/folders/tree'),
  renameFolder: (source, target) =>
    request('/folders/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source, target }),
    }),
  deleteFolder: (folder) =>
    request(`/folders?folder=${encodeURIComponent(folder)}`, { method: 'DELETE' }),
  fileDownloadUrl: (id) => `${BASE}/files/${id}/download`,

  // System
  systemOverview: () => request('/system/overview'),
  systemStorage:  () => request('/system/storage'),
  systemCodecs:   () => request('/system/codecs'),
  systemPaths:    () => request('/system/paths'),
  setSystemPaths: (body) =>
    request('/system/paths', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  // Upload
  upload: async (file, onProgress, folder = '', opts = {}) => {
    const force = opts.force === true;
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const qs = force ? '?force=true' : '';
      xhr.open('POST', `${BASE}/upload${qs}`);
      xhr.responseType = 'json';
      if (onProgress) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) onProgress(e.loaded / e.total);
        };
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) { resolve(xhr.response); return; }
        // Konflikt-Fehler mit Detail-Objekt durchreichen -- der Caller kann
        // nachfragen und ggf. mit force=true erneut versuchen.
        const detail = xhr.response?.detail;
        if (xhr.status === 409 && detail && typeof detail === 'object') {
          const err = new Error(detail.message || 'Datei existiert bereits');
          err.status = 409;
          err.conflict = detail;
          reject(err);
          return;
        }
        reject(new Error(`Upload ${xhr.status}: ${detail || xhr.statusText}`));
      };
      xhr.onerror = () => reject(new Error('Netzwerkfehler beim Upload'));
      const fd = new FormData();
      fd.append('file', file);
      if (folder) fd.append('folder', folder);
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
  clearFailedJobs: () => request('/jobs/failed', { method: 'DELETE' }),
  clearCompletedJobs: (keep_renders = true) =>
    request(`/jobs/completed?keep_renders=${keep_renders}`, { method: 'DELETE' }),

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
  startRender: (id, clipId = null) => {
    const qs = clipId ? `?clip_id=${encodeURIComponent(clipId)}` : '';
    return request(`/projects/${id}/render${qs}`, { method: 'POST' });
  },

  // Exports
  listExports: () => request('/exports'),
  exportDownloadUrl: (jobId) => `${BASE}/exports/${jobId}/download`,
  deleteExport: (jobId) => request(`/exports/${jobId}`, { method: 'DELETE' }),
  importExportToLibrary: (jobId, folder_path = '', rename = null) =>
    request(`/exports/${jobId}/import-to-library`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path, rename }),
    }),
};
