import json
from dataclasses import dataclass
from datetime import date

import pytest

from scripts import youtube_publish as yp
from scripts.captioner import Caption


@dataclass
class FakeClip:
    index: int
    video_path: object
    metadata: dict


def _clip(index, score, start_time=0.0):
    return FakeClip(index, f"/tmp/clip_{index}.mp4",
                    {"score": score, "start_time": start_time})


def test_select_and_order_by_score_desc_then_index():
    clips = [_clip(1, 5.0), _clip(2, 6.0), _clip(3, 6.0), _clip(4, 5.0)]
    ordered = yp.select_and_order(clips, "score", max_clips=3)
    assert [c.index for c in ordered] == [2, 3, 1]  # 6.0s first (index tie-break), then 5.0


def test_select_and_order_chrono_by_start_time():
    clips = [_clip(1, 5.0, start_time=900), _clip(2, 6.0, start_time=10),
             _clip(3, 6.0, start_time=500)]
    ordered = yp.select_and_order(clips, "chrono", max_clips=3)
    assert [c.index for c in ordered] == [2, 3, 1]


def test_select_and_order_caps_at_max():
    clips = [_clip(i, 6.0) for i in range(1, 8)]
    assert len(yp.select_and_order(clips, "score", max_clips=6)) == 6


def test_select_and_order_excludes_indices():
    # 4 sixes (1-4) and 3 fives (5,6,7); dropping clip 5 pulls clip 7 into the top 6.
    clips = [_clip(1, 6.0), _clip(2, 6.0), _clip(3, 6.0), _clip(4, 6.0),
             _clip(5, 5.0), _clip(6, 5.0), _clip(7, 5.0)]
    ordered = yp.select_and_order(clips, "score", max_clips=6, exclude={5})
    indices = [c.index for c in ordered]
    assert 5 not in indices
    assert 7 in indices
    assert indices == [1, 2, 3, 4, 6, 7]


def test_shorts_description_appends_marker_when_missing():
    cap = Caption(caption="Punchy", youtube_title="t", tiktok_title="t",
                  hashtags=["#ia"], source_url="https://youtu.be/x")
    out = yp.shorts_description(cap)
    assert out.lower().count("#shorts") == 1
    assert "https://youtu.be/x" in out


def test_shorts_description_keeps_existing_marker():
    cap = Caption(caption="Punchy #Shorts", youtube_title="t", tiktok_title="t",
                  hashtags=[], source_url=None)
    assert yp.shorts_description(cap).lower().count("#shorts") == 1


def test_build_tags_strips_hash_and_adds_shorts():
    cap = Caption(caption="c", youtube_title="t", tiktok_title="t",
                  hashtags=["#ia", "#viral"], source_url=None)
    tags = yp.build_tags(cap)
    assert tags == ["ia", "viral", "Shorts"]


class FakeLedger:
    def __init__(self):
        self.posts = {}
        self.records = []
    def has_post(self, clip_key, channel):
        return (clip_key, channel) in self.posts
    def record_post(self, clip_key, channel, post_id, mode, due_at, state):
        self.posts[(clip_key, channel)] = post_id
        self.records.append({"clip_key": clip_key, "channel_id": channel,
                             "post_id": post_id, "due_at": due_at})
    def all_posts(self):
        return list(self.records)
    def save(self):
        pass


@dataclass
class FakeCfg:
    caption_provider: str = "openai"


def _make_clip_dir(tmp_path, indices_scores):
    for idx, score in indices_scores:
        (tmp_path / f"viral_clip_{idx}_score_{score}_subtitled.mp4").write_bytes(b"x")
        (tmp_path / f"viral_clip_{idx}_score_{score}.json").write_text(json.dumps({
            "score": score, "start_time": idx * 10.0,
            "reason": "moment", "original_video": "ep_4OlWf_Vj6U4.mp4",
        }))
    return tmp_path


def test_run_schedules_top_clips_and_records_ledger(tmp_path, monkeypatch):
    clips_dir = _make_clip_dir(tmp_path, [(1, "6.0"), (2, "5.0"), (3, "6.0")])

    monkeypatch.setattr(yp, "build_caption", lambda meta, provider, cfg: Caption(
        caption="hook", youtube_title="Hook!", tiktok_title="Hook!",
        hashtags=["#ia"], source_url="https://youtu.be/4OlWf_Vj6U4"))
    uploaded = []
    def fake_upload(service, path, title, desc, tags, slot, category_id):
        uploaded.append((title, slot))
        return f"vid{len(uploaded)}"
    monkeypatch.setattr(yp.yt, "upload_video", fake_upload)

    ledger = FakeLedger()
    summary = yp.run(clips_dir, ledger, FakeCfg(), max_clips=2, per_day=1,
                     start_date=date(2026, 6, 27), hour=18, end_hour=22,
                     tz="Europe/Paris", order="score", category="22",
                     dry_run=False, service=object())

    assert summary["scheduled"] == 2          # capped at max_clips
    assert len(uploaded) == 2
    # Two distinct daily slots, a day apart
    assert (uploaded[1][1] - uploaded[0][1]).days == 1
    assert ("clip_1", "youtube") in ledger.posts


def test_run_skips_already_scheduled(tmp_path, monkeypatch):
    clips_dir = _make_clip_dir(tmp_path, [(1, "6.0")])
    monkeypatch.setattr(yp, "build_caption", lambda meta, provider, cfg: Caption(
        caption="hook", youtube_title="Hook!", tiktok_title="Hook!", hashtags=[]))
    monkeypatch.setattr(yp.yt, "upload_video",
                        lambda *a, **k: pytest.fail("should not upload"))

    ledger = FakeLedger()
    ledger.record_post("clip_1", "youtube", "existing", "scheduled", "x", "scheduled")
    summary = yp.run(clips_dir, ledger, FakeCfg(), max_clips=6, per_day=1,
                     start_date=date(2026, 6, 27), hour=18, end_hour=22,
                     tz="Europe/Paris", order="score", category="22",
                     dry_run=False, service=object())
    assert summary["scheduled"] == 0
    assert summary["skipped"]


def test_run_stacks_after_existing_scheduled_slots(tmp_path, monkeypatch):
    clips_dir = _make_clip_dir(tmp_path, [(1, "6.0")])
    monkeypatch.setattr(yp, "build_caption", lambda meta, provider, cfg: Caption(
        caption="hook", youtube_title="Hook!", tiktok_title="Hook!", hashtags=[]))
    captured = []
    monkeypatch.setattr(yp.yt, "upload_video",
                        lambda service, path, title, desc, tags, slot, category_id:
                        (captured.append(slot) or "vidX"))

    # A prior run already took day 1 (27 Jun 18:00 Paris == 16:00Z).
    ledger = FakeLedger()
    ledger.record_post("clip_99", "youtube", "old", "scheduled",
                       "2026-06-27T16:00:00Z", "scheduled")

    yp.run(clips_dir, ledger, FakeCfg(), max_clips=6, per_day=1,
           start_date=date(2026, 6, 27), hour=18, end_hour=22,
           tz="Europe/Paris", order="score", category="22",
           dry_run=False, service=object())

    # New clip must land on day 2, not double-book the occupied day 1.
    assert yp.yt.to_rfc3339(captured[0]) == "2026-06-28T16:00:00Z"
