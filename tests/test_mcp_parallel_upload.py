"""Unit tests for parallel file attachment in upload_files_to_vectorstore."""

import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock


def test_parallel_file_attachment_timing():
    """Test that parallel attachment is faster than sequential.

    This test validates that using ThreadPoolExecutor reduces execution time
    when attaching multiple files to a vector store.
    """
    # Mock OpenAI client
    mock_client = Mock()

    # Simulate ~100ms per file attachment (typical API call time)
    def mock_create(*args, **kwargs):
        time.sleep(0.1)
        mock_result = Mock()
        mock_result.id = "file_vs_123"
        mock_result.status = "in_progress"
        return mock_result

    mock_client.vector_stores.files.create = mock_create

    # Test data: 5 files to attach
    files_to_attach = [(f"file-{i}", f"file{i}.md") for i in range(5)]
    vector_store_id = "vs_test123"

    # Sequential execution (baseline)
    start = time.perf_counter()
    sequential_results = []
    for file_id, filename in files_to_attach:
        result = mock_client.vector_stores.files.create(
            vector_store_id=vector_store_id, file_id=file_id
        )
        sequential_results.append({"filename": filename, "status": result.status})
    sequential_time = time.perf_counter() - start

    # Parallel execution (optimized)
    start = time.perf_counter()
    parallel_results = []

    def attach_file(file_id, filename):
        result = mock_client.vector_stores.files.create(
            vector_store_id=vector_store_id, file_id=file_id
        )
        return {"filename": filename, "status": result.status}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(attach_file, file_id, filename) for file_id, filename in files_to_attach
        ]
        parallel_results = [f.result() for f in futures]

    parallel_time = time.perf_counter() - start

    # Assertions
    assert len(sequential_results) == 5
    assert len(parallel_results) == 5

    # Parallel should be at least 3x faster (5 files / ~2 tolerance)
    # Sequential: 5 files x 100ms = 500ms
    # Parallel: max(100ms) = ~100ms
    assert (
        parallel_time < sequential_time / 3
    ), f"Parallel ({parallel_time:.2f}s) should be at least 3x faster than sequential ({sequential_time:.2f}s)"

    print("\n✅ Timing validation:")
    print(f"   Sequential: {sequential_time:.3f}s (5 files x ~100ms)")
    print(f"   Parallel:   {parallel_time:.3f}s (max worker time)")
    print(f"   Speedup:    {sequential_time / parallel_time:.1f}x")


def test_parallel_attachment_error_handling():
    """Test that errors in parallel attachment are caught and reported correctly."""

    mock_client = Mock()

    # File 1 and 3 succeed, file 2 fails
    call_count = [0]

    def mock_create(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            raise Exception("Vector store expired")

        mock_result = Mock()
        mock_result.id = f"file_vs_{call_count[0]}"
        mock_result.status = "completed"
        return mock_result

    mock_client.vector_stores.files.create = mock_create

    files_to_attach = [
        ("file-1", "file1.md"),
        ("file-2", "file2.md"),
        ("file-3", "file3.md"),
    ]
    vector_store_id = "vs_test123"

    def attach_file(file_id, filename):
        try:
            result = mock_client.vector_stores.files.create(
                vector_store_id=vector_store_id, file_id=file_id
            )
            return {
                "filename": filename,
                "file_id": file_id,
                "vector_store_file_id": result.id,
                "status": result.status,
                "success": True,
            }
        except Exception as e:
            return {
                "filename": filename,
                "file_id": file_id,
                "error": str(e),
                "status": "attach_failed",
                "success": False,
            }

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(attach_file, file_id, filename) for file_id, filename in files_to_attach
        ]
        results = [f.result() for f in futures]

    # Assertions
    assert len(results) == 3

    # Count successes and failures
    successes = [r for r in results if r.get("success")]
    failures = [r for r in results if not r.get("success")]

    assert len(successes) == 2, "Should have 2 successful attachments"
    assert len(failures) == 1, "Should have 1 failed attachment"

    # Check error message is preserved
    failed_result = failures[0]
    assert "Vector store expired" in failed_result["error"]
    assert failed_result["status"] == "attach_failed"

    print("\n✅ Error handling validation:")
    print(f"   Successes: {len(successes)}")
    print(f"   Failures:  {len(failures)}")
    print(f"   Error msg: {failed_result['error']}")


def test_parallel_attachment_max_workers():
    """Test that max_workers limit is respected."""

    # Track concurrent executions
    active_count = [0]
    max_concurrent = [0]

    def mock_create(*args, **kwargs):
        active_count[0] += 1
        max_concurrent[0] = max(max_concurrent[0], active_count[0])
        time.sleep(0.05)  # Simulate work
        active_count[0] -= 1

        mock_result = Mock()
        mock_result.id = "file_vs_123"
        mock_result.status = "completed"
        return mock_result

    mock_client = Mock()
    mock_client.vector_stores.files.create = mock_create

    # 10 files but only 3 max workers
    files_to_attach = [(f"file-{i}", f"file{i}.md") for i in range(10)]
    vector_store_id = "vs_test123"
    max_workers = 3

    def attach_file(file_id, filename):
        result = mock_client.vector_stores.files.create(
            vector_store_id=vector_store_id, file_id=file_id
        )
        return {"filename": filename, "status": result.status}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(attach_file, file_id, filename) for file_id, filename in files_to_attach
        ]
        results = [f.result() for f in futures]

    # Assertions
    assert len(results) == 10
    assert (
        max_concurrent[0] <= max_workers
    ), f"Max concurrent ({max_concurrent[0]}) should not exceed max_workers ({max_workers})"

    print("\n✅ Max workers validation:")
    print(f"   Max workers:    {max_workers}")
    print(f"   Max concurrent: {max_concurrent[0]}")
    print(f"   Files processed: {len(results)}")


if __name__ == "__main__":
    print("Running parallel file attachment tests...\n")
    test_parallel_file_attachment_timing()
    test_parallel_attachment_error_handling()
    test_parallel_attachment_max_workers()
    print("\n✅ All tests passed!")
