from app.agent.nodes import parse_generated_content


def test_parse_generated_content():
    text = "春日出游好时机\n\n周末开着G9去郊外真的太舒服了\n\n#春日 #出行 #小鹏G9"
    title, body, tags = parse_generated_content(text)
    assert "春日出游" in title
    assert "G9" in body
    assert len(tags) == 3
    assert "春日" in tags


def test_parse_generated_content_empty():
    title, body, tags = parse_generated_content("")
    assert title == ""
    assert body == ""
    assert tags == []


def test_parse_generated_content_no_tags():
    text = "Test Title\n\nJust body content"
    title, body, tags = parse_generated_content(text)
    assert title == "Test Title"
    assert "Just body content" in body
    assert tags == []
