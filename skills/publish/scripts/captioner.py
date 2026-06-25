"""Draft caption + per-platform titles + hashtags from clip metadata.

LLM is injected (`llm_call`) so it is testable and the real provider call is
isolated. On any LLM failure we fall back to a deterministic template so a single
bad caption never aborts a publish run."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# yt-dlp names downloads `<title>_<11-char-id>.<ext>`; pull the YouTube id back out.
_YT_ID_RE = re.compile(r"_([A-Za-z0-9_-]{11})\.(?:mp4|mkv|webm|mov)$")


@dataclass
class Caption:
    caption: str
    youtube_title: str
    tiktok_title: str
    hashtags: list[str] = field(default_factory=list)
    source_url: str | None = None


def _truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def extract_source_url(meta: dict) -> str | None:
    """Recover the source video's YouTube URL from the clip metadata.

    The pipeline stores `original_video` as the downloaded file path, whose name
    ends in the 11-char YouTube id (yt-dlp convention). Returns None for local
    sources with no recoverable id."""
    original = meta.get("original_video") or ""
    m = _YT_ID_RE.search(original)
    return f"https://youtu.be/{m.group(1)}" if m else None


def compose_description(cap: Caption) -> str:
    """Assemble the post body: caption, hashtags, then a link to the full video."""
    parts = [cap.caption]
    if cap.hashtags:
        parts.append(" ".join(cap.hashtags))
    if cap.source_url:
        parts.append(f"🎥 {cap.source_url}")
    return "\n\n".join(parts)


def template_fallback(meta: dict) -> Caption:
    reason = (meta.get("reason") or "Highlight from the episode").strip()
    title = _truncate(reason, 90)
    return Caption(
        caption=_truncate(reason, 200),
        youtube_title=_truncate(title, 100),
        tiktok_title=_truncate(title, 90),
        hashtags=["#shorts", "#viral", "#fyp"],
        source_url=extract_source_url(meta),
    )


def _default_llm_call(prompt: str, provider: str, cfg) -> dict:  # pragma: no cover
    """Call the configured provider and return a JSON dict. Real network call."""
    import requests

    if provider == "anthropic":
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": cfg.anthropic_api_key,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-opus-4-8", "max_tokens": 400,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"]
    else:  # openai
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {cfg.openai_api_key}"},
            json={"model": "gpt-4o-mini", "response_format": {"type": "json_object"},
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
    return json.loads(text)


_PROMPT = """You are a viral short-form video editor writing the post copy for a clip.
Write in the SAME LANGUAGE as the clip's spoken content — infer it from the metadata
below (the `reason` field is written in that language). Do NOT translate to English.

Make the title a scroll-stopping HOOK: curiosity, tension, a bold claim, or a number.
Punchy, not clickbait-spammy. The caption should expand the hook in 1-2 lines.

Return ONLY JSON with keys: caption, youtube_title, tiktok_title, hashtags (array).
Rules: caption <=200 chars, youtube_title <=100, tiktok_title <=90, 3-6 hashtags
(in the content's language where natural). Metadata: {meta}"""


def build_caption(meta: dict, provider: str, cfg, llm_call=_default_llm_call) -> Caption:
    try:
        raw = llm_call(_PROMPT.format(meta=json.dumps(meta, ensure_ascii=False)),
                       provider, cfg)
        return Caption(
            caption=_truncate(str(raw["caption"]), 200),
            youtube_title=_truncate(str(raw["youtube_title"]), 100),
            tiktok_title=_truncate(str(raw["tiktok_title"]), 90),
            hashtags=[str(h) for h in raw.get("hashtags", [])][:6],
            source_url=extract_source_url(meta),
        )
    except Exception:
        return template_fallback(meta)
