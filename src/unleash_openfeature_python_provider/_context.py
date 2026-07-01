from __future__ import annotations

import logging
import typing
from collections.abc import Mapping, Sequence

from openfeature.evaluation_context import EvaluationContext

BASE_CONTEXT_KEYS = {
    "currentTime",
    "userId",
    "sessionId",
    "remoteAddress",
    "environment",
    "appName",
}

logger = logging.getLogger(__name__)


def to_unleash_context(
    evaluation_context: EvaluationContext | None,
) -> dict[str, typing.Any]:
    if evaluation_context is None:
        return {}

    context: dict[str, typing.Any] = {}
    properties: dict[str, typing.Any] = {}

    for key, value in evaluation_context.attributes.items():
        if key in BASE_CONTEXT_KEYS:
            context[key] = value
            continue

        if _is_nested(value):
            logger.warning("Discarding nested Unleash context property: %s", key)
            continue

        properties[key] = value

    if evaluation_context.targeting_key:
        context["userId"] = evaluation_context.targeting_key

    if properties:
        context["properties"] = properties

    return context


def _is_nested(value: typing.Any) -> bool:
    return isinstance(value, Mapping) or (
        isinstance(value, Sequence) and not isinstance(value, str)
    )
