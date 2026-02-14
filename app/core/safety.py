URGENT_SYMPTOM_PATTERNS = [
    "chest pain",
    "pressure in chest",
    "shortness of breath",
    "faint",
    "fainting",
    "passed out",
    "stroke",
    "face droop",
    "slurred speech",
    "one side weak",
]

SUPPLEMENT_PATTERNS = [
    "supplement",
    "stack",
    "creatine",
    "berberine",
    "ashwagandha",
    "omega-3",
]


def detect_urgent_flags(question: str) -> list[str]:
    lowered = question.lower()
    flags = [pattern for pattern in URGENT_SYMPTOM_PATTERNS if pattern in lowered]
    if flags:
        return ["urgent_symptom_language"]
    return []


def has_supplement_topic(question: str) -> bool:
    lowered = question.lower()
    return any(token in lowered for token in SUPPLEMENT_PATTERNS)


def emergency_response() -> dict:
    return {
        "answer": (
            "Your message includes symptoms that could need urgent care. "
            "Please seek immediate medical attention or call emergency services now."
        ),
        "rationale_bullets": [
            "Some symptoms can signal a time-sensitive emergency.",
            "Remote coaching is not safe for urgent symptom evaluation.",
            "Fast in-person assessment is the safest next step.",
        ],
        "recommended_actions": [
            {
                "title": "Get urgent care now",
                "steps": [
                    "Call local emergency services immediately.",
                    "Do not drive yourself if you feel faint or unstable.",
                    "Share your current symptoms clearly with clinicians.",
                ],
            }
        ],
        "suggested_questions": [
            "Want a short summary you can read to emergency services?",
            "Want a checklist of recent metrics to bring to clinicians?",
            "Want guidance on what baseline information to share after urgent care?",
        ],
        "safety_flags": ["urgent_symptom_language"],
        "disclaimer": "This is coaching guidance, not medical diagnosis.",
    }


def supplement_caution_text() -> str:
    return "Supplement guidance should be conservative; check with your clinician if you use medications or have conditions."
