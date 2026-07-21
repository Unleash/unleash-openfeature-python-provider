from __future__ import annotations

import argparse

from openfeature import api
from openfeature.evaluation_context import EvaluationContext

from unleash_openfeature_python_provider import UnleashFlagProvider


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve a boolean feature flag through OpenFeature and Unleash."
    )
    parser.add_argument("--url", required=True, help="Unleash API URL")
    parser.add_argument("--api-key", required=True, help="Unleash client API key")
    parser.add_argument("--flag-key", required=True, help="Feature flag key")
    parser.add_argument("--app-name", default="openfeature-example")
    parser.add_argument("--targeting-key", help="Optional OpenFeature targeting key")
    parser.add_argument("--default", action="store_true", help="Default flag value")
    args = parser.parse_args()

    # It builds and owns the Unleash client. Pass the same options for UnleashClient, 
    # the provider stamps its SDK-flavor on top.
    provider = UnleashFlagProvider(
        url=args.url,
        app_name=args.app_name,
        custom_headers={"Authorization": args.api_key},
    )
    api.set_provider_and_wait(provider)

    evaluation_context = (
        EvaluationContext(targeting_key=args.targeting_key)
        if args.targeting_key is not None
        else None
    )

    client = api.get_client()
    details = client.get_boolean_details(
        args.flag_key,
        args.default,
        evaluation_context,
    )

    print(f"{details.flag_key}={details.value}")
    print(f"reason={details.reason}")

    if details.error_code is not None:
        print(f"error_code={details.error_code}")
    if details.error_message is not None:
        print(f"error_message={details.error_message}")


if __name__ == "__main__":
    main()
