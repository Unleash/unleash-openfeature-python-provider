import logging
from datetime import datetime, timezone

from openfeature.evaluation_context import EvaluationContext

from unleash_openfeature_python_provider._context import to_unleash_context


def test_none_context_becomes_empty_unleash_context() -> None:
    assert to_unleash_context(None) is None


def test_base_attributes_stay_at_context_root() -> None:
    now = datetime(2026, 6, 30, tzinfo=timezone.utc)
    context = EvaluationContext(
        attributes={
            "currentTime": now,
            "userId": "user-123",
            "sessionId": "session-123",
            "remoteAddress": "127.0.0.1",
            "environment": "production",
            "appName": "example-app",
        }
    )

    assert to_unleash_context(context) == {
        "currentTime": now,
        "userId": "user-123",
        "sessionId": "session-123",
        "remoteAddress": "127.0.0.1",
        "environment": "production",
        "appName": "example-app",
    }


def test_custom_attributes_move_to_properties() -> None:
    context = EvaluationContext(
        attributes={
            "thing": "test",
            "userId": "7",
            "enabled": True,
            "count": 3,
        }
    )

    assert to_unleash_context(context) == {
        "userId": "7",
        "properties": {
            "thing": "test",
            "enabled": True,
            "count": 3,
        },
    }


def test_targeting_key_becomes_user_id() -> None:
    context = EvaluationContext(
        targeting_key="user-123",
        attributes={"sessionId": "session-123"},
    )

    assert to_unleash_context(context) == {
        "sessionId": "session-123",
        "userId": "user-123",
    }


def test_empty_targeting_key_becomes_user_id() -> None:
    context = EvaluationContext(
        targeting_key="",
        attributes={"userId": "explicit-user-id"},
    )

    assert to_unleash_context(context) == {"userId": ""}


def test_targeting_key_overrides_user_id_attribute() -> None:
    context = EvaluationContext(
        targeting_key="targeting-key",
        attributes={"userId": "explicit-user-id", "plan": "pro"},
    )

    assert to_unleash_context(context) == {
        "userId": "targeting-key",
        "properties": {"plan": "pro"},
    }


def test_does_not_mutate_evaluation_context_attributes() -> None:
    attributes = {"sessionId": "session-123"}
    context = EvaluationContext(targeting_key="user-123", attributes=attributes)

    to_unleash_context(context)

    assert attributes == {"sessionId": "session-123"}


def test_discards_nested_custom_properties(caplog) -> None:
    context = EvaluationContext(
        attributes={
            "team": {"name": "sdk"},
            "groups": ["beta-testers"],
            "plan": "pro",
        }
    )

    with caplog.at_level(logging.DEBUG):
        result = to_unleash_context(context)

    assert result == {"properties": {"plan": "pro"}}
    assert "Discarding nested Unleash context property: team" in caplog.messages
    assert "Discarding nested Unleash context property: groups" in caplog.messages


def test_does_not_emit_empty_properties_after_discarding_nested_values() -> None:
    context = EvaluationContext(attributes={"team": {"name": "sdk"}})

    assert to_unleash_context(context) == {}


def test_base_context_values_can_be_nested_for_unleash_to_normalize() -> None:
    now = datetime(2026, 6, 30, tzinfo=timezone.utc)
    context = EvaluationContext(
        attributes={
            "currentTime": now,
            "userId": 7,
        }
    )

    assert to_unleash_context(context) == {
        "currentTime": now,
        "userId": 7,
    }
