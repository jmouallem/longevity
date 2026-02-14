from app.core.context_builder import build_coaching_context


def test_context_builder_baseline_missing(create_user, seed_metrics, seed_scores, db_session) -> None:
    user = create_user(with_ai_config=False)
    seed_metrics(user.id)
    seed_scores(user.id)

    context = build_coaching_context(db_session, user.id)
    assert context["baseline_present"] is False
    assert context["baseline"] is None


def test_context_builder_summarizes_metrics(create_user, seed_baseline, seed_metrics, seed_scores, db_session) -> None:
    user = create_user(with_ai_config=False)
    seed_baseline(user.id)
    seed_metrics(user.id)
    seed_scores(user.id)

    context = build_coaching_context(db_session, user.id)
    assert context["baseline_present"] is True
    sleep_summary = context["metrics_7d_summary"]["sleep_hours"]
    assert "avg_7d" in sleep_summary
    assert "latest" in sleep_summary
    assert "rows" not in context
