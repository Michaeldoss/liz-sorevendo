from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Twilio
    TWILIO_ACCOUNT_SID: str = "stub"
    TWILIO_AUTH_TOKEN: str = "stub"
    TWILIO_WHATSAPP_NUMBER: str = "stub"
    GROUP_NOTIFY_NUMBER: str = ""

    # Anthropic
    ANTHROPIC_API_KEY: str = "stub"

    # Ambiente
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings():
    return Settings()
