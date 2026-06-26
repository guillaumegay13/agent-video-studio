import pytest
import scripts.config as config
from scripts.config import load_config, ConfigError


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    # Keep tests hermetic: don't let the real skill .env leak into os.environ.
    monkeypatch.setattr(config, "load_dotenv", None)


def test_load_config_reads_env(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("OPENAI_API_KEY", "sk")
    cfg = load_config()
    assert cfg.youtube_client_id == "cid"
    assert cfg.youtube_refresh_token == "rt"
    assert cfg.openai_api_key == "sk"


def test_load_config_missing_required_raises(monkeypatch):
    monkeypatch.delenv("YOUTUBE_REFRESH_TOKEN", raising=False)
    with pytest.raises(ConfigError):
        load_config(require=("YOUTUBE_REFRESH_TOKEN",))
