"""Unleash OpenFeature Python provider."""

from ._version import __version__
from .provider import SDK_FLAVOR, SDK_FLAVOR_VERSION, UnleashFlagProvider

# The provider owns the Unleash client and sets SDK_FLAVOR / SDK_FLAVOR_VERSION
__all__ = [
    "UnleashFlagProvider",
    "SDK_FLAVOR",
    "SDK_FLAVOR_VERSION",
    "__version__",
]
