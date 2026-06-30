from __future__ import annotations

import typing

from openfeature.evaluation_context import EvaluationContext


def to_unleash_context(
    evaluation_context: EvaluationContext | None,
) -> dict[str, typing.Any]:
    if evaluation_context is None:
        return {}

    context = dict(evaluation_context.attributes)
    if evaluation_context.targeting_key and "userId" not in context:
        context["userId"] = evaluation_context.targeting_key

    return context
