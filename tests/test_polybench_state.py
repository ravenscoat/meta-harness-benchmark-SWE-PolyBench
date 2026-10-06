import sqlite3
from concurrent.futures import ThreadPoolExecutor

from benchmarks.polybench.state import NativeStore
from scripts.hx_console import read_runs


def test_native_state_snapshot_usage_and_cache(tmp_path):
    store = NativeStore(tmp_path / "native", tmp_path / "public")
    run = store.create({"id": "probe"}, {}, "base")
    store.attempt(run["id"], "implement_0", "key")
    store.event(run["id"], "worker.instantiated", "implement_0", {"model": "gpt-6-luna"})
    store.add_usage(run["id"], 123)
    store.save(run["id"], "implement_0", "key", {"ok": True})
    entry = read_runs(tmp_path / "public/state.sqlite3")[0]
    assert entry["run"]["observed_tokens"] == 123
    assert entry["models"]["implement_0"] == "gpt-6-luna"
    assert entry["steps"][0]["status"] == "completed"
    assert store.cached(run["id"], "implement_0", "key") == {"ok": True}
    assert not (tmp_path / "public/state.sqlite3").exists()
    assert sqlite3.connect(store.db).execute("pragma integrity_check").fetchone()[0] == "ok"


def test_console_reads_atomic_snapshots_during_updates(tmp_path):
    store = NativeStore(tmp_path / "native", tmp_path / "public")
    run = store.create({"id": "probe"}, {}, "base")

    def write():
        for _ in range(30):
            store.add_usage(run["id"], 1)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(write)
        for _ in range(60):
            entry = read_runs(tmp_path / "public/state.sqlite3")[0]
            assert 0 <= entry["run"]["observed_tokens"] <= 30
        future.result()
    assert read_runs(tmp_path / "public/state.sqlite3")[0]["run"]["observed_tokens"] == 30


def test_snapshot_publication_does_not_replace_open_reader(tmp_path):
    store = NativeStore(tmp_path / "native", tmp_path / "public")
    run = store.create({"id": "probe"}, {}, "base")
    old = sorted((tmp_path / "public").glob("console-snapshot.*.json"))[-1]
    with old.open("rb") as reader:
        before = reader.read()
        for _ in range(15):
            store.add_usage(run["id"], 1)
        reader.seek(0)
        assert reader.read() == before
        assert read_runs(tmp_path / "public/state.sqlite3")[0]["run"]["observed_tokens"] == 15
