"""Per-thread Daytona cache cleanup regression tests (scope=thread leak)."""

from deepsupport_os.harness import daytona_backend as db


def test_clear_thread_backends_drops_daytona_thread_caches():
    # Simulate a thread that acquired a dedicated Daytona sandbox reference.
    db._thread_backends["tid-x:daytona"] = object()
    db._daytona_by_thread["tid-x"] = object()
    db._sandbox_by_thread["tid-x"] = object()

    db.clear_thread_backends("tid-x")

    assert "tid-x:daytona" not in db._thread_backends
    assert "tid-x" not in db._daytona_by_thread
    assert "tid-x" not in db._sandbox_by_thread


def test_clear_thread_backends_all_prunes_everything():
    db._thread_backends["tid-a:local"] = object()
    db._daytona_by_thread["tid-a"] = object()
    db._sandbox_by_thread["tid-a"] = object()
    db._daytona_by_thread["tid-b"] = object()

    db.clear_thread_backends()

    assert not db._thread_backends
    assert not db._daytona_by_thread
    assert not db._sandbox_by_thread


def test_clear_thread_backends_keeps_other_threads():
    db._daytona_by_thread["keep-me"] = object()
    db._daytona_by_thread["remove-me"] = object()

    db.clear_thread_backends("remove-me")

    assert "keep-me" in db._daytona_by_thread
    assert "remove-me" not in db._daytona_by_thread
    db._daytona_by_thread.clear()