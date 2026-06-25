from types import SimpleNamespace
from scripts.ledger import Ledger
from scripts.cleanup import run_cleanup


class FakeBuffer:
    def __init__(self, statuses):
        self.statuses = statuses
    def post_status(self, post_id):
        return self.statuses[post_id]


def test_deletes_only_when_all_posts_sent(tmp_path, monkeypatch):
    led = Ledger(tmp_path / "l.json")
    led.upsert_asset("clip_1", "pub1", "https://x/c.mp4")
    led.record_post("clip_1", "c1", "p1", "automatic", "2026-07-01T16:00:00Z", "posted")
    led.record_post("clip_1", "c2", "p2", "automatic", "2026-07-01T16:00:00Z", "posted")
    led.save()

    deleted = []
    monkeypatch.setattr("scripts.cleanup.media_host.destroy_clip",
                        lambda pub, cfg: deleted.append(pub) or True)

    # one still sending -> must NOT delete
    buf = FakeBuffer({"p1": "sent", "p2": "sending"})
    result = run_cleanup(buf, led, cfg=SimpleNamespace())
    assert deleted == []
    assert result["retained"] == 1

    # both sent -> delete
    buf = FakeBuffer({"p1": "sent", "p2": "sent"})
    result = run_cleanup(buf, led, cfg=SimpleNamespace())
    assert deleted == ["pub1"]
    assert result["deleted"] == 1


def test_cleanup_tolerates_post_status_error(tmp_path, monkeypatch):
    led = Ledger(tmp_path / "l.json")
    led.upsert_asset("clip_1", "pub1", "https://x/c.mp4")
    led.record_post("clip_1", "c1", "p1", "automatic", "2026-07-01T16:00:00Z", "posted")
    led.save()

    deleted = []
    monkeypatch.setattr("scripts.cleanup.media_host.destroy_clip",
                        lambda pub, cfg: deleted.append(pub) or True)

    class BrokenBuffer:
        def post_status(self, post_id):
            raise RuntimeError("post deleted in UI")

    result = run_cleanup(BrokenBuffer(), led, cfg=SimpleNamespace())
    assert deleted == []           # unknown status -> retained, not deleted
    assert result["retained"] == 1
