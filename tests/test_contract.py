from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, cast

import pytest
from openfeature import api
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import ErrorCode
from openfeature.flag_evaluation import FlagEvaluationDetails
from UnleashClient import UnleashClient
from UnleashClient.cache import BaseCache
from UnleashClient.constants import FEATURES_URL

from unleash_openfeature_python_provider import UnleashFlagProvider

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "verifier" / "spec" / "contract.json"
FEATURES_PATH = ROOT / "verifier" / "fixtures" / "unleash-features.json"

CAPABILITIES = {"localEval", "perCallContext"}
KNOWN_GAPS = {
    # Left as an example exclusion in case future work requires an exclusion
    # "object-scalar-json-passthrough": (
    #     "Current provider rejects scalar JSON object payloads; contract expects "
    #     "JsonValue passthrough."
    # ),
}


class MemoryCache:
    bootstrapped = True

    def __init__(self, features: Mapping[str, Any]) -> None:
        self._values: dict[str, Any] = {FEATURES_URL: json.dumps(features)}

    def set(self, key: str, value: Any) -> None:
        self._values[key] = value

    def mset(self, data: dict[str, Any]) -> None:
        self._values.update(data)

    def get(self, key: str, default: Any | None = None) -> Any:
        return self._values.get(key, default)

    def exists(self, key: str) -> bool:
        return key in self._values

    def destroy(self) -> None:
        self._values.clear()


@pytest.fixture(scope="module", autouse=True)
def openfeature_provider() -> Iterator[None]:
    with FEATURES_PATH.open() as file:
        features = json.load(file)

    unleash_client = UnleashClient(
        url="http://unleash-bootstrap.invalid/api",
        app_name="openfeature-python-verifier",
        cache=cast(BaseCache, MemoryCache(features)),
        refresh_interval=60,
        disable_metrics=True,
        disable_registration=True,
    )

    # Hush pyright, I don't care about this type, stop bothering me
    api.set_provider_and_wait(UnleashFlagProvider._from_client(cast(Any, unleash_client)))
    try:
        yield
    finally:
        api.shutdown()
        api.clear_providers()


def applicable_scenarios() -> list[Any]:
    with CONTRACT_PATH.open() as file:
        contract = json.load(file)

    return [
        pytest.param(
            scenario,
            marks=(
                pytest.mark.xfail(reason=KNOWN_GAPS[scenario["id"]], strict=True)
                if scenario["id"] in KNOWN_GAPS
                else ()
            ),
            id=scenario["id"],
        )
        for scenario in contract["scenarios"]
        if set(scenario.get("requires", ())).issubset(CAPABILITIES)
    ]


@pytest.mark.parametrize("scenario", applicable_scenarios())
def test_openfeature_contract_scenario(scenario: Mapping[str, Any]) -> None:
    details = evaluate(scenario)
    expected = scenario["expect"]

    assert details.value == expected["value"]

    if "variant" in expected:
        assert details.variant == expected["variant"]

    if "errorCode" in expected:
        assert details.error_code == ErrorCode[expected["errorCode"]]
    else:
        assert details.error_code is None


def evaluate(scenario: Mapping[str, Any]) -> FlagEvaluationDetails[Any]:
    client = api.get_client()
    context = evaluation_context(scenario.get("context"))
    flag_key = scenario["flagKey"]
    default = scenario["default"]

    match scenario["type"]:
        case "boolean":
            return client.get_boolean_details(flag_key, default, context)
        case "string":
            return client.get_string_details(flag_key, default, context)
        case "number":
            return client.get_float_details(flag_key, default, context)
        case "object":
            resolution = cast(Any, client.provider).resolve_object_details(
                flag_key,
                default,
                context,
            )
            return resolution.to_flag_evaluation_details(flag_key)
        case flag_type:
            raise AssertionError(f"Unsupported scenario type: {flag_type}")


def evaluation_context(context: Mapping[str, Any] | None) -> EvaluationContext | None:
    if context is None:
        return None

    context = dict(context)
    targeting_key = context.pop("targetingKey", None)
    return EvaluationContext(targeting_key=targeting_key, attributes=context)
