from __future__ import annotations

from ensemble.semantic import rank_symbol_records


def test_rank_symbol_records_prefers_task_matches() -> None:
    symbols = [
        {
            "id": "1",
            "file_path": "src/util.py",
            "name": "helper",
            "qualified_name": "helper",
            "start_line": 1,
        },
        {
            "id": "2",
            "file_path": "src/auth.py",
            "name": "login_timeout",
            "qualified_name": "Auth.login_timeout",
            "start_line": 2,
        },
    ]

    ranked = rank_symbol_records("fix auth timeout", symbols)
    assert ranked[0]["id"] == "2"


def test_rank_symbol_records_is_deterministic_without_matches() -> None:
    symbols = [
        {
            "id": "2",
            "file_path": "z.py",
            "name": "z",
            "qualified_name": "z",
            "start_line": 2,
        },
        {
            "id": "1",
            "file_path": "a.py",
            "name": "a",
            "qualified_name": "a",
            "start_line": 1,
        },
    ]

    ranked = rank_symbol_records("unrelated", symbols)
    assert [item["id"] for item in ranked] == ["1", "2"]
