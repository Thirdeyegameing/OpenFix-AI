from openfix.diagnostics.system import group_process_memory


def test_processes_with_same_name_are_grouped():
    rows = [
        {"name": "chrome.exe", "memory": 100, "pid": 1},
        {"name": "Chrome.exe", "memory": 200, "pid": 2},
        {"name": "other.exe", "memory": 50, "pid": 3},
    ]
    grouped = group_process_memory(rows)
    assert grouped[0]["memory"] == 300
    assert grouped[0]["count"] == 2


def test_process_group_limit_is_applied():
    rows = [{"name": f"p{i}.exe", "memory": i, "pid": i} for i in range(10)]
    assert len(group_process_memory(rows, limit=3)) == 3
