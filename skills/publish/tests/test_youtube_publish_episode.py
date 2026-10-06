from datetime import datetime, timezone

from scripts.youtube_publish_episode import build_episode_body, validate_metadata


def test_validate_accepts_normal_metadata():
    assert validate_metadata("Un titre", "Une description") == []


def test_validate_rejects_long_title_and_angle_brackets():
    errors = validate_metadata("x" * 101, "a <b> c")
    assert any("title is 101 chars" in e for e in errors)
    assert any("description contains" in e for e in errors)


def test_body_without_schedule_keeps_privacy():
    body = build_episode_body("t", "d", ["IA"], "unlisted", None)
    assert body["status"] == {"privacyStatus": "unlisted", "selfDeclaredMadeForKids": False}
    assert body["snippet"]["tags"] == ["IA"]


def test_body_with_schedule_is_private_with_publish_at():
    when = datetime(2026, 10, 8, 16, 0, tzinfo=timezone.utc)
    body = build_episode_body("t", "d", [], "public", when)
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["publishAt"] == "2026-10-08T16:00:00Z"
