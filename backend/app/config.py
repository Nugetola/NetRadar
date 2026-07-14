from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "OIC NetRadar"
    database_url: str = "sqlite+aiosqlite:///./netradar.db"
    poll_interval_seconds: int = 60
    ping_timeout_seconds: int = 2
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "netradar@oic.local"
    smtp_use_tls: bool = True
    sms_gateway_url: str = ""
    sms_api_key: str = ""
    dashboard_url: str = "http://127.0.0.1:5500"
    level_2_escalation_minutes: int = 60
    syslog_port: int = 5515
    snmp_trap_port: int = 1163
    passive_source_allowlist: str = ""
    auth_required: bool = False
    jwt_secret: str = "development-secret-change-me"
    admin_username: str = "netradar-admin"
    admin_password: str = "change-before-production"
    service_api_key: str = ""
    it_support_webhook_url: str = ""
    heartbeat_interval_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()