import os
import pytest
from scripts.config import load_config, ConfigError


def test_load_config_reads_env(monkeypatch):
    monkeypatch.setenv("BUFFER_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "cn")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "ck")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "cs")
    cfg = load_config()
    assert cfg.buffer_token == "tok"
    assert cfg.cloudinary_cloud_name == "cn"


def test_load_config_missing_required_raises(monkeypatch):
    monkeypatch.delenv("BUFFER_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDINARY_CLOUD_NAME", raising=False)
    with pytest.raises(ConfigError):
        load_config(require=("BUFFER_ACCESS_TOKEN",))
