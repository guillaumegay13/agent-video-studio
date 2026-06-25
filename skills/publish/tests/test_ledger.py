from pathlib import Path
from scripts.ledger import Ledger


def test_record_and_reload(tmp_path):
    path = tmp_path / "ledger.json"
    led = Ledger(path)
    led.upsert_asset(clip_key="clip_1", cloudinary_public_id="pub1",
                     video_url="https://x/clip.mp4")
    led.record_post(clip_key="clip_1", channel_id="c1", post_id="p1",
                    mode="automatic", due_at="2026-07-01T16:00:00Z", state="posted")
    led.save()

    reloaded = Ledger(path)
    rows = reloaded.posts_for_asset("pub1")
    assert len(rows) == 1
    assert rows[0]["post_id"] == "p1"
    assert rows[0]["state"] == "posted"


def test_already_posted_is_idempotent(tmp_path):
    led = Ledger(tmp_path / "ledger.json")
    led.upsert_asset("clip_1", "pub1", "https://x/clip.mp4")
    led.record_post("clip_1", "c1", "p1", "automatic", "2026-07-01T16:00:00Z", "posted")
    assert led.has_post("clip_1", "c1") is True
    assert led.has_post("clip_1", "c2") is False


def test_atomic_save_no_partial_file(tmp_path):
    path = tmp_path / "ledger.json"
    led = Ledger(path)
    led.upsert_asset("clip_1", "pub1", "https://x/clip.mp4")
    led.save()
    assert list(path.parent.glob("*.tmp*")) == []
    assert path.exists()
