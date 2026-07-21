from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import ErrorCode
from openfeature.flag_evaluation import Reason

from unleash_openfeature_python_provider import UnleashFlagProvider


class FakeUnleashClient:
    def __init__(self) -> None:
        self.context = None
        self.initialize_calls = 0
        self.destroy_calls = 0

    def initialize_client(self, fetch_toggles=True):
        self.initialize_calls += 1

    def destroy(self):
        self.destroy_calls += 1

    def is_enabled(self, feature_name, context=None, fallback_function=None):
        self.context = context
        if feature_name == "enabled":
            return True
        assert fallback_function is not None
        return fallback_function(feature_name, context)

    def get_variant(self, feature_name, context=None):
        self.context = context
        if feature_name == "string":
            return {
                "name": "variant-a",
                "enabled": True,
                "feature_enabled": True,
                "payload": {"type": "string", "value": "hello"},
            }
        if feature_name == "csv":
            return {
                "name": "variant-a",
                "enabled": True,
                "feature_enabled": True,
                "payload": {"type": "csv", "value": "a,b,c"},
            }
        if feature_name == "integer":
            return {
                "name": "variant-a",
                "enabled": True,
                "feature_enabled": True,
                "payload": {"type": "number", "value": "42"},
            }
        if feature_name == "empty-number":
            return {
                "name": "variant-a",
                "enabled": True,
                "feature_enabled": True,
                "payload": {"type": "number", "value": ""},
            }
        if feature_name == "object":
            return {
                "name": "variant-a",
                "enabled": True,
                "feature_enabled": True,
                "payload": {"type": "json", "value": '{"enabled": true}'},
            }
        if feature_name == "array-object":
            return {
                "name": "variant-a",
                "enabled": True,
                "feature_enabled": True,
                "payload": {"type": "json", "value": "[1,2,3]"},
            }
        if feature_name == "invalid-object":
            return {
                "name": "variant-a",
                "enabled": True,
                "feature_enabled": True,
                "payload": {"type": "json", "value": "not json"},
            }
        if feature_name == "scalar-object":
            return {
                "name": "variant-a",
                "enabled": True,
                "feature_enabled": True,
                "payload": {"type": "json", "value": '"not an object"'},
            }
        if feature_name == "wrong-type":
            return {
                "name": "variant-a",
                "enabled": True,
                "feature_enabled": True,
                "payload": {"type": "number", "value": "123"},
            }
        if feature_name == "bad-integer":
            return {
                "name": "variant-a",
                "enabled": True,
                "feature_enabled": True,
                "payload": {"type": "string", "value": "nope"},
            }
        return {"name": "disabled", "enabled": False, "feature_enabled": False}


def _capture_client_options(monkeypatch) -> dict:
    """Spy on the UnleashClient constructor and return the options it's built
    with, without depending on the SDK's internal attributes."""
    import unleash_openfeature_python_provider.provider as provider_module

    captured: dict = {}

    def fake_unleash_client(**kwargs):
        captured.update(kwargs)
        return FakeUnleashClient()

    monkeypatch.setattr(provider_module, "UnleashClient", fake_unleash_client)
    return captured


def test_provider_owns_client_and_stamps_sdk_flavor(monkeypatch) -> None:
    from unleash_openfeature_python_provider import SDK_FLAVOR, SDK_FLAVOR_VERSION

    captured = _capture_client_options(monkeypatch)

    UnleashFlagProvider(
        url="http://localhost:4242/api",
        app_name="test-app",
        disable_metrics=True,
    )

    assert captured["sdk_flavor"] == SDK_FLAVOR
    assert captured["sdk_flavor_version"] == SDK_FLAVOR_VERSION


def test_provider_sdk_flavor_cannot_be_overridden_by_caller(monkeypatch) -> None:
    from unleash_openfeature_python_provider import SDK_FLAVOR

    captured = _capture_client_options(monkeypatch)

    UnleashFlagProvider(
        url="http://localhost:4242/api",
        app_name="test-app",
        disable_metrics=True,
        sdk_flavor="something-else",
    )

    assert captured["sdk_flavor"] == SDK_FLAVOR


def test_resolves_boolean_flag() -> None:
    provider = UnleashFlagProvider._from_client(FakeUnleashClient())

    details = provider.resolve_boolean_details("enabled", False)

    assert details.value is True


def test_initialize_initializes_unleash_client() -> None:
    client = FakeUnleashClient()
    provider = UnleashFlagProvider._from_client(client)

    provider.initialize(EvaluationContext())
    provider.initialize(EvaluationContext())

    assert client.initialize_calls == 2


def test_shutdown_destroys_unleash_client() -> None:
    client = FakeUnleashClient()
    provider = UnleashFlagProvider._from_client(client)

    provider.shutdown()
    provider.shutdown()

    assert client.destroy_calls == 2


def test_passes_targeting_key_as_unleash_user_id() -> None:
    client = FakeUnleashClient()
    provider = UnleashFlagProvider._from_client(client)

    provider.resolve_boolean_details(
        "enabled",
        False,
        EvaluationContext(targeting_key="user-123", attributes={"sessionId": "abc"}),
    )

    assert client.context == {"sessionId": "abc", "userId": "user-123"}


def test_resolves_string_variant_payload() -> None:
    provider = UnleashFlagProvider._from_client(FakeUnleashClient())

    details = provider.resolve_string_details("string", "fallback")

    assert details.value == "hello"
    assert details.variant == "variant-a"


def test_resolves_csv_variant_payload_as_string() -> None:
    provider = UnleashFlagProvider._from_client(FakeUnleashClient())

    details = provider.resolve_string_details("csv", "none")

    assert details.value == "a,b,c"


def test_returns_type_mismatch_for_wrong_string_payload_type() -> None:
    provider = UnleashFlagProvider._from_client(FakeUnleashClient())

    details = provider.resolve_string_details("wrong-type", "fallback")

    assert details.value == "fallback"
    assert details.reason == Reason.ERROR
    assert details.error_code == ErrorCode.TYPE_MISMATCH


def test_resolves_integer_variant_payload() -> None:
    provider = UnleashFlagProvider._from_client(FakeUnleashClient())

    details = provider.resolve_integer_details("integer", 0)

    assert details.value == 42


def test_resolves_object_variant_payload() -> None:
    provider = UnleashFlagProvider._from_client(FakeUnleashClient())

    details = provider.resolve_object_details("object", {})

    assert details.value == {"enabled": True}


def test_resolves_json_array_object_variant_payload() -> None:
    provider = UnleashFlagProvider._from_client(FakeUnleashClient())

    details = provider.resolve_object_details("array-object", [])

    assert details.value == [1, 2, 3]


def test_returns_parse_error_for_invalid_json_object_payload() -> None:
    provider = UnleashFlagProvider._from_client(FakeUnleashClient())

    details = provider.resolve_object_details("invalid-object", {})

    assert details.value == {}
    assert details.reason == Reason.ERROR
    assert details.error_code == ErrorCode.PARSE_ERROR


def test_resolves_json_scalar_object_payload() -> None:
    provider = UnleashFlagProvider._from_client(FakeUnleashClient())

    details = provider.resolve_object_details("scalar-object", {})

    assert details.value == "not an object"
    assert details.reason == Reason.UNKNOWN
    assert details.error_code is None


def test_returns_default_for_disabled_variant() -> None:
    provider = UnleashFlagProvider._from_client(FakeUnleashClient())

    details = provider.resolve_string_details("missing", "fallback")

    assert details.value == "fallback"


def test_returns_type_mismatch_for_unparseable_variant_payload() -> None:
    provider = UnleashFlagProvider._from_client(FakeUnleashClient())

    details = provider.resolve_integer_details("bad-integer", 0)

    assert details.value == 0
    assert details.reason == Reason.ERROR
    assert details.error_code == ErrorCode.TYPE_MISMATCH


def test_returns_parse_error_for_empty_number_payload() -> None:
    provider = UnleashFlagProvider._from_client(FakeUnleashClient())

    details = provider.resolve_float_details("empty-number", 7)

    assert details.value == 7
    assert details.reason == Reason.ERROR
    assert details.error_code == ErrorCode.PARSE_ERROR


def test_metadata_name() -> None:
    provider = UnleashFlagProvider._from_client(FakeUnleashClient())

    assert provider.get_metadata().name == "Unleash OpenFeature Provider"
