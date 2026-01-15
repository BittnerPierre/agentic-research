import json

from evaluations.eval_utils import extract_read_multiple_files_paths


def test_extract_read_multiple_files_paths_collects_unique_paths():
    messages = [
        {
            "type": "function_call",
            "name": "read_multiple_files",
            "arguments": json.dumps({"paths": ["a.txt", "b.txt"]}),
        },
        {
            "type": "function_call",
            "name": "read_multiple_files",
            "arguments": {"paths": ["b.txt", "c.txt"]},
        },
        {
            "type": "function_call",
            "name": "other_tool",
            "arguments": json.dumps({"paths": ["ignored.txt"]}),
        },
    ]

    assert extract_read_multiple_files_paths(messages) == ["a.txt", "b.txt", "c.txt"]


def test_extract_read_multiple_files_paths_handles_single_path_key():
    messages = [
        {
            "type": "function_call",
            "name": "read_multiple_files",
            "arguments": json.dumps({"path": "only.txt"}),
        }
    ]

    assert extract_read_multiple_files_paths(messages) == ["only.txt"]
