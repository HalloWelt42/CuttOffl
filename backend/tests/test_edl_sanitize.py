"""Tests für den EDL-Sanitize-Validator in app/models/edl.py.

Der Validator muss degenerate Clips (src_end <= src_start, negative
src_start, NaN, fehlende Felder) herausfiltern, bevor die einzelnen
Clip-Validatoren greifen. Sonst scheitert die ganze EDL-Validierung
an einem einzigen kaputten Clip.
"""

from __future__ import annotations

import pytest

from app.models.edl import EDL


def _edl(timeline):
    return EDL.model_validate({
        "source_file_id": "abc",
        "timeline": timeline,
        "output": {},
    })


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
