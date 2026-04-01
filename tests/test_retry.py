"""Tests for retry module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ollama_router.retry import RetryManager, RetryResult, MAX_RETRIES
from ollama_router.state import KeyState, KeySelector, StateStore
from ollama_router.handler import RateLimitHandler, CooldownInfo
from ollama_router.request_history import RequestHistory


@pytest.fixture
def mock_selector():
    """Create a mock KeySelector."""
    selector = MagicMock(spec=KeySelector)
    selector.keys = [KeyState(key="test-key-12345")]
    return selector


@pytest.fixture
def mock_handler():
    """Create a mock RateLimitHandler."""
    handler = MagicMock(spec=RateLimitHandler)
    handler.detect_cooldown = MagicMock(return_value=None)
    return handler


@pytest.fixture
def mock_state_store():
    """Create a mock StateStore."""
    store = MagicMock(spec=StateStore)
    store.save = MagicMock()
    return store


@pytest.fixture
def mock_history():
    """Create a mock RequestHistory."""
    history = MagicMock(spec=RequestHistory)
    history.add = MagicMock()
    return history


@pytest.fixture
def mock_proxy():
    """Create a mock ProxyClient."""
    proxy = MagicMock()
    proxy.forward = AsyncMock()
    return proxy


@pytest.fixture
def retry_manager(mock_selector, mock_handler, mock_state_store, mock_history):
    """Create a RetryManager with mocked dependencies."""
    return RetryManager(
        selector=mock_selector,
        handler=mock_handler,
        state_store=mock_state_store,
        history=mock_history,
    )


class TestRetryResult:
    """Tests for RetryResult dataclass."""

    def test_retry_result_defaults(self):
        """Test RetryResult with default values."""
        result = RetryResult(response=None, success=True, attempts=1)
        assert result.response is None
        assert result.success is True
        assert result.attempts == 1
        assert result.last_error is None

    def test_retry_result_with_error(self):
        """Test RetryResult with error message."""
        result = RetryResult(
            response=None,
            success=False,
            attempts=3,
            last_error="Network error",
        )
        assert result.last_error == "Network error"


class TestRetryManager:
    """Tests for RetryManager class."""

    @pytest.mark.asyncio
    async def test_successful_request_without_retry(
        self, retry_manager, mock_selector, mock_handler, mock_proxy, mock_history
    ):
        """Test successful request without retry."""
        # Setup
        mock_key_state = KeyState(key="test-key-12345")
        mock_selector.select.return_value = mock_key_state

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_proxy.forward.return_value = mock_response

        mock_handler.detect_cooldown.return_value = None

        # Execute
        result = await retry_manager.execute_with_retry(
            method="POST",
            path="/v1/chat/completions",
            headers={},
            body={"model": "test"},
            proxy=mock_proxy,
            request_id="test-request-id",
        )

        # Verify
        assert result.success is True
        assert result.attempts == 1
        assert result.response == mock_response
        assert result.last_error is None

        mock_proxy.forward.assert_called_once()
        mock_history.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_triggers_retry_with_new_key(
        self, retry_manager, mock_selector, mock_handler, mock_state_store, mock_proxy, mock_history
    ):
        """Test rate limit triggers retry with new key."""
        # Setup - first call returns rate limited, second succeeds
        mock_key_state1 = KeyState(key="test-key-11111")
        mock_key_state2 = KeyState(key="test-key-22222")

        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200

        mock_selector.select.side_effect = [mock_key_state1, mock_key_state2]
        mock_proxy.forward.side_effect = [mock_response_429, mock_response_200]

        # First call detects cooldown, second does not
        cooldown_info = CooldownInfo(hours=4, reason="rate_limit")
        mock_handler.detect_cooldown.side_effect = [cooldown_info, None]

        # Execute
        result = await retry_manager.execute_with_retry(
            method="POST",
            path="/v1/chat/completions",
            headers={},
            body={"model": "test"},
            proxy=mock_proxy,
            request_id="test-request-id",
        )

        # Verify
        assert result.success is True
        assert result.attempts == 2
        assert result.response == mock_response_200

        # Verify cooldown was marked
        mock_selector.mark_cooldown.assert_called_once_with(
            "test-key-11111", 4, "rate_limit"
        )
        mock_state_store.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_keys_exhausted_returns_error(
        self, retry_manager, mock_selector, mock_handler, mock_proxy, mock_history
    ):
        """Test all keys exhausted returns error."""
        # Setup - no keys available
        mock_selector.select.return_value = None

        # Execute
        result = await retry_manager.execute_with_retry(
            method="POST",
            path="/v1/chat/completions",
            headers={},
            body={"model": "test"},
            proxy=mock_proxy,
            request_id="test-request-id",
        )

        # Verify
        assert result.success is False
        assert result.attempts == 0
        assert result.last_error == "No available API keys"
        assert result.response is None

        # Proxy should not be called
        mock_proxy.forward.assert_not_called()

    @pytest.mark.asyncio
    async def test_network_error_returns_error(
        self, retry_manager, mock_selector, mock_handler, mock_proxy, mock_history
    ):
        """Test network error returns error."""
        # Setup
        mock_key_state = KeyState(key="test-key-12345")
        mock_selector.select.return_value = mock_key_state

        mock_proxy.forward.side_effect = Exception("Network connection failed")

        # Execute
        result = await retry_manager.execute_with_retry(
            method="POST",
            path="/v1/chat/completions",
            headers={},
            body={"model": "test"},
            proxy=mock_proxy,
            request_id="test-request-id",
        )

        # Verify
        assert result.success is False
        assert result.attempts == 1
        assert "Network connection failed" in result.last_error
        assert result.response is None

        mock_history.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_on_last_attempt_returns_error(
        self, retry_manager, mock_selector, mock_handler, mock_state_store, mock_proxy, mock_history
    ):
        """Test rate limit on last attempt returns error."""
        # Setup - all calls return rate limited
        mock_key_state = KeyState(key="test-key-12345")
        mock_selector.select.return_value = mock_key_state

        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429

        mock_proxy.forward.return_value = mock_response_429

        cooldown_info = CooldownInfo(hours=4, reason="rate_limit")
        mock_handler.detect_cooldown.return_value = cooldown_info

        # Execute
        result = await retry_manager.execute_with_retry(
            method="POST",
            path="/v1/chat/completions",
            headers={},
            body={"model": "test"},
            proxy=mock_proxy,
            request_id="test-request-id",
        )

        # Verify
        assert result.success is False
        assert result.attempts == MAX_RETRIES
        assert result.last_error == "Rate limited"
        assert result.response == mock_response_429

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(
        self, retry_manager, mock_selector, mock_handler, mock_state_store, mock_proxy, mock_history
    ):
        """Test max retries exhausted scenario."""
        # Setup - all keys get rate limited
        keys = [KeyState(key=f"test-key-{i}") for i in range(MAX_RETRIES)]
        mock_selector.select.side_effect = keys

        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_proxy.forward.return_value = mock_response_429

        cooldown_info = CooldownInfo(hours=4, reason="rate_limit")
        mock_handler.detect_cooldown.return_value = cooldown_info

        # Execute
        result = await retry_manager.execute_with_retry(
            method="POST",
            path="/v1/chat/completions",
            headers={},
            body={"model": "test"},
            proxy=mock_proxy,
            request_id="test-request-id",
        )

        # Verify - should fail after max retries
        assert result.success is False
        assert result.attempts == MAX_RETRIES

    @pytest.mark.asyncio
    async def test_record_request_called_on_success(
        self, retry_manager, mock_selector, mock_handler, mock_proxy, mock_history
    ):
        """Test that request is recorded on success."""
        # Setup
        mock_key_state = KeyState(key="test-key-12345")
        mock_selector.select.return_value = mock_key_state

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_proxy.forward.return_value = mock_response

        mock_handler.detect_cooldown.return_value = None

        # Execute
        await retry_manager.execute_with_retry(
            method="POST",
            path="/v1/chat/completions",
            headers={},
            body={"model": "test"},
            proxy=mock_proxy,
            request_id="test-request-id",
        )

        # Verify history.add was called
        mock_history.add.assert_called_once()
        call_args = mock_history.add.call_args[0][0]
        assert call_args.request_id == "test-request-id"
        assert call_args.method == "POST"
        assert call_args.path == "/v1/chat/completions"
        assert call_args.status_code == 200

    @pytest.mark.asyncio
    async def test_authorization_header_set(
        self, retry_manager, mock_selector, mock_handler, mock_proxy
    ):
        """Test that Authorization header is set correctly."""
        # Setup
        mock_key_state = KeyState(key="sk-test-key-12345")
        mock_selector.select.return_value = mock_key_state

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_proxy.forward.return_value = mock_response

        headers = {}

        # Execute
        await retry_manager.execute_with_retry(
            method="POST",
            path="/v1/chat/completions",
            headers=headers,
            body={"model": "test"},
            proxy=mock_proxy,
            request_id="test-request-id",
        )

        # Verify header was set
        assert headers["Authorization"] == "Bearer sk-test-key-12345"
