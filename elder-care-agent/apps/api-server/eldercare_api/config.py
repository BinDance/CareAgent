from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / '.env'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_ENV_FILE), env_file_encoding='utf-8', extra='ignore')

    database_url: str = Field(default='postgresql+psycopg://postgres:postgres@localhost:5432/eldercare', alias='DATABASE_URL')
    redis_url: str = Field(default='redis://localhost:6379/0', alias='REDIS_URL')
    llm_api_key: str = Field(default='', alias='LLM_API_KEY')
    llm_base_url: str = Field(default='https://api.xiaomimimo.com/v1', alias='LLM_BASE_URL')
    llm_model: str = Field(default='mimo-v2-omni', alias='LLM_MODEL')
    langsmith_api_key: str = Field(default='', alias='LANGSMITH_API_KEY')
    langsmith_tracing: bool = Field(default=False, alias='LANGSMITH_TRACING')
    app_env: str = Field(default='development', alias='APP_ENV')
    secret_key: str = Field(default='change-me', alias='SECRET_KEY')
    next_public_api_base_url: str = Field(default='http://localhost:8000', alias='NEXT_PUBLIC_API_BASE_URL')
    mcp_server_url: str = Field(default='http://localhost:9000/mcp', alias='MCP_SERVER_URL')
    eldercare_auth_optional: bool = Field(default=True, alias='ELDERCARE_AUTH_OPTIONAL')
    upload_dir: str = 'uploads'
    scheduler_enabled: bool = True
    api_host: str = '0.0.0.0'
    api_port: int = 8000

    @property
    def resolved_upload_dir(self) -> Path:
        return (Path(__file__).resolve().parent.parent / self.upload_dir).resolve()

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
