from __future__ import annotations

import json
import typing
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import ErrorCode
from openfeature.flag_evaluation import FlagResolutionDetails, Reason
from openfeature.provider import AbstractProvider, Metadata

from ._context import to_unleash_context

if typing.TYPE_CHECKING:
    from openfeature.flag_evaluation import FlagValueType


T = typing.TypeVar("T")


@dataclass
class UnleashProviderMetadata(Metadata):
    name: str = "Unleash OpenFeature Provider"


class UnleashClientProtocol(typing.Protocol):
    def is_enabled(
        self,
        feature_name: str,
        context: dict[str, typing.Any] | None = None,
        fallback_function: (
            typing.Callable[[str, dict[str, typing.Any]], bool] | None
        ) = None,
    ) -> bool: ...

    def get_variant(
        self,
        feature_name: str,
        context: dict[str, typing.Any] | None = None,
    ) -> dict[str, typing.Any]: ...


class UnleashFlagProvider(AbstractProvider):
    def __init__(self, client: UnleashClientProtocol) -> None:
        self._client = client

    def get_metadata(self) -> Metadata:
        return UnleashProviderMetadata()

    def resolve_boolean_details(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[bool]:
        context = to_unleash_context(evaluation_context)

        value = self._client.is_enabled(
            flag_key,
            context,
            fallback_function=lambda _feature_name, _context: default_value,
        )

        return FlagResolutionDetails(
            value=value,
            reason=Reason.UNKNOWN,
        )

    def resolve_string_details(
        self,
        flag_key: str,
        default_value: str,
        evaluation_context: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[str]:
        return self._resolve_variant_value(
            flag_key,
            default_value,
            evaluation_context,
            convert=str,
        )

    def resolve_integer_details(
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[int]:
        return self._resolve_variant_value(
            flag_key,
            default_value,
            evaluation_context,
            convert=int,
        )

    def resolve_float_details(
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[float]:
        return self._resolve_variant_value(
            flag_key,
            default_value,
            evaluation_context,
            convert=float,
        )

    def resolve_object_details(
        self,
        flag_key: str,
        default_value: Sequence[FlagValueType] | Mapping[str, FlagValueType],
        evaluation_context: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[Sequence[FlagValueType] | Mapping[str, FlagValueType]]:
        variant = self._client.get_variant(
            flag_key,
            to_unleash_context(evaluation_context),
        )

        payload = variant.get("payload")
        if not isinstance(payload, Mapping) or "value" not in payload:
            return FlagResolutionDetails(
                value=default_value,
                reason=Reason.DEFAULT,
                variant=variant["name"],
            )

        try:
            payload_value = payload["value"]
            value = (
                json.loads(payload_value)
                if isinstance(payload_value, str)
                else payload_value
            )
        except json.JSONDecodeError as exc:
            return FlagResolutionDetails(
                value=default_value,
                reason=Reason.ERROR,
                error_code=ErrorCode.TYPE_MISMATCH,
                error_message=str(exc),
                variant=variant["name"],
            )

        # Pretty sure Unleash can't give us a list here
        # buuuuut, the OF lib suggests we can get one so it doesn't feel harmful to allow this
        if not isinstance(value, (list, dict)):
            return FlagResolutionDetails(
                value=default_value,
                reason=Reason.ERROR,
                error_code=ErrorCode.TYPE_MISMATCH,
                error_message="Variant payload is not a JSON object or array",
                variant=variant["name"],
            )

        return FlagResolutionDetails(
            value=value,
            reason=Reason.UNKNOWN,
            variant=variant["name"],
        )

    def _resolve_variant_value(
        self,
        flag_key: str,
        default_value: T,
        evaluation_context: EvaluationContext | None,
        *,
        convert: typing.Callable[[typing.Any], T],
    ) -> FlagResolutionDetails[T]:
        context = to_unleash_context(evaluation_context)

        variant = self._client.get_variant(flag_key, context)

        payload = variant.get("payload")
        if not isinstance(payload, Mapping) or "value" not in payload:
            return FlagResolutionDetails(
                value=default_value,
                reason=Reason.UNKNOWN,
                variant=variant["name"],
            )

        try:
            value = convert(payload["value"])
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return FlagResolutionDetails(
                value=default_value,
                reason=Reason.ERROR,
                error_code=ErrorCode.TYPE_MISMATCH,
                error_message=str(exc),
                variant=variant["name"],
            )

        return FlagResolutionDetails(
            value=value,
            reason=Reason.UNKNOWN,
            variant=variant["name"],
        )
