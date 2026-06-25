"""Environment-backed configuration for the publish skill."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv optional at runtime; env may be pre-set
    load_dotenv = None


class ConfigError(Exception):
    pass


@dataclass
class Config:
    buffer_token: str
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str
    caption_provider: str
    openai_api_key: str
    anthropic_api_key: str


def _skill_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "SKILL.md").exists():
            return parent
    return Path(__file__).resolve().parent.parent


def load_config(require: tuple[str, ...] = ()) -> Config:
    if load_dotenv is not None:
        load_dotenv(_skill_root() / ".env")
    missing = [k for k in require if not os.environ.get(k)]
    if missing:
        raise ConfigError(f"Missing required env vars: {', '.join(missing)}")
    return Config(
        buffer_token=os.environ.get("BUFFER_ACCESS_TOKEN", ""),
        cloudinary_cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
        cloudinary_api_key=os.environ.get("CLOUDINARY_API_KEY", ""),
        cloudinary_api_secret=os.environ.get("CLOUDINARY_API_SECRET", ""),
        caption_provider=os.environ.get("CAPTION_PROVIDER", "openai"),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )
