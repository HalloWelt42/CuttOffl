"""Tests für render_service._output_forces_reencode -- die Kern-
Entscheidung "Copy oder Reencode".

Das war der grosse Bug, wegen dem YouTube 1080p auf 4K-HEVC-Quelle
"in Sekunden fertig" war und der Output unveraendert blieb.
"""

from __future__ import annotations

from app.models.edl import OutputProfile
from app.services.render_service import _output_forces_reencode


# Typische Quell-Metadaten (von den echten Demo-Dateien abgeleitet)
SRC_HEVC = {"video_codec": "hevc", "audio_codec": "aac"}
SRC_H264 = {"video_codec": "h264", "audio_codec": "aac"}


def _profile(**kwargs):
    # Minimale Helfer: nur Felder ueberschreiben, die der Test braucht.
    defaults = dict(
        codec="source",
        resolution="source",
        container="mp4",
        bitrate=None,
        crf=None,
        audio_codec="copy",
        audio_bitrate="160k",
        audio_normalize=False,
        audio_mono=False,
        audio_mute=False,
    )
    defaults.update(kwargs)
    return OutputProfile(**defaults)


class TestNoReencodeNeeded:
    def test_alles_quelle_und_audio_copy_ist_copy_mode(self):
        forced, reason = _output_forces_reencode(_profile(), SRC_HEVC)
        assert forced is False
        assert reason == ""

    def test_codec_source_mit_source_res_ist_copy(self):
        forced, _ = _output_forces_reencode(
            _profile(codec="source", resolution="source"), SRC_HEVC,
        )
        assert forced is False


class TestResolutionForcesReencode:
    def test_1080p_zwingt_reencode(self):
        forced, reason = _output_forces_reencode(
            _profile(resolution="1080p"), SRC_HEVC,
        )
        assert forced is True
        assert "1080p" in reason

    def test_720p_zwingt_reencode(self):
        forced, reason = _output_forces_reencode(
            _profile(resolution="720p"), SRC_HEVC,
        )
        assert forced is True


class TestBitrateForcesReencode:
    def test_ziel_bitrate_8M_zwingt_reencode(self):
        forced, reason = _output_forces_reencode(
            _profile(bitrate="8M"), SRC_HEVC,
        )
        assert forced is True
        assert "8M" in reason


class TestCrfForcesReencode:
    """CRF war lange NICHT als Trigger drin -- das Resultat war, dass
    die UI 'copy: 1' zeigte obwohl CRF 22 gesetzt war."""
    def test_crf_22_zwingt_reencode(self):
        forced, reason = _output_forces_reencode(
            _profile(crf=22), SRC_HEVC,
        )
        assert forced is True
        assert "22" in reason

    def test_crf_none_bleibt_copy(self):
        forced, _ = _output_forces_reencode(
            _profile(crf=None, bitrate=None, resolution="source"),
            SRC_HEVC,
        )
        assert forced is False


class TestAudioFiltersForceReencode:
    def test_audio_normalize_zwingt_reencode(self):
        forced, reason = _output_forces_reencode(
            _profile(audio_normalize=True), SRC_HEVC,
        )
        assert forced is True
        assert "Audio" in reason

    def test_audio_mono_zwingt_reencode(self):
        forced, _ = _output_forces_reencode(
            _profile(audio_mono=True), SRC_HEVC,
        )
        assert forced is True

    def test_audio_mute_zwingt_reencode(self):
        forced, _ = _output_forces_reencode(
            _profile(audio_mute=True), SRC_HEVC,
        )
        assert forced is True


class TestCodecMismatch:
    def test_ziel_h264_bei_hevc_quelle_zwingt_reencode(self):
        forced, reason = _output_forces_reencode(
            _profile(codec="h264"), SRC_HEVC,
        )
        assert forced is True
        assert "h264" in reason or "hevc" in reason

    def test_ziel_hevc_bei_h264_quelle_zwingt_reencode(self):
        forced, _ = _output_forces_reencode(
            _profile(codec="hevc"), SRC_H264,
        )
        assert forced is True

    def test_ziel_codec_source_matcht_jede_quelle(self):
        forced, _ = _output_forces_reencode(
            _profile(codec="source"), SRC_HEVC,
        )
        assert forced is False
        forced, _ = _output_forces_reencode(
            _profile(codec="source"), SRC_H264,
        )
        assert forced is False


class TestAudioCodecMismatch:
    def test_audio_aac_bei_aac_quelle_ok_solange_copy(self):
        forced, _ = _output_forces_reencode(
            _profile(audio_codec="copy"), SRC_H264,
        )
        assert forced is False

    def test_audio_mp3_bei_aac_quelle_zwingt_reencode(self):
        forced, reason = _output_forces_reencode(
            _profile(audio_codec="mp3"), SRC_H264,
        )
        assert forced is True
        assert "Audio" in reason


class TestOhneQuellMetadaten:
    """Ohne source_meta kann die Funktion keinen Codec-Vergleich
    machen. Sie darf dann nicht faelschlich Reencode erzwingen."""
    def test_nur_profil_ohne_quelle_ist_copy_wenn_alles_source(self):
        forced, _ = _output_forces_reencode(_profile(), None)
        assert forced is False

    def test_nur_profil_1080p_zwingt_reencode_auch_ohne_quelle(self):
        forced, _ = _output_forces_reencode(
            _profile(resolution="1080p"), None,
        )
        assert forced is True
