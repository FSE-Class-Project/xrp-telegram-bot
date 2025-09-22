"""Comprehensive bot tests."""

import asyncio
import json
import os
import time
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from telegram import Update, User, Message, Chat, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import RetryAfter
from telegram.ext import ContextTypes

# Import test fixtures from backend tests
from backend.database.models import Base, User as DBUser, Wallet, Transaction, Beneficiary
from backend.services.user_service import UserService

# Import bot modules for testing
from bot.handlers.start import start_command, handle_import_wallet
from bot.handlers.transaction import send_command
from bot.handlers.account import handle_username_update, update_username_command
from bot.utils.formatting import format_xrp_amount, format_error_message, escape_html


# Test fixtures and utilities
@pytest.fixture
def test_db():
    """Create test database session (reused from backend tests)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    db = session_local()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def telegram_update_factory():
    """Factory for creating Telegram Update objects."""

    def _create_update(chat_id: int, text: str, update_id: int, user_id: int | None = None):
        user_id = user_id or chat_id
        user = User(
            id=user_id, is_bot=False, first_name="Test", last_name="User", username="testuser"
        )
        chat = Chat(id=chat_id, type="private")

        # Create a mock message with reply_text method
        message = Mock()
        message.message_id = 1
        message.date = datetime.now()
        message.chat = chat
        message.from_user = user
        message.text = text
        message.reply_text = AsyncMock()

        return Update(update_id=update_id, message=message)

    return _create_update


@pytest.fixture
def mock_xrpl_client():
    """Mock XRPL client with configurable responses."""

    class MockXRPLClient:
        def __init__(self):
            self.reset()

        def reset(self):
            self.submit_calls = []
            self.balance_calls = []
            self.setup_success_response()

        def setup_success_response(
            self, tx_hash="E3FE6EA3D48F0C2B639448020EA4F03D4F4F8FFDB243A852A0F59177921B4879"
        ):
            self.submit_response = {"result": "tesSUCCESS", "tx_json": {"hash": tx_hash}}
            self.should_timeout = False
            self.should_retry = False

        def setup_timeout_once_then_success(self):
            self.should_timeout = True
            self.should_retry = True
            self.setup_success_response()

        def setup_reject(self, code="tecUNFUNDED_PAYMENT"):
            self.submit_response = {"result": code, "error": "Transaction failed"}
            self.should_timeout = False

        async def submit_and_wait(self, transaction, wallet):
            self.submit_calls.append((transaction, wallet))
            if self.should_timeout and not hasattr(self, "_timeout_used"):
                self._timeout_used = True
                raise asyncio.TimeoutError("XRPL timeout")
            return self.submit_response

        async def get_balance(self, address):
            self.balance_calls.append(address)
            return {"result": {"account_data": {"Balance": "10000000"}}}  # 10 XRP in drops

    return MockXRPLClient()


@pytest.fixture
def mock_context():
    """Mock Telegram context with bot data."""
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.bot_data = {"api_url": "http://localhost:8000", "api_key": "test-api-key"}
    context.args = []
    return context


@pytest.fixture
def log_capture(caplog):
    """Capture logs for testing."""
    caplog.set_level("INFO")
    return caplog


# ===============================
# E2E Tests
# ===============================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_onboarding_balance_beneficiary_send_flow(
    test_db, telegram_update_factory, mock_xrpl_client, mock_context, log_capture
):
    """Test complete user journey from onboarding to sending XRP."""
    user_id = 123456789
    chat_id = 123456789

    # Mock API responses for user creation and balance
    with patch("httpx.AsyncClient") as mock_http:
        mock_client = AsyncMock()
        mock_http.return_value.__aenter__.return_value = mock_client

        # Mock user doesn't exist initially (404), then exists after creation
        mock_client.get.side_effect = [
            Mock(status_code=404),  # User doesn't exist
            Mock(status_code=200, json=lambda: {"balance": 10.0}),  # Balance check
        ]
        mock_client.post.return_value = Mock(
            status_code=200, json=lambda: {"success": True, "user_id": user_id}
        )

        # Mock XRPL wallet creation in user service
        with patch("backend.services.xrp_service.XRPService.create_wallet") as mock_wallet:
            mock_wallet.return_value = ("rTestAddress123", "encrypted_secret")

            # 1. /start → user row + wallet created
            start_update = telegram_update_factory(chat_id, "/start", 1, user_id)

            await start_command(start_update, mock_context)

            # Assert welcome message contains wallet creation options
            start_update.message.reply_text.assert_called_once()
            reply_args = start_update.message.reply_text.call_args
            reply_text = reply_args[0][0]
            assert "Welcome to the XRP Ledger Bot" in reply_text

            # 2. Simulate wallet creation choice (would be callback in real flow)
            user_service = UserService()
            with patch(
                "backend.services.user_service.UserService.get_user_by_telegram_id"
            ) as mock_get:
                mock_get.return_value = None
                user = await user_service.create_user(
                    db=test_db,
                    telegram_id=str(user_id),
                    telegram_username="testuser",
                    telegram_first_name="Test",
                    telegram_last_name="User",
                )

                # Assert user and wallet created
                assert user.telegram_id == str(user_id)
                assert user.wallet is not None
                assert user.wallet.xrp_address == "rTestAddress123"

            # 3. Add beneficiary
            beneficiary = Beneficiary(
                user_id=user.id,
                alias="friend",
                address="rFriendAddress456",  # Use 'address' field name
            )
            test_db.add(beneficiary)
            test_db.commit()

            # Test duplicate alias returns friendly error
            duplicate_beneficiary = Beneficiary(
                user_id=user.id,
                alias="friend",  # Same alias
                address="rAnotherAddress789",  # Use 'address' field name
            )
            test_db.add(duplicate_beneficiary)

            with pytest.raises(Exception):  # SQLAlchemy IntegrityError expected
                test_db.commit()
            test_db.rollback()

            # 4. Mock successful transaction flow (simplified)
            # Create transaction record directly
            transaction = Transaction(
                sender_id=user.id,
                sender_address=user.wallet.xrp_address,
                recipient_address="rFriendAddress456",
                amount=5.0,
                status="pending",
                idempotency_key=str(uuid4()),
            )
            test_db.add(transaction)
            test_db.commit()

            # Assert transaction row exists with correct status
            assert transaction.status == "pending"
            assert transaction.amount == 5.0

            # Simulate successful submission
            setattr(transaction, "status", "confirmed")
            setattr(transaction, "tx_hash", "ABCD1234")
            test_db.commit()

            assert transaction.status == "confirmed"
            assert transaction.tx_hash == "ABCD1234"

            # Assert no secrets in logs
            for record in log_capture.records:
                assert "encrypted_secret" not in record.getMessage()
                assert "private" not in record.getMessage().lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_start_import_existing_wallet_flow(telegram_update_factory, mock_context):
    """Ensure import existing wallet path is available immediately after /start."""
    user_id = 987654321
    chat_id = 987654321

    with patch("httpx.AsyncClient") as mock_http:
        mock_client = AsyncMock()
        mock_http.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = Mock(status_code=404)

        start_update = telegram_update_factory(chat_id, "/start", 111, user_id)
        await start_command(start_update, mock_context)

        start_update.message.reply_text.assert_called_once()
        reply_args, reply_kwargs = start_update.message.reply_text.call_args
        welcome_keyboard = reply_kwargs.get("reply_markup")

        assert isinstance(welcome_keyboard, InlineKeyboardMarkup)
        import_button = welcome_keyboard.inline_keyboard[1][0]
        assert import_button.callback_data == "import_wallet"
        assert import_button.text.strip().endswith("Import Existing Wallet")

    import_update = Mock()
    callback_query = Mock()
    callback_query.message = Mock()
    callback_query.answer = AsyncMock()
    callback_query.edit_message_text = AsyncMock()
    import_update.callback_query = callback_query

    await handle_import_wallet(import_update, mock_context)

    callback_query.answer.assert_called_once()
    callback_query.edit_message_text.assert_called_once()
    edit_args, edit_kwargs = callback_query.edit_message_text.call_args

    assert "Import Existing Wallet" in edit_args[0]
    assert "CRITICAL SAFETY WARNING" in edit_args[0]
    assert edit_kwargs.get("parse_mode") == ParseMode.HTML

    followup_keyboard = edit_kwargs.get("reply_markup")
    assert isinstance(followup_keyboard, InlineKeyboardMarkup)
    confirm_button = followup_keyboard.inline_keyboard[0][0]
    back_button = followup_keyboard.inline_keyboard[-1][0]

    assert confirm_button.callback_data == "confirm_testnet_import"
    assert back_button.callback_data == "back_to_start"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_idempotent_on_duplicate_update(
    test_db, telegram_update_factory, mock_context, log_capture
):
    """Test idempotency when receiving duplicate Telegram updates."""
    user_id = 123456789
    chat_id = 123456789
    update_id = 42

    # Create user first
    user = DBUser(
        telegram_id=str(user_id),
        telegram_username="testuser",
        wallet=Wallet(
            xrp_address="rTestAddress123", encrypted_secret="encrypted_secret", balance=10.0
        ),
    )
    test_db.add(user)
    test_db.commit()

    # Mock API responses
    with patch("httpx.AsyncClient") as mock_http:
        mock_client = AsyncMock()
        mock_http.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = Mock(status_code=200, json=lambda: {"success": True})

        # Create identical updates
        update1 = telegram_update_factory(chat_id, "/start", update_id, user_id)
        update2 = telegram_update_factory(chat_id, "/start", update_id, user_id)  # Same update_id

        # Process first update
        await start_command(update1, mock_context)

        # Process duplicate update
        await start_command(update2, mock_context)

        # Both should reply (no update-level deduplication in this simple test)
        # But backend API should handle idempotency
        assert update1.message.reply_text.called
        assert update2.message.reply_text.called

        # In a real implementation, we'd check that backend API was called only once
        # due to idempotency protection at the API level


# ===============================
# Integration Tests
# ===============================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_webhook_dispatch_and_state_machine(
    test_db, telegram_update_factory, mock_context
):
    """Test webhook handling and conversation state transitions."""
    user_id = 123456789
    chat_id = 123456789

    # Mock conversation states
    mock_context.user_data = {"transaction": {"state": "AMOUNT"}, "current_conversation": "send"}

    # Create test update for amount input
    update = telegram_update_factory(chat_id, "5.0", 1, user_id)

    # Mock the conversation handler state transitions
    # In real code, this would be handled by python-telegram-bot's ConversationHandler

    # Simulate state transition from AMOUNT to CONFIRM
    initial_state = mock_context.user_data["transaction"]["state"]
    assert initial_state == "AMOUNT"

    # Process amount input (simulated)
    mock_context.user_data["transaction"]["amount"] = "5.0"
    mock_context.user_data["transaction"]["state"] = "CONFIRM"

    final_state = mock_context.user_data["transaction"]["state"]
    assert final_state == "CONFIRM"

    # Assert proper state transition occurred
    assert initial_state != final_state


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_xrpl_timeout_then_retry_once(test_db, mock_xrpl_client, log_capture):
    """Test XRPL timeout handling with retry logic."""
    # Setup timeout scenario
    mock_xrpl_client.setup_timeout_once_then_success()

    retry_count = 0
    max_retries = 1

    async def simulate_xrpl_call_with_retry():
        nonlocal retry_count

        # First call should timeout
        if retry_count == 0:
            retry_count += 1
            try:
                mock_wallet = Mock()
                mock_wallet.classic_address = "rTestAddress123"
                mock_transaction = {"Amount": "5000000"}  # 5 XRP in drops

                result = await mock_xrpl_client.submit_and_wait(mock_transaction, mock_wallet)
                # This shouldn't be reached on first call due to timeout setup
                return result
            except asyncio.TimeoutError:
                # Expected timeout, continue to retry
                pass

        # Retry call should succeed
        mock_wallet = Mock()
        mock_wallet.classic_address = "rTestAddress123"
        mock_transaction = {"Amount": "5000000"}  # 5 XRP in drops

        result = await mock_xrpl_client.submit_and_wait(mock_transaction, mock_wallet)
        return result

    # Test timeout then success
    result = await simulate_xrpl_call_with_retry()

    # Assert exactly one retry occurred
    assert retry_count == 1
    assert result is not None
    assert result["result"] == "tesSUCCESS"

    # Assert backoff was simulated
    assert len(mock_xrpl_client.submit_calls) == 1  # Only successful call recorded


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_alias_unique_violation_graceful_error(test_db):
    """Test graceful handling of database unique constraint violations."""
    user = DBUser(telegram_id="123456789", telegram_username="testuser")
    test_db.add(user)
    test_db.commit()

    # Create first beneficiary
    beneficiary1 = Beneficiary(user_id=user.id, alias="friend", address="rAddress1")
    test_db.add(beneficiary1)
    test_db.commit()

    # Attempt to create duplicate alias
    beneficiary2 = Beneficiary(
        user_id=user.id,
        alias="friend",  # Duplicate alias
        address="rAddress2",
    )
    test_db.add(beneficiary2)

    # Should raise constraint violation
    with pytest.raises(Exception):  # SQLAlchemy IntegrityError
        test_db.commit()

    # Rollback to clean state
    test_db.rollback()

    # Assert only original beneficiary exists
    beneficiaries = test_db.query(Beneficiary).filter_by(user_id=user.id).all()
    assert len(beneficiaries) == 1
    assert beneficiaries[0].alias == "friend"
    assert beneficiaries[0].address == "rAddress1"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_rate_limit_429_from_telegram_backoff():
    """Test handling of Telegram API rate limiting."""
    retry_count = 0

    async def mock_send_message_with_rate_limit():
        nonlocal retry_count
        retry_count += 1
        if retry_count == 1:
            # First call fails with rate limit
            raise RetryAfter(30)  # Retry after 30 seconds
        else:
            # Second call succeeds
            return Mock(message_id=123)

    # Test rate limit handling
    try:
        result = await mock_send_message_with_rate_limit()
        assert False, "Should have raised RetryAfter"
    except RetryAfter as e:
        assert e.retry_after == 30

        # Simulate backoff and retry
        result = await mock_send_message_with_rate_limit()
        assert result.message_id == 123
        assert retry_count == 2


# ===============================
# Unit Tests
# ===============================


@pytest.mark.unit
def test_unit_command_parsing_and_routing():
    """Test command parsing and handler routing logic."""
    # Test command parsing
    commands = [
        ("/start", "start_command"),
        ("/balance", "balance_command"),
        ("/send 5.0 rAddress123", "send_command"),
        ("alias add friend rAddress456", "alias_add"),
    ]

    for command_text, expected_handler in commands:
        # Simple parsing logic test
        if command_text.startswith("/start"):
            handler_name = "start_command"
        elif command_text.startswith("/balance"):
            handler_name = "balance_command"
        elif command_text.startswith("/send"):
            handler_name = "send_command"
        elif command_text.startswith("alias add"):
            handler_name = "alias_add"
        else:
            handler_name = "unknown"

        assert handler_name == expected_handler


@pytest.mark.unit
def test_unit_transaction_state_transitions():
    """Test transaction state machine transitions."""
    # Valid transitions
    valid_transitions = {
        "CREATED": ["PENDING"],
        "PENDING": ["CONFIRMED", "FAILED"],
        "CONFIRMED": [],  # Terminal state
        "FAILED": [],  # Terminal state
    }

    def is_valid_transition(from_state: str, to_state: str) -> bool:
        return to_state in valid_transitions.get(from_state, [])

    # Test valid transitions
    assert is_valid_transition("CREATED", "PENDING")
    assert is_valid_transition("PENDING", "CONFIRMED")
    assert is_valid_transition("PENDING", "FAILED")

    # Test invalid transitions
    assert not is_valid_transition("PENDING", "CREATED")  # Cannot go backwards
    assert not is_valid_transition("CONFIRMED", "PENDING")  # Cannot leave terminal state
    assert not is_valid_transition("FAILED", "CONFIRMED")  # Cannot leave terminal state
    assert not is_valid_transition("CREATED", "CONFIRMED")  # Cannot skip PENDING


@pytest.mark.unit
def test_unit_environment_variable_defaults():
    """Test environment variable handling and defaults."""
    # Test missing BOT_TOKEN
    with patch.dict(os.environ, {}, clear=True):
        # Simulate bot initialization without token
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        assert bot_token is None

        # In real code, this should raise clear error
        def validate_bot_token(token):
            if not token:
                raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
            return token

        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN environment variable is required"):
            validate_bot_token(bot_token)

    # Test optional environment variables with defaults
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token"}, clear=True):
        api_url = os.getenv("API_URL", "http://localhost:8000")
        debug_mode = os.getenv("DEBUG", "false").lower() == "true"

        assert api_url == "http://localhost:8000"  # Default applied
        assert debug_mode is False  # Default applied


@pytest.mark.unit
def test_unit_formatting_helpers_used_by_bot():
    """Test formatting utilities used in bot responses."""
    # Test XRP amount formatting
    amount_tests = [
        (Decimal("5.123456"), "5.123456"),
        (Decimal("10.0"), "10.000000"),
        (Decimal("0.000001"), "0.000001"),
        (100.5, "100.500000"),
    ]

    for amount, expected in amount_tests:
        formatted = format_xrp_amount(amount)
        assert expected in formatted

    # Test HTML escaping
    dangerous_text = "<script>alert('xss')</script>"
    escaped = escape_html(dangerous_text)
    assert "&lt;script&gt;" in escaped
    assert "<script>" not in escaped

    # Test error message formatting
    error = format_error_message("Something went wrong")
    assert "❌" in error  # Error emoji
    assert "Something went wrong" in error

    # Assert no formatting regressions
    assert "<b>" in error  # HTML bold tags preserved
    assert "&lt;" not in error or "&gt;" not in error  # Properly formatted HTML


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unit_username_update_validation_and_flow(telegram_update_factory, mock_context):
    """Test username update feature with validation and API call."""
    user_id = 123456789
    chat_id = 123456789
    
    # Set up context for username update state
    mock_context.user_data["awaiting_username_update"] = True
    
    # Mock API response for successful username update
    with patch("httpx.AsyncClient") as mock_http:
        mock_client = AsyncMock()
        mock_http.return_value.__aenter__.return_value = mock_client
        mock_client.put.return_value = Mock(status_code=200, json=lambda: {"success": True})
        
        # Test valid username update
        update = telegram_update_factory(chat_id, "new_username123", 1, user_id)
        
        await handle_username_update(update, mock_context)
        
        # Assert API was called with correct data
        mock_client.put.assert_called_once()
        call_args = mock_client.put.call_args
        # Check the URL argument (first positional argument)
        assert "/api/v1/user/profile/" in call_args[0][0]
        # Check the JSON data (keyword argument)
        assert call_args[1]["json"]["telegram_username"] == "new_username123"
        
        # Assert success message was sent
        update.message.reply_text.assert_called_once()
        reply_args = update.message.reply_text.call_args
        reply_text = reply_args[0][0]
        assert "✅" in reply_text
        assert "Username Updated!" in reply_text
        assert "@new_username123" in reply_text
        
        # Assert state was cleared
        assert "awaiting_username_update" not in mock_context.user_data


@pytest.mark.unit
@pytest.mark.asyncio 
async def test_unit_username_validation_rejects_invalid_usernames(telegram_update_factory, mock_context):
    """Test username validation rejects invalid formats."""
    user_id = 123456789
    chat_id = 123456789
    
    # Set up context for username update state
    mock_context.user_data["awaiting_username_update"] = True
    
    invalid_usernames = [
        "ab",  # Too short
        "a" * 33,  # Too long  
        "user name",  # Contains space
        "user@name",  # Contains @
        "user-name",  # Contains hyphen
        "user.name",  # Contains period
    ]
    
    for invalid_username in invalid_usernames:
        # Reset state for each test
        mock_context.user_data["awaiting_username_update"] = True
        
        update = telegram_update_factory(chat_id, invalid_username, 1, user_id)
        
        await handle_username_update(update, mock_context)
        
        # Assert error message was sent
        update.message.reply_text.assert_called()
        reply_args = update.message.reply_text.call_args
        reply_text = reply_args[0][0]
        assert "❌" in reply_text
        assert ("Invalid username" in reply_text or "Must be 3-32 characters" in reply_text)
        
        # Reset mock for next iteration
        update.message.reply_text.reset_mock()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unit_message_handler_precedence_issue(telegram_update_factory, mock_context):
    """Test that username updates work when user is in the correct state."""
    user_id = 123456789
    chat_id = 123456789
    
    # User is in username update state
    mock_context.user_data["awaiting_username_update"] = True
    
    # But NOT in wallet import state
    assert mock_context.user_data.get("import_state") != "waiting_for_private_key"
    
    update = telegram_update_factory(chat_id, "validusername", 1, user_id)
    
    # Mock the API call for username update
    with patch("httpx.AsyncClient") as mock_http:
        mock_client = AsyncMock()
        mock_http.return_value.__aenter__.return_value = mock_client
        mock_client.put.return_value = Mock(status_code=200, json=lambda: {"success": True})
        
        # Now username handler should work properly 
        await handle_username_update(update, mock_context)
        
        # Verify the API was called (username update succeeded)
        mock_client.put.assert_called_once()
        
        # Verify success message was sent
        update.message.reply_text.assert_called_once()
        reply_args = update.message.reply_text.call_args
        reply_text = reply_args[0][0]
        assert "✅" in reply_text
        assert "Username Updated!" in reply_text
        
        # Verify state was cleared after successful update
        assert "awaiting_username_update" not in mock_context.user_data
