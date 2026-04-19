// Tests fuer die reine Audio-Track-Logik (audioTrackLogic.js).
// Keine Svelte-Runes noetig -- pur JS und damit direkt mit vitest
// testbar.

import { describe, it, expect } from 'vitest';
import {
  addClip, splitAtPlayhead,
  setClipOffset, setClipRange, setClipGain, setClipFades,
  deleteClip,
} from '../src/lib/audioTrackLogic.js';

describe('audioTrackLogic', () => {
  describe('addClip', () => {
    it('legt einen Clip mit Default-Werten an', () => {
      const { list, clip } = addClip([], 'audio-1', 10, 0);
      expect(list).toHaveLength(1);
      expect(clip.file_id).toBe('audio-1');
      expect(clip.src_start).toBe(0);
      expect(clip.src_end).toBe(10);
      expect(clip.timeline_start).toBe(0);
      expect(clip.gain_db).toBe(0);
      expect(clip.fade_in_s).toBe(0);
      expect(clip.fade_out_s).toBe(0);
      expect(clip.id).toMatch(/^c[a-z0-9]+/);
    });

    it('sortiert neue Clips nach timeline_start', () => {
      let list = [];
      ({ list } = addClip(list, 'a', 5, 10));
      ({ list } = addClip(list, 'b', 5, 0));
      ({ list } = addClip(list, 'c', 5, 5));
      expect(list.map((c) => c.timeline_start)).toEqual([0, 5, 10]);
    });

    it('klemmt negative timeline_start auf 0', () => {
      const { clip } = addClip([], 'a', 5, -3);
      expect(clip.timeline_start).toBe(0);
    });

    it('hat eine Mindest-Dauer von 50 ms', () => {
      const { clip } = addClip([], 'a', 0, 0);
      expect(clip.src_end).toBeGreaterThan(0);
    });
  });

  describe('splitAtPlayhead', () => {
    it('teilt den passenden Clip in zwei', () => {
      let list = [];
      ({ list } = addClip(list, 'a', 10, 0));
      const result = splitAtPlayhead(list, 4);
      expect(result).not.toBeNull();
      expect(result.list).toHaveLength(2);
      const [left, right] = result.list;
      expect(left.src_start).toBe(0);
      expect(left.src_end).toBe(4);
      expect(right.src_start).toBe(4);
      expect(right.src_end).toBe(10);
      expect(right.timeline_start).toBe(4);
      expect(right.id).toBe(result.rightId);
    });

    it('nahtlose Schnittkante: left.src_end == right.src_start', () => {
      let list = [];
      ({ list } = addClip(list, 'a', 8, 0));
      const result = splitAtPlayhead(list, 3.25);
      const [left, right] = result.list;
      expect(left.src_end).toBe(right.src_start);
    });

    it('gibt null zurueck, wenn Playhead ausserhalb aller Clips', () => {
      const { list } = addClip([], 'a', 5, 0);
      expect(splitAtPlayhead(list, 20)).toBeNull();
      expect(splitAtPlayhead(list, -1)).toBeNull();
    });

    it('triggert nicht zu nah am Rand (Schutz gegen Null-Laengen)', () => {
      const { list } = addClip([], 'a', 5, 0);
      // exakt am Start oder Ende -> kein Split
      expect(splitAtPlayhead(list, 0)).toBeNull();
      expect(splitAtPlayhead(list, 5)).toBeNull();
    });

    it('verschobenen Clip sauber teilen', () => {
      let list = [];
      ({ list } = addClip(list, 'a', 10, 5));  // timeline 5..15, src 0..10
      const result = splitAtPlayhead(list, 8); // offset_in_clip = 3
      const [left, right] = result.list;
      expect(left.timeline_start).toBe(5);
      expect(left.src_end).toBe(3);
      expect(right.timeline_start).toBe(8);
      expect(right.src_start).toBe(3);
    });

    it('Fade-out wandert auf den rechten Teil', () => {
      let list = [];
      ({ list } = addClip(list, 'a', 10, 0));
      list = setClipFades(list, list[0].id, 0, 2);  // fade_out = 2s
      const result = splitAtPlayhead(list, 4);
      const [left, right] = result.list;
      expect(left.fade_out_s).toBe(0);
      expect(right.fade_out_s).toBe(2);
    });
  });

  describe('setClipOffset', () => {
    it('verschiebt', () => {
      let list = [];
      ({ list } = addClip(list, 'a', 5, 0));
      const id = list[0].id;
      list = setClipOffset(list, id, 12.5);
      expect(list[0].timeline_start).toBe(12.5);
    });
    it('klemmt negative Werte auf 0', () => {
      let list = [];
      ({ list } = addClip(list, 'a', 5, 5));
      list = setClipOffset(list, list[0].id, -3);
      expect(list[0].timeline_start).toBe(0);
    });
    it('sortiert nach Verschiebung neu', () => {
      let list = [];
      ({ list } = addClip(list, 'a', 5, 0));
      ({ list } = addClip(list, 'b', 5, 10));
      list = setClipOffset(list, list[0].id, 20);
      expect(list[0].file_id).toBe('b');
      expect(list[1].file_id).toBe('a');
    });
  });

  describe('setClipRange', () => {
    it('trimmt src_start und src_end', () => {
      let list = [];
      ({ list } = addClip(list, 'a', 10, 0));
      list = setClipRange(list, list[0].id, 2, 8);
      expect(list[0].src_start).toBe(2);
      expect(list[0].src_end).toBe(8);
    });
    it('tauscht vertauschte Werte korrekt', () => {
      let list = [];
      ({ list } = addClip(list, 'a', 10, 0));
      list = setClipRange(list, list[0].id, 5, 3);
      expect(list[0].src_start).toBe(3);
      expect(list[0].src_end).toBeGreaterThan(list[0].src_start);
    });
  });

  describe('setClipGain', () => {
    it('klemmt auf -30..+12', () => {
      let list = [];
      ({ list } = addClip(list, 'a', 5, 0));
      const id = list[0].id;
      list = setClipGain(list, id, -45);
      expect(list[0].gain_db).toBe(-30);
      list = setClipGain(list, id, 99);
      expect(list[0].gain_db).toBe(12);
      list = setClipGain(list, id, 6);
      expect(list[0].gain_db).toBe(6);
    });
  });

  describe('setClipFades', () => {
    it('klemmt 0..10 und laesst den anderen Wert unberuehrt', () => {
      let list = [];
      ({ list } = addClip(list, 'a', 10, 0));
      const id = list[0].id;
      list = setClipFades(list, id, 3, null);
      expect(list[0].fade_in_s).toBe(3);
      expect(list[0].fade_out_s).toBe(0);
      list = setClipFades(list, id, null, 2);
      expect(list[0].fade_in_s).toBe(3);   // unveraendert
      expect(list[0].fade_out_s).toBe(2);
      list = setClipFades(list, id, 25, -5);
      expect(list[0].fade_in_s).toBe(10);
      expect(list[0].fade_out_s).toBe(0);
    });
  });

  describe('deleteClip', () => {
    it('entfernt nur den passenden Clip', () => {
      let list = [];
      ({ list } = addClip(list, 'a', 5, 0));
      ({ list } = addClip(list, 'b', 5, 10));
      list = deleteClip(list, list[0].id);
      expect(list).toHaveLength(1);
      expect(list[0].file_id).toBe('b');
    });
  });
});
