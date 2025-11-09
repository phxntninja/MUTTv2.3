#!/usr/bin/env python3
"""
MUTT v2.5 - Dynamic Read Helpers Unit Tests

Validates that dynamic helper getters fall back to static values when
dynamic config is disabled/unavailable, and respect dynamic overrides when set.
"""

import sys
import os
from types import SimpleNamespace

# Add repository root to path for root module imports
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


import pytest


def test_alerter_dynamic_helpers_fallback(monkeypatch):
    try:
        import alerter_service as alr
    except Exception as e:
        pytest.skip(f"Alerter module not loadable: {e}")

    # Ensure no dynamic config is set
    monkeypatch.setattr(alr, 'DYN_CONFIG', None, raising=False)

    cfg = SimpleNamespace(
        CACHE_RELOAD_INTERVAL=300,
        UNHANDLED_THRESHOLD=100,
        UNHANDLED_EXPIRY_SECONDS=86400,
    )

    assert alr._get_cache_reload_interval(cfg) == 300
    assert alr._get_unhandled_threshold(cfg) == 100
    assert alr._get_unhandled_expiry(cfg) == 86400


def test_alerter_dynamic_helpers_override(monkeypatch):
    try:
        import alerter_service as alr
    except Exception as e:
        pytest.skip(f"Alerter module not loadable: {e}")

    class FakeDyn:
        def __init__(self, mapping):
            self.mapping = mapping

        def get(self, key, default=None):
            return self.mapping.get(key, default)

    fake = FakeDyn({
        'cache_reload_interval': '123',
        'unhandled_threshold': '42',
        'unhandled_expiry_seconds': '3600',
    })
    monkeypatch.setattr(alr, 'DYN_CONFIG', fake, raising=False)

    cfg = SimpleNamespace(
        CACHE_RELOAD_INTERVAL=300,
        UNHANDLED_THRESHOLD=100,
        UNHANDLED_EXPIRY_SECONDS=86400,
    )

    assert alr._get_cache_reload_interval(cfg) == 123
    assert alr._get_unhandled_threshold(cfg) == 42
    assert alr._get_unhandled_expiry(cfg) == 3600


def test_forwarder_dynamic_helpers(monkeypatch):
    try:
        import moog_forwarder_service as mfs
    except Exception as e:
        pytest.skip(f"Forwarder module not loadable: {e}")

    # Fallback first
    monkeypatch.setattr(mfs, 'DYN_CONFIG', None, raising=False)
    cfg = SimpleNamespace(
        MOOG_RATE_LIMIT=50,
        MOOG_RATE_PERIOD=1,
    )
    assert mfs._get_moog_rate_limit(cfg) == 50
    assert mfs._get_moog_rate_period(cfg) == 1

    # Override
    class FakeDyn:
        def __init__(self, mapping):
            self.mapping = mapping

        def get(self, key, default=None):
            return self.mapping.get(key, default)

    fake = FakeDyn({'moog_rate_limit': '200', 'moog_rate_period': '2'})
    monkeypatch.setattr(mfs, 'DYN_CONFIG', fake, raising=False)

    assert mfs._get_moog_rate_limit(cfg) == 200
    assert mfs._get_moog_rate_period(cfg) == 2


def test_invalid_dynamic_values_fallback(monkeypatch):
    # Alerter: invalid dynamic values should fall back to static
    try:
        import alerter_service as alr
    except Exception as e:
        pytest.skip(f"Alerter module not loadable: {e}")

    class FakeDynBad:
        def get(self, key, default=None):
            return 'not-an-int'

    monkeypatch.setattr(alr, 'DYN_CONFIG', FakeDynBad(), raising=False)
    cfg = SimpleNamespace(
        CACHE_RELOAD_INTERVAL=300,
        UNHANDLED_THRESHOLD=100,
        UNHANDLED_EXPIRY_SECONDS=86400,
    )
    assert alr._get_cache_reload_interval(cfg) == 300
    assert alr._get_unhandled_threshold(cfg) == 100
    assert alr._get_unhandled_expiry(cfg) == 86400

    # Forwarder: invalid dynamic values should fall back to static
    try:
        import moog_forwarder_service as mfs
    except Exception as e:
        pytest.skip(f"Forwarder module not loadable: {e}")

    monkeypatch.setattr(mfs, 'DYN_CONFIG', FakeDynBad(), raising=False)
    cfg2 = SimpleNamespace(MOOG_RATE_LIMIT=50, MOOG_RATE_PERIOD=1)
    assert mfs._get_moog_rate_limit(cfg2) == 50
    assert mfs._get_moog_rate_period(cfg2) == 1
