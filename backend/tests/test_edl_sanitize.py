"""Tests für den EDL-Sanitize-Validator in app/models/edl.py.

Der Validator muss degenerate Clips (src_end <= src_start, negative
src_start, NaN, fehlende Felder) herausfiltern, bevor die einzelnen
Clip-Validatoren greifen. Sonst scheitert die ganze EDL-Validierung
an einem einzigen kaputten Clip.
"""

from __future__ import annotations

import pytest

from app.models.edl import EDL


def _edl(timeline, *, audio_track=None, mute_original=False):
    body = {
        "source_file_id": "abc",
        "timeline": timeline,
        "output": {},
        "mute_original": mute_original,
    }
    if audio_track is not None:
        body["audio_track"] = audio_track
    return EDL.model_validate(body)


class TestEdlSanitize:
    def test_gueltige_clips_bleiben(self):
        edl = _edl([
            {"id": "a", "src_start": 0, "src_end": 10},
            {"id": "b", "src_start": 20, "src_end": 30},
        ])
        assert [c.id for c in edl.timeline] == ["a", "b"]

    def test_src_end_gleich_src_start_wird_gefiltert(self):
        edl = _edl([
            {"id": "a", "src_start": 0, "src_end": 10},
            {"id": "bad", "src_start": 5, "src_end": 5},
            {"id": "b", "src_start": 20, "src_end": 30},
        ])
        assert [c.id for c in edl.timeline] == ["a", "b"]

    def test_src_end_kleiner_src_start_wird_gefiltert(self):
        edl = _edl([
            {"id": "bad", "src_start": 10, "src_end": 5},
            {"id": "ok", "src_start": 0, "src_end": 3},
        ])
        assert [c.id for c in edl.timeline] == ["ok"]

    def test_negative_src_start_wird_gefiltert(self):
        edl = _edl([
            {"id": "bad", "src_start": -1, "src_end": 3},
            {"id": "ok", "src_start": 0, "src_end": 3},
        ])
        assert [c.id for c in edl.timeline] == ["ok"]

    def test_fehlende_werte_werden_gefiltert(self):
        edl = _edl([
            {"id": "no_start", "src_end": 3},
            {"id": "no_end", "src_start": 0},
            {"id": "ok", "src_start": 0, "src_end": 3},
        ])
        assert [c.id for c in edl.timeline] == ["ok"]

    def test_nicht_numerische_werte_werden_gefiltert(self):
        edl = _edl([
            {"id": "bad", "src_start": "foo", "src_end": "bar"},
            {"id": "ok", "src_start": 0, "src_end": 3},
        ])
        assert [c.id for c in edl.timeline] == ["ok"]

    def test_werte_werden_auf_3_nachkommastellen_gerundet(self):
        edl = _edl([
            {"id": "a", "src_start": 0.123456789, "src_end": 9.987654321},
        ])
        assert edl.timeline[0].src_start == 0.123
        assert edl.timeline[0].src_end == 9.988

    def test_leere_timeline_ist_ok(self):
        edl = _edl([])
        assert edl.timeline == []

    def test_mix_wie_im_frontend_produziert(self):
        # genau der Test-Fall, mit dem ich den Sanitize initial
        # verifiziert habe: 4 Clips, 2 degenerate, 2 gueltig
        edl = _edl([
            {"id": "good1", "src_start": 0, "src_end": 5},
            {"id": "bad1", "src_start": 10, "src_end": 10},
            {"id": "bad2", "src_start": -2, "src_end": 3},
            {"id": "good2", "src_start": 20, "src_end": 25},
        ])
        assert [c.id for c in edl.timeline] == ["good1", "good2"]


class TestAudioTrackSanitize:
    """Analog zum Video-Sanitize, aber fuer EDL.audio_track (AudioClip)."""

    def _ac(self, **kw):
        return {"id": kw.get("id", "a"),
                "file_id": kw.get("file_id", "f"),
                "src_start": kw.get("src_start", 0.0),
                "src_end": kw.get("src_end", 5.0),
                "timeline_start": kw.get("timeline_start", 0.0)}

    def test_gueltige_audio_clips_bleiben(self):
        edl = _edl([], audio_track=[
            self._ac(id="a1", timeline_start=0),
            self._ac(id="a2", timeline_start=30),
        ])
        assert [c.id for c in edl.audio_track] == ["a1", "a2"]

    def test_audio_clips_duerfen_ueberlappen(self):
        # Das ist erwuenscht -- ueberlappende Clips werden im Render
        # per amix gemischt, der Sanitize darf sie nicht ablehnen.
        edl = _edl([], audio_track=[
            self._ac(id="a1", timeline_start=0, src_end=10),
            self._ac(id="a2", timeline_start=5, src_end=10),
        ])
        assert len(edl.audio_track) == 2

    def test_negativer_timeline_start_wird_gefiltert(self):
        edl = _edl([], audio_track=[
            self._ac(id="bad", timeline_start=-1),
            self._ac(id="ok", timeline_start=5),
        ])
        assert [c.id for c in edl.audio_track] == ["ok"]

    def test_degenerate_audio_clip_wird_gefiltert(self):
        edl = _edl([], audio_track=[
            self._ac(id="bad", src_start=5, src_end=5),
            self._ac(id="ok"),
        ])
        assert [c.id for c in edl.audio_track] == ["ok"]

    def test_zeiten_werden_auf_3_nachkommastellen_gerundet(self):
        edl = _edl([], audio_track=[
            self._ac(id="a", src_start=0.1234567, src_end=5.9876543,
                     timeline_start=12.3456789),
        ])
        c = edl.audio_track[0]
        assert c.src_start == 0.123
        assert c.src_end == 5.988
        assert c.timeline_start == 12.346

    def test_leere_audio_track_ist_ok(self):
        edl = _edl([])
        assert edl.audio_track == []
        assert edl.mute_original is False

    def test_mute_original_flag_uebernommen(self):
        edl = _edl([], mute_original=True)
        assert edl.mute_original is True
