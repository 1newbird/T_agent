from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # LLM
    model_provider: str = "openai"
    chat_api_key: str = ""
    base_url: str = ""
    chat_model_name: str = "gpt-5.4"
    embed_api_key: str = ""
    embed_model_name: str = "text-embedding-3-large"


    # Storage
    redis_url: str = "redis://localhost:6379/0"
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # App
    log_level: str = "INFO"
    env: str = "development"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )

settings = Settings()

if __name__ == "__main__":
    # setting 类里的参数与 env 里面的对齐，若 env 里有默认值，不是空值的，需要在类里声明，空值的不用，这里忽略大小写
    print(settings.chat_model_name)
    print(settings.embed_model_name)