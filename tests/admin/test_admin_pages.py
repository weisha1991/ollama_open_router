from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from ollama_router.config import Config
from ollama_router.request_history import RequestRecord
from ollama_router.router import create_app


def _make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        Config(
            listen="127.0.0.1:11435",
            upstream="https://ollama.com/v1",
            keys=["test_key"],
            admin_username="admin",
            admin_password="testpass",
            admin_session_secret="test-secret",
        ),
        state_dir=str(tmp_path),
    )
    return TestClient(app)


def _login(client: TestClient) -> None:
    response = client.post(
        "/admin/api/login",
        data={"username": "admin", "password": "testpass"},
    )
    assert response.status_code == 200


def test_login_page_renders_brand_shell(tmp_path: Path):
    client = _make_client(tmp_path)

    response = client.get("/admin/login")

    assert response.status_code == 200
    html = response.text
    assert "Ollama Router" in html
    assert "Sign in" in html
    assert "admin-login-shell" in html


def test_dashboard_page_renders_new_shell_after_auth(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/dashboard")

    assert response.status_code == 200
    html = response.text
    assert "admin-shell" in html
    assert "admin-page-header-compact" in html
    assert "admin-content-dense" in html
    assert "Dashboard" in html
    assert "/admin/keys" in html
    assert "/admin/logs" in html


def test_dashboard_fragment_renders_cards_and_panels(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/api/stats/panel")

    assert response.status_code == 200
    html = response.text
    assert "admin-dashboard-primary" in html
    assert "admin-kpi-secondary" in html
    assert "Total Keys" in html
    assert "Available Keys" in html
    assert "Cooldown Keys" in html
    assert "Total Requests" in html
    assert "Request Overview" in html
    assert "Key Status Distribution" in html
    assert "Recent Keys" in html
    assert "Recent Activity" in html


def test_dashboard_fragment_shows_collecting_message_for_single_request(
    tmp_path: Path,
):
    client = _make_client(tmp_path)
    _login(client)
    client.app.state.request_history.add(
        RequestRecord(
            timestamp=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
            request_id="req-single-panel",
            method="POST",
            path="/v1/chat/completions",
            status_code=200,
            key_id="key-a",
            latency_ms=120.0,
        )
    )

    response = client.get("/admin/api/stats/panel")

    assert response.status_code == 200
    assert "Collecting a fuller history" in response.text


def test_keys_page_renders_summary_and_action_shell(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/keys")

    assert response.status_code == 200
    html = response.text
    assert "admin-page-intro-compact" in html
    assert "admin-table-dense" in html
    assert "Key Inventory" in html
    assert "Add API Key" in html
    assert "Key ID" in html


def test_history_page_renders_monitoring_summary(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/history")

    assert response.status_code == 200
    html = response.text
    assert "admin-page-intro-compact" in html
    assert "admin-table-dense" in html
    assert "Request History" in html
    assert "Recent Traffic" in html
    assert "Latency" in html


def test_logs_page_renders_segmented_monitoring_layout(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)

    response = client.get("/admin/logs")

    assert response.status_code == 200
    html = response.text
    assert "admin-tab-strip" in html
    assert "admin-console-frame" in html
    assert "Historical Logs" in html
    assert "Realtime Logs" in html
    assert "log-console-shell" in html


def test_admin_json_stats_handles_request_history_object(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)
    client.app.state.request_history.add(
        RequestRecord(
            timestamp=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
            request_id="req-json-stats",
            method="POST",
            path="/v1/chat/completions",
            status_code=200,
            key_id="key-a",
            latency_ms=120.0,
        )
    )

    response = client.get("/admin/api/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["history_size"] == 1
    assert data["average_latency_ms"] == 120.0
    assert data["requests_by_status"] == {"200": 1}
    assert data["requests_by_key"] == {"key-a": 1}


def test_admin_json_history_handles_request_history_object(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)
    client.app.state.request_history.add(
        RequestRecord(
            timestamp=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
            request_id="req-json-history",
            method="GET",
            path="/v1/models",
            status_code=200,
            key_id="key-b",
            latency_ms=42.5,
        )
    )

    response = client.get("/admin/api/history")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["request_id"] == "req-json-history"
    assert data["items"][0]["status_code"] == 200
    assert data["items"][0]["latency_ms"] == 42.5
