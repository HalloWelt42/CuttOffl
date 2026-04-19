// tourRecorder: schlanker Frontend-Helfer. Ohne URL-Param komplett
// no-op, mit Param ruft er nur start/stop im Backend auf.

import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('tourRecorder (default: kein ?tour_record=1)', () => {
  let fetchCalls;

  beforeEach(() => {
    window.history.replaceState({}, '', 'http://127.0.0.1:10037/');
    fetchCalls = [];
    globalThis.fetch = vi.fn((...args) => {
      fetchCalls.push(args);
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    vi.resetModules();
  });

  it('markTourStart macht keinen fetch', async () => {
    const mod = await import('../src/lib/tourRecorder.js');
    await mod.markTourStart();
    expect(fetchCalls).toHaveLength(0);
  });

  it('markTourEnd macht keinen fetch', async () => {
    const mod = await import('../src/lib/tourRecorder.js');
    await mod.markTourEnd();
    expect(fetchCalls).toHaveLength(0);
  });

  it('recorderActive() gibt false zurueck', async () => {
    const mod = await import('../src/lib/tourRecorder.js');
    expect(mod.recorderActive()).toBe(false);
  });
});

describe('tourRecorder (aktiv: ?tour_record=1)', () => {
  let fetchCalls;

  beforeEach(() => {
    window.history.replaceState({}, '', 'http://127.0.0.1:10037/?tour_record=1');
    fetchCalls = [];
    globalThis.fetch = vi.fn((...args) => {
      fetchCalls.push(args);
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    vi.resetModules();
  });

  it('recorderActive() gibt true zurueck', async () => {
    const mod = await import('../src/lib/tourRecorder.js');
    expect(mod.recorderActive()).toBe(true);
  });

  it('markTourStart POSTet an /api/_recorder/start', async () => {
    const mod = await import('../src/lib/tourRecorder.js');
    await mod.markTourStart();
    expect(fetchCalls).toHaveLength(1);
    const [url, opts] = fetchCalls[0];
    expect(url).toBe('/api/_recorder/start');
    expect(opts.method).toBe('POST');
  });

  it('markTourEnd POSTet an /api/_recorder/stop', async () => {
    const mod = await import('../src/lib/tourRecorder.js');
    await mod.markTourEnd();
    expect(fetchCalls).toHaveLength(1);
    const [url, opts] = fetchCalls[0];
    expect(url).toBe('/api/_recorder/stop');
    expect(opts.method).toBe('POST');
  });
});
