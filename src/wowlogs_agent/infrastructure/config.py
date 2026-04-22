from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Environment-backed configuration. Never log secret values."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    wcl_client_id: str = Field(default="")
    wcl_client_secret: SecretStr = Field(default=SecretStr(""))
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))

    wowlogs_llm_model: str = Field(default="claude-opus-4-6")
    wcl_endpoint: str = Field(default="https://www.warcraftlogs.com/api/v2/client")
    wcl_token_url: str = Field(default="https://www.warcraftlogs.com/oauth/token")

    project_root: Path = Field(default_factory=_default_project_root)

    @property
    def llm_model(self) -> str:
        return self.wowlogs_llm_model

    @property
    def cache_dir(self) -> Path:
        return self.project_root / ".cache"

    @property
    def runs_dir(self) -> Path:
        return self.project_root / "runs"

    @property
    def prompts_dir(self) -> Path:
        return self.project_root / "prompts"

    @classmethod
    def load(cls, project_root: Path | None = None) -> Settings:
        settings = cls()
        if project_root is not None:
            object.__setattr__(settings, "project_root", project_root)
        return settings

    # Convenience unwrappers so callers never touch SecretStr directly.
    @property
    def wcl_client_secret_value(self) -> str:
        return self.wcl_client_secret.get_secret_value()

    @property
    def anthropic_api_key_value(self) -> str:
        return self.anthropic_api_key.get_secret_value()
