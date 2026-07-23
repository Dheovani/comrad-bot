from comradbot.ai.prompts import COMRADBOT_PERSONA


def test_persona_keeps_the_caricature_separate_from_unsolicited_politics() -> None:
    prompt = COMRADBOT_PERSONA.lower()

    assert "comrade" in prompt
    assert "companheiro" in prompt
    assert "do not introduce politics" in prompt
    assert "only discuss politics when the user explicitly brings up" in prompt
    assert "do not impersonate a real person" in prompt
