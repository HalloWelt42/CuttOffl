// renderPresets-Helper: parseBitrateKbps, formatBytes. Edge Cases
// (leer, NaN, grosse Zahlen, Ziffer+M ohne K, nackte Zahl).

import { describe, it, expect } from 'vitest';
import { parseBitrateKbps, formatBytes } from '../src/lib/renderPresets.js';

describe('parseBitrateKbps', () => {
  it('leere Eingaben -> 0', () => {
    expect(parseBitrateKbps('')).toBe(0);
    expect(parseBitrateKbps(null)).toBe(0);
    expect(parseBitrateKbps(undefined)).toBe(0);
  });

  it('k-Suffix (kbit/s)', () => {
    expect(parseBitrateKbps('500k')).toBe(500);
    expect(parseBitrateKbps('800K')).toBe(800);
    expect(parseBitrateKbps('128k')).toBe(128);
  });

  it('m-Suffix (Mbit/s -> kbit/s)', () => {
    expect(parseBitrateKbps('8M')).toBe(8000);
    expect(parseBitrateKbps('1m')).toBe(1000);
    expect(parseBitrateKbps('35M')).toBe(35000);
  });

  it('nackte Zahl = bit/s (ffmpeg-Konvention)', () => {
    expect(parseBitrateKbps('8000000')).toBe(8000);
    expect(parseBitrateKbps('1500000')).toBe(1500);
  });

  it('ungueltige Eingaben -> 0', () => {
    expect(parseBitrateKbps('abc')).toBe(0);
    expect(parseBitrateKbps('8 Mbit')).toBe(0);
  });
});

describe('formatBytes', () => {
  it('0 / negative -> "-"', () => {
    expect(formatBytes(0)).toBe('-');
    expect(formatBytes(-1)).toBe('-');
    expect(formatBytes(null)).toBe('-');
  });

  it('Bytes unter 1 KB', () => {
    expect(formatBytes(500)).toBe('500 B');
  });

  it('KB / MB / GB', () => {
    expect(formatBytes(2048)).toBe('2.0 KB');
    expect(formatBytes(5_000_000)).toBe('4.8 MB');
    expect(formatBytes(2_000_000_000)).toBe('1.9 GB');
  });

  it('Grenzwerte: ab 10 MB / GB ohne Nachkomma', () => {
    expect(formatBytes(10 * 1024 * 1024)).toBe('10 MB');
    expect(formatBytes(15 * 1024 * 1024 * 1024)).toBe('15 GB');
  });
});
