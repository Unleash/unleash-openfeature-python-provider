from __future__ import annotations

import json
import typing
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import ErrorCode
from openfeature.flag_evaluation import FlagResolutionDetails, FlagValueType, Reason
from openfeature.provider import AbstractProvider, Metadata
from UnleashClient import UnleashClient

from ._context import to_unleash_context
from ._version import __version__

T = typing.TypeVar("T")

SDK_FLAVOR = "unleash-openfeature-python-provider"
SDK_FLAVOR_VERSION = __version__


class _VariantResolutionError(Exception):
    def __init__(
        self,
        reason: Reason,
        *,
        error_code: ErrorCode | None = None,
        error_message: str | None = None,
    ) -> None:
        super().__init__(error_message)
        self.reason = reason
        self.error_code = error_code
        self.error_message = error_message


@dataclass
class UnleashProviderMetadata(Metadata):
    name: str = "Unleash OpenFeature Provider"


def _resolve_payload_value(
    variant: Mapping[str, typing.Any],
    *,
    payload_types: set[str],
) -> typing.Any:
    # Enabled property being false is the SDK telling us it returned
    # the default variant for whatever reason.
    if not variant.get("enabled"):
        raise _VariantResolutionError(Reason.UNKNOWN)

    payload = variant.get("payload")
    if not isinstance(payload, Mapping) or "value" not in payload:
        raise _VariantResolutionError(
            Reason.ERROR,
            error_code=ErrorCode.TYPE_MISMATCH,
            error_message="Variant payload is not present on the resolved variant",
        )

    payload_type = payload.get("type")
    if payload_type not in payload_types:
        raise _VariantResolutionError(
            Reason.ERROR,
            error_code=ErrorCode.TYPE_MISMATCH,
            error_message=(
                f"Variant payload has type {payload_type!r}, "
                f"expected one of {sorted(payload_types)!r}"
            ),
        )

    return payload["value"]


def _resolve_object_payload(
    variant: Mapping[str, typing.Any],
) -> Sequence[FlagValueType] | Mapping[str, FlagValueType]:
    payload_value = _resolve_payload_value(variant, payload_types={"json"})

    try:
        value = (
            json.loads(payload_value)
            if isinstance(payload_value, str)
            else payload_value
        )
    except json.JSONDecodeError as exc:
        raise _VariantResolutionError(
            Reason.ERROR,
            error_code=ErrorCode.PARSE_ERROR,
            error_message=str(exc),
        ) from exc

    if value is None:
        raise _VariantResolutionError(
            Reason.ERROR,
            error_code=ErrorCode.TYPE_MISMATCH,
            error_message="Variant payload is JSON null",
        )

    return typing.cast(
        Sequence[FlagValueType] | Mapping[str, FlagValueType],
        value,
    )


# This exists so we can yield error types that we expect
# Only really needed for spec compliance
def _parse_int(value: typing.Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise _VariantResolutionError(
            Reason.ERROR,
            error_code=ErrorCode.PARSE_ERROR,
            error_message=str(exc),
        ) from exc


def _parse_float(value: typing.Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise _VariantResolutionError(
            Reason.ERROR,
            error_code=ErrorCode.PARSE_ERROR,
            error_message=str(exc),
        ) from exc


class UnleashClientProtocol(typing.Protocol):
    def initialize_client(self, fetch_toggles: bool = True) -> None: ...

    def destroy(self) -> None: ...

    def is_enabled(
        self,
        feature_name: str,
        context: dict[str, typing.Any] | None = None,
        fallback_function: (
            typing.Callable[[str, dict[str, typing.Any] | None], bool] | None
        ) = None,
    ) -> bool: ...

    def get_variant(
        self,
        feature_name: str,
        context: dict[str, typing.Any] | None = None,
    ) -> dict[str, typing.Any]: ...


class UnleashFlagProvider(AbstractProvider):
    def __init__(self, url: str, app_name: str, **client_options: typing.Any) -> None:
        # The provider builds and owns the client so it can always stamp its own
        client_options["sdk_flavor"] = SDK_FLAVOR
        client_options["sdk_flavor_version"] = SDK_FLAVOR_VERSION
        self._client: UnleashClientProtocol = UnleashClient(
            url=url,
            app_name=app_name,
            **client_options,
        )

    @classmethod
    def _from_client(cls, client: UnleashClientProtocol) -> UnleashFlagProvider:
        """Test-only seam: wrap an already-built (or fake) client directly,
        bypassing UnleashClient construction. Not part of the public API."""
        provider = cls.__new__(cls)
        provider._client = client
        return provider

    def get_metadata(self) -> Metadata:
        return UnleashProviderMetadata()

    def initialize(self, evaluation_context: EvaluationContext) -> None:
        self._client.initialize_client()

    def shutdown(self) -> None:
        self._client.destroy()

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
            payload_types={"string", "csv"},
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
            payload_types={"number"},
            convert=_parse_int,
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
            payload_types={"number"},
            convert=_parse_float,
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

        try:
            value = _resolve_object_payload(variant)
        except _VariantResolutionError as exc:
            return FlagResolutionDetails(
                value=default_value,
                reason=exc.reason,
                error_code=exc.error_code,
                error_message=exc.error_message,
                variant=variant.get("name"),
            )

        return FlagResolutionDetails(
            value=value,
            reason=Reason.UNKNOWN,
            variant=variant.get("name"),
        )

    def _resolve_variant_value(
        self,
        flag_key: str,
        default_value: T,
        evaluation_context: EvaluationContext | None,
        *,
        payload_types: set[str],
        convert: typing.Callable[[typing.Any], T],
    ) -> FlagResolutionDetails[T]:
        context = to_unleash_context(evaluation_context)

        variant = self._client.get_variant(flag_key, context)

        try:
            payload_value = _resolve_payload_value(variant, payload_types=payload_types)
            value = convert(payload_value)
            return FlagResolutionDetails(
                value=value,
                reason=Reason.UNKNOWN,
                variant=variant.get("name"),
            )

        except _VariantResolutionError as exc:
            return FlagResolutionDetails(
                value=default_value,
                reason=exc.reason,
                error_code=exc.error_code,
                error_message=exc.error_message,
                variant=variant.get("name"),
            )
        except (TypeError, ValueError) as exc:
            return FlagResolutionDetails(
                value=default_value,
                reason=Reason.ERROR,
                error_code=ErrorCode.TYPE_MISMATCH,
                error_message=str(exc),
                variant=variant.get("name"),
            )
