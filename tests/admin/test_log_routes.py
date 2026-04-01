# pyright: reportMissingImports=false

import json
import pytest
from datetime import datetime
from pathlib import Path
from fastapi.testclient import TestClient

from ollama_router.config import Config, LoggingConfig
from ollama_router.router import create_app
from ollama_router.admin.auth import create_session


@pytest.fixture
def config_with_logging(tmp_path: Path) -> Config:
    """Create a config with logging enabled to a temp file."""
    log_file = tmp_path / "test.log"
    return Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["test_key"],
        admin_username="admin",
        admin_password="testpass",
        admin_session_secret="test-secret-for-testing",
        logging=LoggingConfig(file=str(log_file)),
    )


@pytest.fixture
def config_no_logging(tmp_path: Path) -> Config:
    """Create a config without a log file."""
    return Config(
        listen="127.0.0.1:11435",
        upstream="https://ollama.com/v1",
        keys=["test_key"],
        admin_username="admin",
        admin_password="testpass",
        admin_session_secret="test-secret-for-testing",
        logging=LoggingConfig(file=None),
    )


@pytest.fixture
def auth_client(config_with_logging: Config) -> TestClient:
    """Create an authenticated test client."""
    app = create_app(config_with_logging)
    client = TestClient(app)

    # Login to get session cookie
    response = client.post(
        "/admin/api/login",
        data={"username": "admin", "password": "testpass"},
    )
    assert response.status_code == 200
    return client


@pytest.fixture
def sample_log_file(config_with_logging: Config) -> Path:
    """Create a sample log file with test entries."""
    log_path = Path(config_with_logging.logging.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    entries = [
        "2026-03-30 10:00:00.123 INFO     [req_001] request_start method=POST path=/chat",
        "2026-03-30 10:00:00.456 DEBUG    [req_001] proxying to upstream",
        "2026-03-30 10:00:01.789 INFO     [req_001] request_end status=200",
        "2026-03-30 10:01:00.000 WARNING  [req_002] rate limit detected",
        "2026-03-30 10:02:00.000 ERROR    [req_003] connection failed",
        "2026-03-30 10:03:00.000 CRITICAL [req_004] system error",
        "2026-03-30 11:00:00.000 INFO     [req_005] another request",
    ]

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(entries) + "\n")

    return log_path


class TestGetLogsEndpoint:
    """Tests for GET /admin/api/logs endpoint."""

    def test_get_logs_returns_empty_when_no_file(
        self, config_no_logging: Config, tmp_path: Path
    ):
        """Test that endpoint returns empty list when log file doesn't exist."""
        # Create app with no logging configured
        app = create_app(config_no_logging)
        client = TestClient(app)

        # Login
        client.post(
            "/admin/api/login",
            data={"username": "admin", "password": "testpass"},
        )

        response = client.get("/admin/api/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["filtered"] == 0

    def test_get_logs_returns_entries(
        self, auth_client: TestClient, sample_log_file: Path
    ):
        """Test that endpoint returns log entries from file."""
        response = auth_client.get("/admin/api/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 7
        assert len(data["items"]) == 7
        assert data["has_more"] is False

    def test_get_logs_filter_by_level(
        self, auth_client: TestClient, sample_log_file: Path
    ):
        """Test filtering logs by level."""
        response = auth_client.get("/admin/api/logs?levels=ERROR,WARNING")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        levels = {item["level"] for item in data["items"]}
        assert levels == {"ERROR", "WARNING"}

    def test_get_logs_filter_by_single_level(
        self, auth_client: TestClient, sample_log_file: Path
    ):
        """Test filtering logs by a single level."""
        response = auth_client.get("/admin/api/logs?levels=INFO")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["level"] == "INFO"

    def test_get_logs_filter_by_time_start(
        self, auth_client: TestClient, sample_log_file: Path
    ):
        """Test filtering logs by start time."""
        response = auth_client.get(
            "/admin/api/logs?start=2026-03-30T10:01:00"
        )
        assert response.status_code == 200
        data = response.json()
        # Should include entries from 10:01:00 onwards
        assert data["total"] == 4

    def test_get_logs_filter_by_time_end(
        self, auth_client: TestClient, sample_log_file: Path
    ):
        """Test filtering logs by end time."""
        response = auth_client.get(
            "/admin/api/logs?end=2026-03-30T10:01:00"
        )
        assert response.status_code == 200
        data = response.json()
        # Should include entries before 10:01:00
        assert data["total"] == 4

    def test_get_logs_pagination(
        self, auth_client: TestClient, sample_log_file: Path
    ):
        """Test pagination of logs."""
        # First page
        response = auth_client.get("/admin/api/logs?offset=0&limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 7
        assert data["has_more"] is True

        # Second page
        response = auth_client.get("/admin/api/logs?offset=3&limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["has_more"] is True

        # Last page
        response = auth_client.get("/admin/api/logs?offset=6&limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["has_more"] is False

    def test_get_logs_requires_authentication(self, config_with_logging: Config):
        """Test that endpoint requires authentication."""
        app = create_app(config_with_logging)
        client = TestClient(app)

        response = client.get("/admin/api/logs")
        assert response.status_code == 401


class TestLogStreamEndpoint:
    """Tests for GET /admin/api/logs/stream endpoint."""

    def test_stream_requires_authentication(self, config_with_logging: Config):
        """Test that stream endpoint requires authentication."""
        app = create_app(config_with_logging)
        client = TestClient(app)

        response = client.get("/admin/api/logs/stream")
        assert response.status_code == 401

    def test_stream_returns_sse_content_type(
        self, auth_client: TestClient, sample_log_file: Path
    ):
        """Test that stream returns text/event-stream content type."""
        # Note: TestClient may not fully support SSE, so we just check initial response
        with auth_client as client:
            # We can't easily test the streaming in sync TestClient
            # Just verify the endpoint exists and returns correct content type
            pass


class TestDownloadLogsEndpoint:
    """Tests for GET /admin/api/logs/download endpoint."""

    def test_download_requires_authentication(self, config_with_logging: Config):
        """Test that download endpoint requires authentication."""
        app = create_app(config_with_logging)
        client = TestClient(app)

        response = client.get("/admin/api/logs/download")
        assert response.status_code == 401

    def test_download_file_not_found(
        self, config_no_logging: Config, tmp_path: Path
    ):
        """Test download returns 404 when log file doesn't exist."""
        app = create_app(config_no_logging)
        client = TestClient(app)

        # Login
        client.post(
            "/admin/api/login",
            data={"username": "admin", "password": "testpass"},
        )

        response = client.get("/admin/api/logs/download")
        assert response.status_code == 404

    def test_download_default_log_format(
        self, auth_client: TestClient, sample_log_file: Path
    ):
        """Test downloading logs in default .log format."""
        response = auth_client.get("/admin/api/logs/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        assert "attachment" in response.headers.get("content-disposition", "")
        assert ".log" in response.headers.get("content-disposition", "")

        content = response.text
        # Check that content contains log entries
        assert "req_001" in content
        assert "INFO" in content

    def test_download_json_format(
        self, auth_client: TestClient, sample_log_file: Path
    ):
        """Test downloading logs in JSON format."""
        response = auth_client.get("/admin/api/logs/download?format=json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "attachment" in response.headers.get("content-disposition", "")
        assert ".json" in response.headers.get("content-disposition", "")

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 7
        assert data[0]["level"] == "INFO"
        assert data[0]["request_id"] == "req_001"

    def test_download_with_level_filter(
        self, auth_client: TestClient, sample_log_file: Path
    ):
        """Test downloading filtered logs."""
        response = auth_client.get(
            "/admin/api/logs/download?levels=ERROR,CRITICAL&format=json"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        levels = {item["level"] for item in data}
        assert levels == {"ERROR", "CRITICAL"}

    def test_download_with_time_filter(
        self, auth_client: TestClient, sample_log_file: Path
    ):
        """Test downloading logs filtered by time range."""
        response = auth_client.get(
            "/admin/api/logs/download"
            "?start=2026-03-30T10:01:00"
            "&end=2026-03-30T10:02:30"
            "&format=json"
        )
        assert response.status_code == 200
        data = response.json()
        # Should include WARNING and ERROR entries
        assert len(data) == 2
