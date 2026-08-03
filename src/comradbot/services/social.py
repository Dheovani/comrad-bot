"""Bounded business rules for lightweight Discord social utilities."""

from dataclasses import dataclass

from comradbot.errors import ValidationError

MAX_POLL_QUESTION_LENGTH = 300
MAX_POLL_ANSWER_LENGTH = 55
MAX_POLL_ANSWERS = 10
MAX_POLL_DURATION_HOURS = 32 * 24


@dataclass(frozen=True, slots=True)
class PollPlan:
    question: str
    answers: tuple[str, ...]
    duration_hours: int
    multiple: bool


def prepare_poll(*, question: str, options: str, duration_hours: int, multiple: bool) -> PollPlan:
    """Validate and normalize a pipe-separated native Discord poll request."""
    normalized_question = " ".join(question.split())
    if not normalized_question:
        raise ValidationError("The poll question cannot be empty.")
    if len(normalized_question) > MAX_POLL_QUESTION_LENGTH:
        raise ValidationError(
            f"The poll question cannot exceed {MAX_POLL_QUESTION_LENGTH} characters."
        )
    if not 1 <= duration_hours <= MAX_POLL_DURATION_HOURS:
        raise ValidationError(
            f"Poll duration must be between 1 and {MAX_POLL_DURATION_HOURS} hours."
        )

    answers = tuple(" ".join(option.split()) for option in options.split("|") if option.strip())
    if len(answers) < 2:
        raise ValidationError("Provide at least two options separated by `|`.")
    if len(answers) > MAX_POLL_ANSWERS:
        raise ValidationError(f"A poll can have at most {MAX_POLL_ANSWERS} options.")
    if any(len(answer) > MAX_POLL_ANSWER_LENGTH for answer in answers):
        raise ValidationError(
            f"Each poll option must contain at most {MAX_POLL_ANSWER_LENGTH} characters."
        )
    if len({answer.casefold() for answer in answers}) != len(answers):
        raise ValidationError("Poll options must be unique.")

    return PollPlan(normalized_question, answers, duration_hours, multiple)
