import json
import pytest
from scripts.clips import discover_clips, ClipMappingError


def _write(p, data):
    p.write_text(json.dumps(data))


def test_discover_maps_subtitled_to_metadata(tmp_path):
    (tmp_path / "clip_1_final_subtitled.mp4").write_bytes(b"x")
    _write(tmp_path / "clip_1_score_7.0.json",
           {"score": 7.0, "reason": "great moment", "duration": 30.0})
    clips = discover_clips(tmp_path)
    assert len(clips) == 1
    assert clips[0].video_path.name == "clip_1_final_subtitled.mp4"
    assert clips[0].metadata["reason"] == "great moment"
    assert clips[0].index == 1


def test_discover_prefers_subtitled_over_raw(tmp_path):
    (tmp_path / "clip_2_final_subtitled.mp4").write_bytes(b"x")
    (tmp_path / "clip_2_score_8.0.mp4").write_bytes(b"x")
    _write(tmp_path / "clip_2_score_8.0.json", {"score": 8.0, "reason": "r"})
    clips = discover_clips(tmp_path)
    paths = [c.video_path.name for c in clips]
    assert paths == ["clip_2_final_subtitled.mp4"]


def test_discover_newest_json_when_multiple(tmp_path):
    import os, time
    (tmp_path / "clip_3_final_subtitled.mp4").write_bytes(b"x")
    old = tmp_path / "clip_3_score_5.0.json"
    new = tmp_path / "clip_3_score_9.0.json"
    _write(old, {"score": 5.0, "reason": "old"})
    _write(new, {"score": 9.0, "reason": "new"})
    os.utime(old, (time.time() - 100, time.time() - 100))
    clips = discover_clips(tmp_path)
    assert clips[0].metadata["reason"] == "new"


def test_missing_metadata_raises(tmp_path):
    (tmp_path / "clip_4_final_subtitled.mp4").write_bytes(b"x")
    with pytest.raises(ClipMappingError):
        discover_clips(tmp_path)


def test_discover_handles_viral_clip_scheme(tmp_path):
    # Real pipeline output for some runs uses the `viral_clip_<N>_score_<s>` scheme,
    # with a `_seam_` layout variant alongside the standard `_score_` subtitled clip.
    (tmp_path / "viral_clip_1_score_6.0_subtitled.mp4").write_bytes(b"x")
    (tmp_path / "viral_clip_1_seam_subtitled.mp4").write_bytes(b"x")
    (tmp_path / "viral_clip_1_score_6.0.mp4").write_bytes(b"x")
    _write(tmp_path / "viral_clip_1_score_6.0.json",
           {"score": 6.0, "reason": "ai costs zero"})
    clips = discover_clips(tmp_path)
    assert len(clips) == 1
    assert clips[0].index == 1
    # prefers the _score_ subtitled render over the _seam_ variant
    assert clips[0].video_path.name == "viral_clip_1_score_6.0_subtitled.mp4"
    assert clips[0].metadata["reason"] == "ai costs zero"
