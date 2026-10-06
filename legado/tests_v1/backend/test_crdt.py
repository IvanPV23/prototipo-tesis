from backend.app.crdt.vector_clock import compare, merge


def test_vector_clock_detects_concurrency_and_merges():
    assert compare({"a": 1}, {"b": 1}) == "concurrent"
    assert compare({"a": 1}, {"a": 2}) == "before"
    assert merge({"a": 1}, {"a": 2, "b": 1}) == {"a": 2, "b": 1}


def test_vector_clock_does_not_depend_on_aggregate_ids():
    assert compare({"CLI-A": 1}, {"CLI-B": 1}) == "concurrent"
    assert merge({"CLI-A": 1}, {"CLI-B": 1}) == {"CLI-A": 1, "CLI-B": 1}
