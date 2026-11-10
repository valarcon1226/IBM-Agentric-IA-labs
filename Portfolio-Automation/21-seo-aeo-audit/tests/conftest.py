"""Pytest fixtures and local test server."""

import threading
from collections.abc import Generator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

FIXTURES_PATH = Path(__file__).parent / "fixtures"
MOCK_SITE_PATH = FIXTURES_PATH / "mock_site"


class MockSiteHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler serving mock site files with intentional 404s."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(MOCK_SITE_PATH), **kwargs)

    def do_GET(self):
        # Specific test endpoints
        if self.path in ("/broken-404", "/enlace-roto-404", "/error-404"):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not Found - Enlace Roto de Prueba")
            return

        if self.path == "/":
            self.path = "/index.html"

        return super().do_GET()

    def log_message(self, format, *args):
        # Suppress test server console logs
        pass


@pytest.fixture(scope="session")
def mock_server() -> Generator[str, None, None]:
    """Start local test server serving mock site fixtures."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockSiteHandler)
    host, port = server.server_address
    base_url = f"http://127.0.0.1:{port}"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield base_url

    server.shutdown()
    server.server_close()


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to fixtures directory."""
    return FIXTURES_PATH


@pytest.fixture
def perfect_html(fixtures_dir: Path) -> str:
    """Return HTML content of perfect.html fixture."""
    return (fixtures_dir / "perfect.html").read_text(encoding="utf-8")


@pytest.fixture
def broken_seo_html(fixtures_dir: Path) -> str:
    """Return HTML content of broken_seo.html fixture."""
    return (fixtures_dir / "broken_seo.html").read_text(encoding="utf-8")


@pytest.fixture
def broken_aeo_html(fixtures_dir: Path) -> str:
    """Return HTML content of broken_aeo.html fixture."""
    return (fixtures_dir / "broken_aeo.html").read_text(encoding="utf-8")
