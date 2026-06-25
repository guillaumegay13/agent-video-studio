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
