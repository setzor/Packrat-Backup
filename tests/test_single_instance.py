import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtNetwork import QLocalSocket  # noqa: E402

from packrat.single_instance import SingleInstance, default_key  # noqa: E402

KEY = default_key()


@pytest.fixture()
def first_instance(qapp):
    guard = SingleInstance(key=KEY)
    assert guard.acquire()
    yield guard
    guard.release()


def test_acquire_and_second_fails(first_instance):
    second = SingleInstance(key=KEY)
    try:
        assert not second.acquire()
    finally:
        second.release()


def test_release_allows_new_owner(first_instance):
    first_instance.release()
    second = SingleInstance(key=KEY)
    try:
        assert second.acquire()
    finally:
        second.release()


def test_notify_running_triggers_callback(qapp, first_instance):
    fired = []
    first_instance._on_activate = lambda: fired.append(True)

    assert first_instance.notify_running()

    deadline = 20
    for _ in range(deadline):
        qapp.processEvents()
        if fired:
            break
    assert fired


def test_notify_running_fails_when_no_owner(qapp):
    guard = SingleInstance(key="packrat-test-no-such-server")
    assert not guard.notify_running()
