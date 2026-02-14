from app.core.safety import detect_urgent_flags


def test_detect_urgent_flags_chest_pain() -> None:
    flags = detect_urgent_flags("I have chest pain and feel faint.")
    assert "urgent_symptom_language" in flags
