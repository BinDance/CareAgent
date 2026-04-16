from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / '.env'


class AgentCoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_ENV_FILE), env_file_encoding='utf-8', extra='ignore')

    llm_api_key: str = Field(default='', alias='LLM_API_KEY')
    llm_base_url: str = Field(default='https://api.xiaomimimo.com/v1', alias='LLM_BASE_URL')
    llm_model: str = Field(default='mimo-v2-omni', alias='LLM_MODEL')
    mcp_server_url: str = Field(default='http://localhost:9000/mcp', alias='MCP_SERVER_URL')
    app_env: str = Field(default='development', alias='APP_ENV')
    langsmith_tracing: bool = Field(default=False, alias='LANGSMITH_TRACING')

@lru_cache(maxsize=1)
def get_settings() -> AgentCoreSettings:
    return AgentCoreSettings()
