import pytest

from app.services.llm import parse_llm_json


def test_parse_llm_json_valid() -> None:
    payload = parse_llm_json('{"answer":"ok","suggested_questions":["a","b","c"]}')
    assert payload["answer"] == "ok"


def test_parse_llm_json_malformed_raises() -> None:
    with pytest.raises(ValueError):
        parse_llm_json('{"answer":"bad",}')
