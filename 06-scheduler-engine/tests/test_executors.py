from unittest.mock import MagicMock, patch

import httpx

from app.executors.http_executor import execute_http
from app.executors.python_executor import execute_python
from app.executors.shell_executor import execute_shell


def test_http_executor_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "All systems operational"
    mock_resp.reason_phrase = "OK"

    with patch("httpx.Client.request", return_value=mock_resp):
        res = execute_http({"url": "https://httpbin.org/get"}, allow_private=True)
        assert res.status == "SUCCESS"
        assert res.exit_code == 200
        assert "All systems operational" in res.stdout
        assert res.stderr == ""


def test_http_executor_http_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_resp.reason_phrase = "Internal Server Error"

    with patch("httpx.Client.request", return_value=mock_resp):
        res = execute_http({"url": "https://httpbin.org/status/500"}, allow_private=True)
        assert res.status == "FAILED"
        assert res.exit_code == 500
        assert "Internal Server Error" in res.stderr


def test_http_executor_timeout():
    payload = {"url": "https://httpbin.org/delay/10", "timeout": 1}
    with patch("httpx.Client.request", side_effect=httpx.TimeoutException("Timeout")):
        res = execute_http(payload, allow_private=True)
        assert res.status == "FAILED"
        assert res.exit_code == -1
        assert "timed out" in res.stderr.lower()


def test_http_executor_ssrf_protection():
    # Attempting to access private IP when allow_private=False
    res = execute_http({"url": "http://127.0.0.1:8080/test"}, allow_private=False)
    assert res.status == "FAILED"
    assert "SSRF Protection" in res.stderr or "forbidden" in res.stderr.lower()


def test_http_executor_ssrf_allow_override():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "Echo OK"
    mock_resp.reason_phrase = "OK"

    with patch("httpx.Client.request", return_value=mock_resp):
        res = execute_http({"url": "http://127.0.0.1:8080/test"}, allow_private=True)
        assert res.status == "SUCCESS"
        assert res.exit_code == 200


def test_http_executor_invalid_scheme():
    res = execute_http({"url": "ftp://example.com/file.txt"}, allow_private=True)
    assert res.status == "FAILED"
    assert "scheme" in res.stderr.lower()


def test_shell_executor_success():
    res = execute_shell({"command": "demo_success.py", "args": ["param1"]})
    assert res.status == "SUCCESS"
    assert res.exit_code == 0
    assert "Demo task running" in res.stdout


def test_shell_executor_failure():
    res = execute_shell({"command": "demo_failure.py"})
    assert res.status == "FAILED"
    assert res.exit_code != 0
    assert "Simulated error" in res.stderr


def test_shell_executor_path_traversal():
    res = execute_shell({"command": "../../../etc/passwd"})
    assert res.status == "FAILED"
    assert "access denied" in res.stderr.lower() or "not found" in res.stderr.lower()


def test_shell_executor_not_found():
    res = execute_shell({"command": "nonexistent_script_xyz.sh"})
    assert res.status == "FAILED"
    assert "not found" in res.stderr.lower()


def test_python_executor_success():
    res = execute_python({"script": "demo_success.py", "args": ["hello", "world"]})
    assert res.status == "SUCCESS"
    assert res.exit_code == 0
    assert "Demo task running" in res.stdout


def test_python_executor_failure():
    res = execute_python({"script": "demo_failure.py"})
    assert res.status == "FAILED"
    assert res.exit_code == 1
    assert "Simulated error" in res.stderr


def test_python_executor_non_python_file():
    res = execute_python({"script": "backup.sh"})
    assert res.status == "FAILED"
    assert "not a python" in res.stderr.lower()


def test_python_executor_path_traversal():
    res = execute_python({"script": "../conftest.py"})
    assert res.status == "FAILED"
    assert "access denied" in res.stderr.lower() or "not found" in res.stderr.lower()
