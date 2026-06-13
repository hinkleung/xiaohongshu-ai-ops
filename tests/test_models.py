from app.models import AIConfig, Post, GenerationHistory
from app.schemas import AIConfigCreate, PostCreate, GenerateRequest


def test_ai_config_create(test_db):
    config = AIConfig(provider="openai", api_key="encrypted_key",
                       quick_model="gpt-4o-mini", deep_model="gpt-4o")
    test_db.add(config)
    test_db.commit()
    assert config.id is not None
    assert config.is_active is False


def test_post_tags(test_db):
    post = Post(title="Test", content="Hello", status="draft")
    post.set_tags(["美食", "旅行"])
    test_db.add(post)
    test_db.commit()
    assert post.get_tags() == ["美食", "旅行"]


def test_generate_request_schema():
    req = GenerateRequest(theme="春日出游", images=["/uploads/1.jpg"])
    assert req.theme == "春日出游"
    assert req.ai_provider is None
