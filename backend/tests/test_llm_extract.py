from app.llm import extract_json


def test_extract_json_parses_plain_object():
    assert extract_json('{"days": []}') == {"days": []}


def test_extract_json_parses_markdown_code_block():
    text = """```json
{"days": []}
```"""
    assert extract_json(text) == {"days": []}


def test_extract_json_ignores_trailing_object():
    text = """{"days": [{"morning": "A"}]}
{"extra": true}"""

    assert extract_json(text) == {
        "days": [{"morning": "A"}],
    }
