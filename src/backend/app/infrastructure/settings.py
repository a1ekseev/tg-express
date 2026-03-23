from __future__ import annotations

from uuid import UUID  # noqa: TC003 - required at runtime for pydantic-settings

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")

    tg_bot_token: str
    tg_proxy_url: str | None = None

    express_bot_id: UUID
    express_cts_url: str
    express_secret_key: str

    database_url: str

    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str

    file_download_base_url: str

    express_system_channel_id: UUID | None
    express_admin_huids: list[UUID]  # noqa: RUF012

    admin_username: str
    admin_password: str
    jwt_secret_key: str

    s3_file_ttl_days: int | None

    retry_max_attempts: int
    retry_base_delay: float
    retry_max_delay: float

    log_level: str
