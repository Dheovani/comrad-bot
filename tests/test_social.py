import pytest

from comradbot.errors import ValidationError
from comradbot.services.social import prepare_poll


def test_prepare_poll_normalizes_options_and_preserves_policy() -> None:
    plan = prepare_poll(
        question="  When   should we play? ",
        options=" Friday evening | Saturday  afternoon | Sunday ",
        duration_hours=48,
        multiple=True,
    )

    assert plan.question == "When should we play?"
    assert plan.answers == ("Friday evening", "Saturday afternoon", "Sunday")
    assert plan.duration_hours == 48
    assert plan.multiple is True


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ("Friday", "at least two"),
        ("Friday | friday", "unique"),
        (" | ".join(str(index) for index in range(11)), "at most 10"),
        (f"Friday | {'x' * 56}", "at most 55"),
    ],
)
def test_prepare_poll_rejects_invalid_options(options: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        prepare_poll(question="When?", options=options, duration_hours=24, multiple=False)


@pytest.mark.parametrize("duration_hours", [0, 769])
def test_prepare_poll_rejects_duration_outside_discord_limit(duration_hours: int) -> None:
    with pytest.raises(ValidationError, match="between 1 and 768"):
        prepare_poll(
            question="When?",
            options="Friday | Saturday",
            duration_hours=duration_hours,
            multiple=False,
        )
