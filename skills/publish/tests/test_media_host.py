from scripts.media_host import thumbnail_url, public_id_for_clip


def test_thumbnail_url_is_video_frame_jpg():
    url = thumbnail_url("https://res.cloudinary.com/cn/video/upload/v1/pub1.mp4")
    assert url.endswith("pub1.jpg")
    assert "so_1" in url  # still frame at 1s


def test_public_id_has_no_extension():
    pid = public_id_for_clip("clip_1_final_subtitled.mp4", prefix="publish")
    assert pid.startswith("publish/")
    assert not pid.endswith(".mp4")
