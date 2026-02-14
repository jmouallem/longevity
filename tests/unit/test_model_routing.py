from app.services.llm import select_model_for_task


def test_select_model_for_utility_task() -> None:
    chosen = select_model_for_task("gpt-4.1", "gpt-4.1", "gpt-4.1-mini", "summarization")
    assert chosen == "gpt-4.1-mini"


def test_select_model_for_reasoning_task() -> None:
    chosen = select_model_for_task("gpt-4.1", "gpt-4.1", "gpt-4.1-mini", "reasoning")
    assert chosen == "gpt-4.1"


def test_select_model_for_deep_think_task() -> None:
    chosen = select_model_for_task("gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "deep_think")
    assert chosen == "gpt-4.1"
