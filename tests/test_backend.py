import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base, User, Wallet
from backend.services.user_service import UserService

class TestUserService:
    """Test user management service"""

    @pytest.fixture
    def test_db(self):
        """Create test database session"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture
    def user_service(self):
        """Create an instance of the user service"""
        return UserService()

    @pytest.mark.asyncio
    async def test_create_user(self, user_service, test_db):
        """Test user creation with wallet"""
        with patch('backend.services.xrp_service.XRPService.create_wallet') as mock_wallet:
            mock_wallet.return_value = ("rTestAddress123", "encrypted_secret")

            user = await user_service.create_user(
                db=test_db,
                telegram_id="123456789",
                telegram_username="testuser",
                telegram_first_name="Test",
                telegram_last_name="User"
            )

            assert user.telegram_id == "123456789"
            assert user.telegram_username == "testuser"
            assert user.wallet is not None
            assert user.wallet.xrp_address == "rTestAddress123"

    @pytest.mark.asyncio
    async def test_duplicate_user_returns_existing(self, user_service, test_db):
        """Test that creating duplicate user returns existing"""
        # Patch the wallet creation as it's not the focus of this test
        with patch('backend.services.xrp_service.XRPService.create_wallet') as mock_wallet:
            mock_wallet.return_value = ("rTestAddress1", "secret1")
            # Create first user
            user1 = await user_service.create_user(
                db=test_db,
                telegram_id="123456789",
                telegram_username="testuser",
                telegram_first_name="Test",
                telegram_last_name="User"
            )

            mock_wallet.return_value = ("rTestAddress2", "secret2")
            # Try to create same user again
            user2 = await user_service.create_user(
                db=test_db,
                telegram_id="123456789",
                telegram_username="testuser",
                telegram_first_name="Test",
                telegram_last_name="User"
            )

        assert user1.id == user2.id

    def test_get_user_by_telegram_id(self, user_service, test_db):
        """Test user retrieval by Telegram ID"""
        # Create user first
        user_to_add = User(telegram_id="999999999", telegram_username="get_user")
        test_db.add(user_to_add)
        test_db.commit()

        user = user_service.get_user_by_telegram_id(test_db, "999999999")

        assert user is not None
        assert user.telegram_id == "999999999"

    @pytest.mark.asyncio
    async def test_send_xrp_validation(self, user_service, test_db):
        """Test send XRP validation logic"""
        # Create sender with wallet
        sender = User(
            telegram_id="111111111",
            wallet=Wallet(
                xrp_address="rSenderAddress",
                encrypted_secret="encrypted",
                balance=100.0
            )
        )
        test_db.add(sender)
        test_db.commit()

        # Test invalid recipient address
        result = await user_service.send_xrp(
            db=test_db,
            sender=sender,
            recipient_address="invalid_address",
            amount=10.0
        )

        assert result["success"] is False
        assert "Invalid recipient address" in result["error"]
