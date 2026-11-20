"""Runtime configuration.

Every option can be set through an environment variable with the ``TP_`` prefix
(for example ``TP_DATABASE_URL``) or through ``backend/.env``. Optional
integrations stay disabled until their credentials are provided, so the API
can start with nothing but a database.
"""

from __future__ import annotations

import logging
import secrets
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)


class MailProvider(BaseSettings):
    """IMAP/SMTP endpoints of one mail provider."""

    imap_host: str
    imap_port: int = 993
    smtp_host: str
    smtp_port: int = 465


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TP_",
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # --- application -----------------------------------------------------
    environment: Literal["development", "production", "test"] = "development"
    demo_mode: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])
    timezone: str = "Asia/Shanghai"

    secret_key: SecretStr | None = None
    token_ttl_minutes: int = 12 * 60

    database_url: str = f"sqlite:///{(BACKEND_ROOT / 'var' / 'termpilot.db').as_posix()}"
    data_dir: Path = BACKEND_ROOT / "var"

    # --- campus systems ------------------------------------------------------
    campus_sso_url: str = "https://cas.sustech.edu.cn/cas/login"
    campus_lms_url: str = "https://bb.sustech.edu.cn"
    campus_records_url: str = "https://tis.sustech.edu.cn"
    campus_mail_domain: str = "mail.sustech.edu.cn"
    campus_verify_tls: bool = True
    campus_timeout_seconds: float = 15.0
    campus_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    term_start_override: date | None = None
    term_weeks: int = 16

    # --- language models -----------------------------------------------------
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: SecretStr | None = None
    llm_chat_model: str = "deepseek-chat"
    llm_reasoning_model: str = "deepseek-reasoner"
    llm_timeout_seconds: float = 120.0
    agent_max_steps: int = 6
    history_turns: int = 4

    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_api_key: SecretStr | None = None
    embedding_model: str = "text-embedding-v3"
    embedding_dimensions: int = 1024
    embedding_batch_size: int = 10

    rerank_url: str = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    rerank_api_key: SecretStr | None = None
    rerank_model: str = "gte-rerank-v2"

    web_search_api_key: SecretStr | None = None
    web_search_url: str = "https://google.serper.dev"

    # --- document library ----------------------------------------------------
    search_url: str = "http://localhost:9200"
    search_username: str = "elastic"
    search_password: SecretStr | None = None
    search_index_prefix: str = "termpilot-library"
    upload_max_mb: int = 25
    attachment_max_chars: int = 12_000

    # --- mail ------------------------------------------------------------------
    mail_timeout_seconds: float = 20.0
    mail_providers: dict[str, MailProvider] = Field(
        default_factory=lambda: {
            "qq": MailProvider(imap_host="imap.qq.com", smtp_host="smtp.qq.com"),
            "exmail": MailProvider(imap_host="imap.exmail.qq.com", smtp_host="smtp.exmail.qq.com"),
        }
    )

    # --- assistant safety ------------------------------------------------------
    approval_ttl_minutes: int = 15
    workspace_quota_mb: int = 200

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    # --- derived values --------------------------------------------------------
    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def workspaces_dir(self) -> Path:
        return self.data_dir / "workspaces"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def llm_enabled(self) -> bool:
        return self.llm_api_key is not None

    @property
    def embeddings_enabled(self) -> bool:
        return self.embedding_api_key is not None

    @property
    def web_search_enabled(self) -> bool:
        return self.web_search_api_key is not None

    def signing_key(self) -> str:
        """Return the secret used for tokens and at-rest encryption.

        Outside production a missing key is generated once and kept in
        ``var/secret.key`` so that sessions survive restarts.
        """
        if self.secret_key is not None:
            return self.secret_key.get_secret_value()
        if self.environment == "production":
            raise RuntimeError("TP_SECRET_KEY must be set in production")
        key_file = self.data_dir / "secret.key"
        if key_file.exists():
            return key_file.read_text(encoding="utf-8").strip()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        generated = secrets.token_urlsafe(48)
        key_file.write_text(generated, encoding="utf-8")
        logger.warning("TP_SECRET_KEY is not set; generated a local key at %s", key_file)
        return generated


@lru_cache
def get_settings() -> Settings:
    return Settings()
