from scripts.captioner import build_caption, template_fallback


def test_template_fallback_uses_reason():
    meta = {"reason": "A surprising claim about AI costs", "score": 8.0}
    cap = template_fallback(meta)
    assert "AI costs" in cap.caption
    assert cap.youtube_title
    assert isinstance(cap.hashtags, list) and cap.hashtags


def test_build_caption_uses_llm_then_maps(monkeypatch):
    def fake_llm(prompt, provider, cfg):
        return {
            "caption": "Watch this 🔥",
            "youtube_title": "AI costs nothing?",
            "tiktok_title": "AI costs nothing",
            "hashtags": ["#ai", "#shorts"],
        }
    cap = build_caption({"reason": "r", "score": 7.0}, provider="openai",
                        cfg=None, llm_call=fake_llm)
    assert cap.caption == "Watch this 🔥"
    assert cap.youtube_title == "AI costs nothing?"


def test_build_caption_falls_back_on_llm_error():
    def boom(prompt, provider, cfg):
        raise RuntimeError("api down")
    cap = build_caption({"reason": "great moment", "score": 7.0},
                        provider="openai", cfg=None, llm_call=boom)
    assert "great moment" in cap.caption  # fell back to template


def test_extract_source_url_from_yt_dlp_filename():
    from scripts.captioner import extract_source_url
    meta = {"original_video": "/x/L'IA au service ... s2 ep5_4OlWf_Vj6U4.mp4"}
    assert extract_source_url(meta) == "https://youtu.be/4OlWf_Vj6U4"
    assert extract_source_url({"original_video": "/x/local-clip.mp4"}) is None
    assert extract_source_url({}) is None


def test_compose_description_appends_link_and_hashtags():
    from scripts.captioner import Caption, compose_description
    cap = Caption(caption="Hook line", youtube_title="t", tiktok_title="tt",
                  hashtags=["#ai", "#shorts"], source_url="https://youtu.be/abc12345678")
    body = compose_description(cap)
    assert "Hook line" in body
    assert "#ai #shorts" in body
    assert "🎥 https://youtu.be/abc12345678" in body


def test_template_fallback_carries_source_url():
    meta = {"reason": "un moment fort", "original_video": "/x/ep_4OlWf_Vj6U4.mp4"}
    cap = template_fallback(meta)
    assert cap.source_url == "https://youtu.be/4OlWf_Vj6U4"
