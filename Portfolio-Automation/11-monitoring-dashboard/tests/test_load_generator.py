from fastapi.testclient import TestClient

from demo_app.main import app
from load_generator import run_load


def test_run_load_with_test_transport():
    with TestClient(app, raise_server_exceptions=False) as client:
        summary = run_load(
            base_url="http://testserver",
            items_requests=5,
            process_batches=2,
            rows_per_batch=50,
            with_errors=True,
            with_slow=True,
            client=client,
        )

    assert summary["items_success"] == 5
    assert summary["items_failed"] == 0
    assert summary["process_success"] == 2
    assert summary["total_rows_processed"] == 100
    assert summary["errors_triggered"] == 3
    assert summary["slow_triggered"] == 1
