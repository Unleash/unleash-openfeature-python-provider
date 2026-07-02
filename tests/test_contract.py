from __future__ import annotations

import json
import threading
from collections.abc import Iterator, Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

import pytest
from openfeature import api
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import ErrorCode
from openfeature.flag_evaluation import FlagEvaluationDetails
from UnleashClient import UnleashClient

from unleash_openfeature_python_provider import UnleashFlagProvider

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "verifier" / "contract.json"
FEATURES_PATH = ROOT / "verifier" / "fixtures" / "unleash-features.json"

CAPABILITIES = {"localEval", "perCallContext"}
KNOWN_GAPS = {
    "number-empty-string-guard": (
        "Current provider reports TYPE_MISMATCH for an empty number payload; "
        "contract expects PARSE_ERROR."
    ),
    "object-scalar-json-passthrough": (
        "Current provider rejects scalar JSON object payloads; contract expects "
        "JsonValue passthrough."
    ),
}


class FakeUnleashServer:
    def __init__(self, features: Mapping[str, Any]) -> None:
        self._features = features
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="fake-unleash",
            daemon=True,
        )

    @property
    def url(self) -> str:
        host, port = cast(tuple[str, int], self._server.server_address)
        return f"http://{host}:{port}/api"

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        features = self._features

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path.startswith("/api/client/features"):
                    body = json.dumps(features).encode()
                    self.send_response(HTTPStatus.OK)
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()

            def do_POST(self) -> None:
                if self.path.startswith(
                    (
                        "/api/client/register",
                        "/api/client/metrics",
                    )
                ):
                    self.send_response(HTTPStatus.ACCEPTED)
                    self.end_headers()
                    return

                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()

            def log_message(self, format: str, *args: Any) -> None:
                return

        return Handler


@pytest.fixture(scope="module")
def fake_unleash() -> Iterator[FakeUnleashServer]:
    with FEATURES_PATH.open() as file:
        features = json.load(file)

    server = FakeUnleashServer(features)
    server.start()
    try:
        yield server
    finally:
        server.close()


@pytest.fixture(scope="module", autouse=True)
def openfeature_provider(fake_unleash: FakeUnleashServer) -> Iterator[None]:
    unleash_client = UnleashClient(
        url=fake_unleash.url,
        app_name="openfeature-python-verifier",
        custom_headers={"Authorization": "verifier-not-a-real-token"},
        refresh_interval=60,
        disable_metrics=True,
        disable_registration=True,
    )

    api.set_provider_and_wait(UnleashFlagProvider(cast(Any, unleash_client)))
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
            return client.get_object_details(flag_key, default, context)
        case flag_type:
            raise AssertionError(f"Unsupported scenario type: {flag_type}")


def evaluation_context(context: Mapping[str, Any] | None) -> EvaluationContext | None:
    if context is None:
        return None

    context = dict(context)
    targeting_key = context.pop("targetingKey", None)
    return EvaluationContext(targeting_key=targeting_key, attributes=context)
