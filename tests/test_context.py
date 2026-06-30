from datetime import datetime, timezone

from openfeature.evaluation_context import EvaluationContext

from unleash_openfeature_python_provider._context import to_unleash_context


def test_none_context_becomes_empty_unleash_context() -> None:
    assert to_unleash_context(None) == {}


def test_attributes_are_passed_through() -> None:
    context = EvaluationContext(
        attributes={
            "sessionId": "session-123",
            "remoteAddress": "127.0.0.1",
            "plan": "pro",
        }
    )

    assert to_unleash_context(context) == {
        "sessionId": "session-123",
        "remoteAddress": "127.0.0.1",
        "plan": "pro",
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


def test_existing_user_id_takes_precedence_over_targeting_key() -> None:
    context = EvaluationContext(
        targeting_key="targeting-key",
        attributes={"userId": "explicit-user-id"},
    )

    assert to_unleash_context(context) == {"userId": "explicit-user-id"}


def test_does_not_mutate_evaluation_context_attributes() -> None:
    attributes = {"sessionId": "session-123"}
    context = EvaluationContext(targeting_key="user-123", attributes=attributes)

    to_unleash_context(context)

    assert attributes == {"sessionId": "session-123"}


def test_preserves_openfeature_attribute_values() -> None:
    now = datetime(2026, 6, 30, tzinfo=timezone.utc)
    context = EvaluationContext(
        attributes={
            "currentTime": now,
            "properties": {"team": "sdk"},
            "enabled": True,
        }
    )

    assert to_unleash_context(context) == {
        "currentTime": now,
        "properties": {"team": "sdk"},
        "enabled": True,
    }
