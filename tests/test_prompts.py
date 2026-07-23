from comradbot.ai.prompts import COMRADBOT_PERSONA, resolve_comradbot_persona


def test_persona_keeps_the_caricature_separate_from_unsolicited_politics() -> None:
    prompt = COMRADBOT_PERSONA.lower()

    assert "comrade" in prompt
    assert "companheiro" in prompt
    assert "do not introduce politics" in prompt
    assert "only discuss politics when the user explicitly brings up" in prompt
    assert "do not impersonate a real person" in prompt


def test_custom_persona_has_priority_and_blank_value_uses_default() -> None:
    assert resolve_comradbot_persona("  A custom persona  ") == "A custom persona"
    assert resolve_comradbot_persona("") == COMRADBOT_PERSONA
    assert resolve_comradbot_persona(None) == COMRADBOT_PERSONA
