from datetime import datetime, timezone, timedelta

from scripts import youtube_uploader as yt


def test_to_rfc3339_is_utc_zulu():
    dt = datetime(2026, 6, 27, 16, 0, 0, tzinfo=timezone.utc)
    assert yt.to_rfc3339(dt) == "2026-06-27T16:00:00Z"


def test_to_rfc3339_converts_offset_to_utc():
    paris = timezone(timedelta(hours=2))
    dt = datetime(2026, 6, 27, 18, 0, 0, tzinfo=paris)  # 18:00 +02:00 == 16:00Z
    assert yt.to_rfc3339(dt) == "2026-06-27T16:00:00Z"


def test_build_insert_body_schedules_private_publishat():
    dt = datetime(2026, 6, 27, 16, 0, 0, tzinfo=timezone.utc)
    body = yt.build_insert_body("Hook title", "desc #Shorts", ["Shorts", "ia"], dt)

    assert body["snippet"]["title"] == "Hook title"
    assert body["snippet"]["tags"] == ["Shorts", "ia"]
    assert body["snippet"]["categoryId"] == yt.DEFAULT_CATEGORY_ID
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["publishAt"] == "2026-06-27T16:00:00Z"
    assert body["status"]["selfDeclaredMadeForKids"] is False


def test_is_quota_error_detects_quota():
    class Resp:
        status = 403

    class Err(Exception):
        resp = Resp()
        content = b'{"error":{"errors":[{"reason":"quotaExceeded"}]}}'

    assert yt.is_quota_error(Err("quotaExceeded")) is True


def test_is_quota_error_false_for_other():
    class Resp:
        status = 400

    class Err(Exception):
        resp = Resp()
        content = b'{"error":"badRequest"}'

    assert yt.is_quota_error(Err("badRequest")) is False
