import pytest
from scripts.publish import resolve_channels, ChannelResolutionError


CHANNELS = [
    {"id": "yt1", "service": "youtube", "name": "Y", "isDisconnected": False,
     "isLocked": False, "isQueuePaused": False},
    {"id": "ig1", "service": "instagram", "name": "I", "isDisconnected": False,
     "isLocked": True, "isQueuePaused": False},
]


def test_resolve_maps_requested_to_connected():
    resolved, skipped = resolve_channels(["youtube"], CHANNELS,
                                         allow_missing=False)
    assert resolved[0]["id"] == "yt1"
    assert skipped == []


def test_missing_channel_hard_errors_by_default():
    with pytest.raises(ChannelResolutionError):
        resolve_channels(["youtube", "tiktok"], CHANNELS, allow_missing=False)


def test_missing_channel_skipped_when_allowed():
    resolved, skipped = resolve_channels(["youtube", "tiktok"], CHANNELS,
                                         allow_missing=True)
    assert [c["id"] for c in resolved] == ["yt1"]
    assert "tiktok" in skipped


def test_locked_channel_is_skipped_with_reason():
    resolved, skipped = resolve_channels(["instagram"], CHANNELS,
                                         allow_missing=True)
    assert resolved == []
    assert any("instagram" in s for s in skipped)


def test_build_metadata_youtube_includes_category():
    from types import SimpleNamespace
    from scripts.publish import build_metadata
    cap = SimpleNamespace(youtube_title="t", tiktok_title="tt", caption="c", hashtags=[])
    meta = build_metadata("youtube", cap)
    # Buffer rejects YouTube posts with no category — must always be present.
    assert meta["youtube"]["categoryId"] == "22"
    assert build_metadata("youtube", cap, youtube_category="28")["youtube"]["categoryId"] == "28"
    # other platforms unchanged
    assert build_metadata("instagram", cap)["instagram"]["type"] == "reel"
