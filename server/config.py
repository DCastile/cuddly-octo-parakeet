"""Configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Recall.ai
    recall_api_key: str = ""
    recall_region: str = "us-east-1"

    # OpenAI (Whisper STT + TTS)
    openai_api_key: str = ""

    # Anthropic (Claude reasoning)
    anthropic_api_key: str = ""

    # Server
    port: int = 8000
    ws_port: int = 8001

    # Agent page URL (public, loaded by Recall's bot)
    agent_page_url: str = "https://dcastile.github.io/cuddly-octo-parakeet/page/"

    # Bot
    bot_name: str = "Clawdius"
    activation_keywords: str = "clawdius,claudius,claw"

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8"}

    @property
    def recall_base_url(self) -> str:
        return f"https://{self.recall_region}.recall.ai"

    @property
    def activation_words(self) -> list[str]:
        return [w.strip().lower() for w in self.activation_keywords.split(",")]


settings = Settings()
