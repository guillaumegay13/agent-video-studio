from datetime import date
from types import SimpleNamespace
from pathlib import Path
import pytest
from scripts.publish import schedule_run


class FakeBuffer:
    def __init__(self):
        self.created = []
    def list_scheduled_due_ats(self, org_id, channel_id):
        return []
    def create_post(self, channel_id, text, video_url, thumbnail_url, due_at,
                    scheduling_type, metadata):
        self.created.append((channel_id, due_at, scheduling_type))
        return f"post-{len(self.created)}"


def test_schedule_run_creates_one_post_per_channel(tmp_path, monkeypatch):
    (tmp_path / "clip_1_final_subtitled.mp4").write_bytes(b"x")
    (tmp_path / "clip_1_score_7.0.json").write_text('{"reason":"r","score":7.0}')

    monkeypatch.setattr("scripts.publish.media_host.upload_clip",
        lambda path, cfg, prefix="publish": {
            "public_id": "publish/clip_1_final_subtitled",
            "video_url": "https://x/clip.mp4",
            "thumbnail_url": "https://x/clip.jpg"})
    monkeypatch.setattr("scripts.publish.build_caption",
        lambda meta, provider, cfg: SimpleNamespace(
            caption="c", youtube_title="t", tiktok_title="tt", hashtags=["#a"], source_url=None))

    buf = FakeBuffer()
    channels = [{"id": "yt1", "service": "youtube", "isDisconnected": False,
                 "isLocked": False, "isQueuePaused": False}]
    summary = schedule_run(
        clips_dir=tmp_path, resolved_channels=channels, buffer=buf, org_id="org1",
        cfg=SimpleNamespace(caption_provider="openai"),
        ledger=__import__("scripts.ledger", fromlist=["Ledger"]).Ledger(tmp_path/"l.json"),
        per_day=1, start_date=date(2026, 7, 1), hour=18, end_hour=22, tz="UTC",
        max_clips=5, dry_run=False)
    assert len(buf.created) == 1
    assert summary["posted"] == 1


def test_dry_run_creates_no_posts(tmp_path, monkeypatch):
    (tmp_path / "clip_1_final_subtitled.mp4").write_bytes(b"x")
    (tmp_path / "clip_1_score_7.0.json").write_text('{"reason":"r","score":7.0}')
    monkeypatch.setattr("scripts.publish.media_host.upload_clip",
        lambda path, cfg, prefix="publish": {"public_id": "p", "video_url": "u",
                                             "thumbnail_url": "t"})
    monkeypatch.setattr("scripts.publish.build_caption",
        lambda meta, provider, cfg: SimpleNamespace(
            caption="c", youtube_title="t", tiktok_title="tt", hashtags=[], source_url=None))
    buf = FakeBuffer()
    channels = [{"id": "yt1", "service": "youtube", "isDisconnected": False,
                 "isLocked": False, "isQueuePaused": False}]
    summary = schedule_run(
        clips_dir=tmp_path, resolved_channels=channels, buffer=buf, org_id="org1",
        cfg=SimpleNamespace(caption_provider="openai"),
        ledger=__import__("scripts.ledger", fromlist=["Ledger"]).Ledger(tmp_path/"l.json"),
        per_day=1, start_date=date(2026, 7, 1), hour=18, end_hour=22, tz="UTC",
        max_clips=5, dry_run=True)
    assert buf.created == []
    assert summary["planned"] == 1


def test_existing_buffer_slot_is_skipped(tmp_path, monkeypatch):
    (tmp_path / "clip_1_final_subtitled.mp4").write_bytes(b"x")
    (tmp_path / "clip_1_score_7.0.json").write_text('{"reason":"r","score":7.0}')
    monkeypatch.setattr("scripts.publish.media_host.upload_clip",
        lambda path, cfg, prefix="publish": {"public_id": "p",
            "video_url": "https://x/clip.mp4", "thumbnail_url": None})
    monkeypatch.setattr("scripts.publish.build_caption",
        lambda meta, provider, cfg: SimpleNamespace(
            caption="c", youtube_title="t", tiktok_title="tt", hashtags=[], source_url=None))

    class BusyBuffer(FakeBuffer):
        def list_scheduled_due_ats(self, org_id, channel_id):
            return ["2026-07-01T18:00:00Z"]  # the default first slot is taken

    buf = BusyBuffer()
    channels = [{"id": "yt1", "service": "youtube", "isDisconnected": False,
                 "isLocked": False, "isQueuePaused": False}]
    schedule_run(
        clips_dir=tmp_path, resolved_channels=channels, buffer=buf, org_id="org1",
        cfg=SimpleNamespace(caption_provider="openai"),
        ledger=__import__("scripts.ledger", fromlist=["Ledger"]).Ledger(tmp_path/"l.json"),
        per_day=1, start_date=date(2026, 7, 1), hour=18, end_hour=22, tz="UTC",
        max_clips=5, dry_run=False)
    # the occupied 18:00 slot must be skipped -> next day
    assert buf.created[0][1] == "2026-07-02T18:00:00Z"


def test_mutation_error_on_one_channel_does_not_abort(tmp_path, monkeypatch):
    from scripts.buffer_client import MutationError
    (tmp_path / "clip_1_final_subtitled.mp4").write_bytes(b"x")
    (tmp_path / "clip_1_score_7.0.json").write_text('{"reason":"r","score":7.0}')
    monkeypatch.setattr("scripts.publish.media_host.upload_clip",
        lambda path, cfg, prefix="publish": {"public_id": "p",
            "video_url": "https://x/clip.mp4", "thumbnail_url": None})
    monkeypatch.setattr("scripts.publish.build_caption",
        lambda meta, provider, cfg: SimpleNamespace(
            caption="c", youtube_title="t", tiktok_title="tt", hashtags=[], source_url=None))

    class PartialBuffer(FakeBuffer):
        def create_post(self, channel_id, **kw):
            if channel_id == "bad":
                raise MutationError("duplicate post detected")
            self.created.append((channel_id, kw["due_at"], kw["scheduling_type"]))
            return f"post-{len(self.created)}"

    buf = PartialBuffer()
    channels = [
        {"id": "yt1", "service": "youtube", "isDisconnected": False,
         "isLocked": False, "isQueuePaused": False},
        {"id": "bad", "service": "tiktok", "isDisconnected": False,
         "isLocked": False, "isQueuePaused": False},
    ]
    summary = schedule_run(
        clips_dir=tmp_path, resolved_channels=channels, buffer=buf, org_id="org1",
        cfg=SimpleNamespace(caption_provider="openai"),
        ledger=__import__("scripts.ledger", fromlist=["Ledger"]).Ledger(tmp_path/"l.json"),
        per_day=1, start_date=date(2026, 7, 1), hour=18, end_hour=22, tz="UTC",
        max_clips=5, dry_run=False)
    assert summary["posted"] == 1               # youtube succeeded
    assert any("tiktok" in s for s in summary["skipped"])
