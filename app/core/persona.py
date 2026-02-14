def apply_longevity_alchemist_voice(answer: str, mode: str) -> str:
    if mode == "deep":
        prefix = "Here is a structured game plan. "
    else:
        prefix = "Here is a practical next move. "
    return f"{prefix}{answer.strip()}"
