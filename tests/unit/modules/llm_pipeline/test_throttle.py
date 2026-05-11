import time
import uuid

import pytest

from app.modules.llm_pipeline.routers.throttle import (
    InMemoryThrottle,
    ThrottleExceeded,
)


def test_under_limit_allowed():
    t = InMemoryThrottle(max_calls=3, window_seconds=60)
    uid = uuid.uuid4()
    for _ in range(3):
        t.check(uid)


def test_over_limit_raises():
    t = InMemoryThrottle(max_calls=2, window_seconds=60)
    uid = uuid.uuid4()
    t.check(uid)
    t.check(uid)
    with pytest.raises(ThrottleExceeded):
        t.check(uid)


def test_window_expiry_resets(monkeypatch):
    t = InMemoryThrottle(max_calls=1, window_seconds=1)
    uid = uuid.uuid4()
    t.check(uid)
    real_monotonic = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real_monotonic() + 2)
    t.check(uid)  # no raise


def test_separate_users_independent():
    t = InMemoryThrottle(max_calls=1, window_seconds=60)
    a, b = uuid.uuid4(), uuid.uuid4()
    t.check(a)
    t.check(b)  # different user, no raise
    with pytest.raises(ThrottleExceeded):
        t.check(a)


def test_get_throttle_returns_default():
    from app.modules.llm_pipeline.routers.throttle import get_throttle
    t1 = get_throttle()
    t2 = get_throttle()
    assert t1 is t2
    assert t1._max == 10
    assert t1._window == 60
