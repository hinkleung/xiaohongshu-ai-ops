from dataclasses import dataclass
from typing import Optional, Literal
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic


@dataclass
class ProviderConfig:
    provider: str            # claude / openai / deepseek
    api_key: str
    quick_model: str
    deep_model: str
    api_base: Optional[str] = None


class LLMFactory:
    """Multi-provider LLM factory with quick/deep tier routing."""

    @staticmethod
    def create(config: ProviderConfig, tier: Literal["quick", "deep"]):
        model_name = config.quick_model if tier == "quick" else config.deep_model
        provider = config.provider.lower()

        if provider == "openai":
            kwargs = {"model": model_name, "api_key": config.api_key}
            if config.api_base:
                kwargs["base_url"] = config.api_base
            return ChatOpenAI(**kwargs)

        elif provider == "deepseek":
            base = config.api_base or "https://api.deepseek.com/v1"
            return ChatOpenAI(
                model=model_name,
                api_key=config.api_key,
                base_url=base,
            )

        elif provider == "claude":
            return ChatAnthropic(
                model=model_name,
                api_key=config.api_key,
                base_url=config.api_base,
            )

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def from_db_config(db_config, tier: Literal["quick", "deep"]):
        """Create LLM from AIConfig DB model."""
        from app.config import decrypt_api_key
        return LLMFactory.create(
            ProviderConfig(
                provider=db_config.provider,
                api_key=decrypt_api_key(db_config.api_key),
                quick_model=db_config.quick_model,
                deep_model=db_config.deep_model,
                api_base=db_config.api_base,
            ),
            tier=tier,
        )
