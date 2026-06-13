import pytest
from app.services.llm_factory import LLMFactory, ProviderConfig


def test_create_openai_llm():
    config = ProviderConfig(
        provider="openai",
        api_key="sk-test",
        quick_model="gpt-4o-mini",
        deep_model="gpt-4o",
        api_base=None,
    )
    llm = LLMFactory.create(config, tier="quick")
    assert llm is not None
    assert llm.model_name == "gpt-4o-mini"


def test_create_deepseek_llm():
    config = ProviderConfig(
        provider="deepseek",
        api_key="sk-test",
        quick_model="deepseek-chat",
        deep_model="deepseek-chat",
        api_base="https://api.deepseek.com/v1",
    )
    llm = LLMFactory.create(config, tier="deep")
    assert llm is not None


def test_invalid_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        LLMFactory.create(ProviderConfig(
            provider="unknown", api_key="x",
            quick_model="m1", deep_model="m2",
        ), tier="quick")
