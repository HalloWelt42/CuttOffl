"""Smoke-Tests für die Render-Presets -- jeder Preset muss ein
valides OutputProfile ergeben, die Bitraten muessen dem ffmpeg-
Format entsprechen, und jede eindeutige ID kommt nur einmal vor.
"""

from __future__ import annotations

import re

from app.services.render_presets import RENDER_PRESETS, get_preset


class TestPresets:
    def test_mindestens_ein_preset_vorhanden(self):
        assert len(RENDER_PRESETS) >= 1

    def test_ids_sind_eindeutig(self):
        ids = [p.id for p in RENDER_PRESETS]
        assert len(ids) == len(set(ids)), f"doppelte IDs: {ids}"

    def test_jedes_profile_ist_valides_OutputProfile(self):
        # Schon durch Pydantic beim Import geprueft -- Test dient als
        # expliziter Smoke-Test fuer den Fall, dass Presets dynamisch
        # modifiziert werden.
        for p in RENDER_PRESETS:
            assert p.profile is not None
            assert p.profile.container in ("mp4", "mkv", "mov")

    def test_bitrate_format(self):
        rx = re.compile(r"^\d{1,9}[KkMm]?$")
        for p in RENDER_PRESETS:
            b = p.profile.bitrate
            if b is None:
                continue
            assert rx.fullmatch(b), f"{p.id}: bitrate {b!r} entspricht nicht dem Muster"

    def test_get_preset_findet_passthrough(self):
        assert get_preset("passthrough") is not None
        assert get_preset("nonexistent") is None
