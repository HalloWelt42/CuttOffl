"""Tests für render_analysis.analyze_output.

Das ist die zentrale Entscheidungs- und Schaetz-Funktion, von der der
Export-Dialog seine Anzeige bezieht. Jede Regression wuerde das UI
direkt luegen lassen.
"""

from __future__ import annotations

from app.models.edl import OutputProfile
from app.routers.render_analysis import analyze_output


SRC_HEVC_4K_GB = {
    "video_codec": "hevc",
    "audio_codec": "aac",
    "width": 3840,
    "height": 2160,
    "duration_s": 878.0,
    "size_bytes": 4_100_000_000,  # 4.1 GB
}

SRC_H264_1080_MB = {
    "video_codec": "h264",
    "audio_codec": "aac",
    "width": 1920,
    "height": 1080,
    "duration_s": 600.0,
    "size_bytes": 180_000_000,    # 180 MB
}


def _profile(**kw):
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
    defaults.update(kw)
    return OutputProfile(**defaults)


class TestModeDecision:
    def test_alles_source_ist_copy(self):
        r = analyze_output(_profile(), SRC_HEVC_4K_GB, 60.0)
        assert r.mode == "copy"
        assert r.reason == ""

    def test_1080p_target_ist_reencode(self):
        r = analyze_output(_profile(resolution="1080p"), SRC_HEVC_4K_GB, 60.0)
        assert r.mode == "reencode"
        assert "1080p" in r.reason

    def test_crf_target_ist_reencode(self):
        r = analyze_output(_profile(crf=22), SRC_HEVC_4K_GB, 60.0)
        assert r.mode == "reencode"
        assert "22" in r.reason


class TestEstimates:
    def test_copy_estimate_proportional_zu_quelle(self):
        # Halbe Quell-Dauer -> halbe Datei-Groesse
        r = analyze_output(_profile(), SRC_H264_1080_MB, 300.0)
        assert r.mode == "copy"
        assert abs(r.estimated_bytes - 90_000_000) < 1_000_000

    def test_copy_volle_dauer_matcht_quelle(self):
        r = analyze_output(_profile(), SRC_H264_1080_MB, 600.0)
        assert abs(r.estimated_bytes - 180_000_000) < 1_000_000

    def test_reencode_bitrate_target_proportional(self):
        # 8 Mbit/s * 60 s ~= 60 MB + ein bisschen Audio/Container
        r = analyze_output(
            _profile(codec="h264", resolution="1080p", bitrate="8M"),
            SRC_HEVC_4K_GB, 60.0,
        )
        assert r.mode == "reencode"
        # ~60 MB Video + 1.2 MB Audio, Container-Overhead ~2%
        assert 55_000_000 <= r.estimated_bytes <= 65_000_000


class TestResolvedCodec:
    def test_codec_source_wird_zu_hevc_wenn_quelle_hevc(self):
        r = analyze_output(_profile(codec="source"), SRC_HEVC_4K_GB, 60.0)
        assert r.resolved_codec == "hevc"

    def test_codec_source_wird_zu_h264_wenn_quelle_h264(self):
        r = analyze_output(_profile(codec="source"), SRC_H264_1080_MB, 60.0)
        assert r.resolved_codec == "h264"

    def test_codec_source_faellt_auf_h264_ohne_quelle(self):
        r = analyze_output(_profile(codec="source"), None, 60.0)
        assert r.resolved_codec == "h264"


class TestAudioMode:
    """Neu in Phase 4: audio_mode wird aus audio_track_count +
    mute_original abgeleitet und im Response ausgewiesen."""

    def test_kein_override_ist_original(self):
        r = analyze_output(_profile(), SRC_H264_1080_MB, 60.0)
        assert r.audio_mode == "original"
        assert r.audio_track_count == 0

    def test_override_ohne_mute_ist_mixed(self):
        r = analyze_output(
            _profile(), SRC_H264_1080_MB, 60.0,
            audio_track_count=2, mute_original=False,
        )
        assert r.audio_mode == "mixed"
        assert r.audio_track_count == 2

    def test_override_mit_mute_ist_replaced(self):
        r = analyze_output(
            _profile(), SRC_H264_1080_MB, 60.0,
            audio_track_count=1, mute_original=True,
        )
        assert r.audio_mode == "replaced"

    def test_mute_ohne_override_ist_muted(self):
        r = analyze_output(
            _profile(), SRC_H264_1080_MB, 60.0,
            audio_track_count=0, mute_original=True,
        )
        assert r.audio_mode == "muted"
