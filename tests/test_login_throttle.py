from api.services.login_throttle import LoginAttemptLimiter


def test_limiter_blocks_only_the_client_with_repeated_failures() -> None:
    now = [0.0]
    limiter = LoginAttemptLimiter(clock=lambda: now[0])

    for _ in range(5):
        assert limiter.begin_attempt("203.0.113.10")
        limiter.record_failure("203.0.113.10")

    assert not limiter.begin_attempt("203.0.113.10")
    assert limiter.begin_attempt("203.0.113.11")


def test_limiter_expires_a_lockout_and_resets_the_window() -> None:
    now = [0.0]
    limiter = LoginAttemptLimiter(clock=lambda: now[0], block_seconds=60)
    for _ in range(5):
        assert limiter.begin_attempt("203.0.113.10")
        limiter.record_failure("203.0.113.10")

    assert not limiter.begin_attempt("203.0.113.10")
    now[0] = 60.0
    assert limiter.begin_attempt("203.0.113.10")
    limiter.record_failure("203.0.113.10")
    assert limiter.begin_attempt("203.0.113.10")


def test_limiter_success_clear_removes_only_its_client_record() -> None:
    limiter = LoginAttemptLimiter()
    assert limiter.begin_attempt("203.0.113.10")
    limiter.record_failure("203.0.113.10")
    assert limiter.begin_attempt("203.0.113.11")
    limiter.record_failure("203.0.113.11")

    limiter.clear("203.0.113.10")

    assert limiter.begin_attempt("203.0.113.10")
    for _ in range(4):
        assert limiter.begin_attempt("203.0.113.11")
        limiter.record_failure("203.0.113.11")
    assert not limiter.begin_attempt("203.0.113.11")


def test_limiter_does_not_evict_a_victim_when_capacity_is_full() -> None:
    limiter = LoginAttemptLimiter(max_tracked_clients=1)
    for _ in range(5):
        assert limiter.begin_attempt("203.0.113.10")
        limiter.record_failure("203.0.113.10")

    assert not limiter.begin_attempt("203.0.113.10")
    assert limiter.begin_attempt("203.0.113.11")
    limiter.record_failure("203.0.113.11")
    assert not limiter.begin_attempt("203.0.113.10")


def test_limiter_reserves_in_flight_attempts_to_close_concurrent_bypass() -> None:
    limiter = LoginAttemptLimiter()

    for _ in range(5):
        assert limiter.begin_attempt("203.0.113.10")

    assert not limiter.begin_attempt("203.0.113.10")
    limiter.record_failure("203.0.113.10")
    assert not limiter.begin_attempt("203.0.113.10")


def test_limiter_cancel_releases_an_unfinished_attempt() -> None:
    limiter = LoginAttemptLimiter()

    assert limiter.begin_attempt("203.0.113.10")
    limiter.cancel_attempt("203.0.113.10")

    assert limiter.begin_attempt("203.0.113.10")
