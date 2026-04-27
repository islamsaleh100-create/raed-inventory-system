from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from app.models import Evaluation, EvaluationFinalRating, EvaluationTargetMode


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rating(percentage: Decimal) -> EvaluationFinalRating:
    if percentage < Decimal("60"):
        return EvaluationFinalRating.POOR
    if percentage < Decimal("75"):
        return EvaluationFinalRating.NEEDS_IMPROVEMENT
    if percentage < Decimal("90"):
        return EvaluationFinalRating.GOOD
    return EvaluationFinalRating.EXCELLENT


def calculate(evaluation: Evaluation) -> dict:
    valid_answers = [a for a in evaluation.answers if not a.is_na and a.score is not None]
    low_score_count = 0
    total_score = Decimal("0")
    by_section: dict[str, list[Decimal]] = defaultdict(list)
    section_weights: dict[str, Decimal | None] = {}

    for answer in valid_answers:
        score = Decimal(str(answer.score))
        max_score = Decimal(str(answer.max_score_snapshot))
        total_score += score
        percentage = (score / max_score) * Decimal("100")
        key = answer.section_name_snapshot
        by_section[key].append(percentage)
        section_weights[key] = Decimal(str(answer.section_weight_snapshot)) if answer.section_weight_snapshot is not None else None
        question = answer.question
        if question and score <= Decimal(str(question.low_score_threshold)):
            low_score_count += 1

    if not by_section:
        final_percentage = Decimal("0")
    else:
        section_percentages = {
            section: sum(values, Decimal("0")) / Decimal(len(values))
            for section, values in by_section.items()
        }
        weights = {k: v for k, v in section_weights.items() if v is not None}
        if weights and len(weights) == len(section_percentages):
            weight_total = sum(weights.values(), Decimal("0"))
            final_percentage = (
                sum(section_percentages[s] * weights[s] for s in section_percentages) / weight_total
                if weight_total > 0 else Decimal("0")
            )
        else:
            final_percentage = sum(section_percentages.values(), Decimal("0")) / Decimal(len(section_percentages))

    final_percentage = _round(final_percentage)
    final_rating = _rating(final_percentage)
    action_required = (
        (evaluation.target_mode == EvaluationTargetMode.BRANCH and final_percentage < Decimal("60"))
        or (evaluation.target_mode == EvaluationTargetMode.EMPLOYEE and final_percentage < Decimal("70"))
    )
    return {
        "total_score": _round(total_score),
        "total_percentage": final_percentage,
        "final_rating": final_rating,
        "low_score_count": low_score_count,
        "action_required_flag": action_required,
    }
