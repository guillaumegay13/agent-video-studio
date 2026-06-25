"""Draft caption + per-platform titles + hashtags from clip metadata.

LLM is injected (`llm_call`) so it is testable and the real provider call is
isolated. On any LLM failure we fall back to a deterministic template so a single
bad caption never aborts a publish run."""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Caption:
    caption: str
    youtube_title: str
    tiktok_title: str
    hashtags: list[str] = field(default_factory=list)


def _truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def template_fallback(meta: dict) -> Caption:
    reason = (meta.get("reason") or "Highlight from the episode").strip()
    title = _truncate(reason, 90)
    return Caption(
        caption=_truncate(reason, 200),
        youtube_title=_truncate(title, 100),
        tiktok_title=_truncate(title, 90),
        hashtags=["#shorts", "#viral", "#fyp"],
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


_PROMPT = """You write short-form social captions. Given this viral clip metadata,
return ONLY JSON with keys caption, youtube_title, tiktok_title, hashtags (array).
Rules: caption <=200 chars, youtube_title <=100, tiktok_title <=90, 3-6 hashtags.
Metadata: {meta}"""


def build_caption(meta: dict, provider: str, cfg, llm_call=_default_llm_call) -> Caption:
    try:
        raw = llm_call(_PROMPT.format(meta=json.dumps(meta, ensure_ascii=False)),
                       provider, cfg)
        return Caption(
            caption=_truncate(str(raw["caption"]), 200),
            youtube_title=_truncate(str(raw["youtube_title"]), 100),
            tiktok_title=_truncate(str(raw["tiktok_title"]), 90),
            hashtags=[str(h) for h in raw.get("hashtags", [])][:6],
        )
    except Exception:
        return template_fallback(meta)
