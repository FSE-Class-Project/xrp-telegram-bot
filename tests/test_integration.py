import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Test configuration
TEST_DATABASE_URL = "sqlite:///./test.db"
TEST_TELEGRAM_ID = "123456789"
TEST_XRP_ADDRESS = "rTestAddressXRP123456789"

@pytest.fixture
def test_db():
    """Create test database"""
    from backend.database.models import Base
    from backend.database.connection import get_db
    
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    Base.metadata.create_all(bind=engine)
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    yield override_get_db
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def test_client(test_db):
    """Create test client with test database"""
    from backend.main import app
    from backend.database.connection import get_db
    
    app.dependency_overrides[get_db] = test_db
    
    with TestClient(app) as client:
        yield client

class TestAPI:
    """Test API endpoints"""
    
    def test_health_check(self, test_client):
        """Test health endpoint"""
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "network" in data
    
    @pytest.mark.asyncio
    async def test_user_registration(self, test_client):
        """Test user registration"""
        with patch('backend.services.xrp_service.xrp_service.create_wallet') as mock_wallet:
            mock_wallet.return_value = (TEST_XRP_ADDRESS, "encrypted_secret")
            
            with patch('backend.services.xrp_service.xrp_service.fund_wallet_from_faucet') as mock_fund:
                mock_fund.return_value = {"success": True, "amount": 10000}
                
                response = test_client.post(
                    "/api/v1/user/register",
                    json={
                        "telegram_id": TEST_TELEGRAM_ID,
                        "telegram_username": "testuser",
                        "telegram_first_name": "Test",
                        "telegram_last_name": "User"
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["telegram_id"] == TEST_TELEGRAM_ID
                assert data["xrp_address"] == TEST_XRP_ADDRESS
    
    def test_get_balance(self, test_client):
        """Test balance retrieval"""
        # First register a user
        with patch('backend.services.xrp_service.xrp_service.create_wallet') as mock_wallet:
            mock_wallet.return_value = (TEST_XRP_ADDRESS, "encrypted_secret")
            
            with patch('backend.services.xrp_service.xrp_service.fund_wallet_from_faucet') as mock_fund:
                mock_fund.return_value = {"success": True}
                
                test_client.post(
                    "/api/v1/user/register",
                    json={"telegram_id": "987654321"}
                )
        
        # Get balance
        with patch('backend.services.xrp_service.xrp_service.get_balance') as mock_balance:
            mock_balance.return_value = 100.0
            
            response = test_client.get("/api/v1/wallet/balance/987654321")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "address" in data
            assert data["balance"] == 100.0
    
    def test_validate_address(self, test_client):
        """Test address validation"""
        # Valid address
        response = test_client.get("/api/v1/wallet/validate/rN7n7enGRiLVpHJgWoEjPaXb7JkwD8nH5q")
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        
        # Invalid address
        response = test_client.get("/api/v1/wallet/validate/invalid")
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
    
    def test_get_current_price(self, test_client):
        """Test price endpoint"""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "ripple": {
                    "usd": 0.5234,
                    "usd_24h_change": 2.5,
                    "usd_market_cap": 25000000000,
                    "usd_24h_vol": 1000000000
                }
            }
            mock_get.return_value = mock_response
            
            response = test_client.get("/api/v1/price/current")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["price_usd"] == 0.5234

class TestXRPService:
    """Test XRP service functions"""
    
    def test_wallet_generation(self):
        """Test XRP wallet generation"""
        from backend.services.xrp_service import xrp_service
        
        address, encrypted_secret = xrp_service.create_wallet()
        
        assert address.startswith('r')
        assert len(address) >= 25
        assert encrypted_secret != ""
        assert len(encrypted_secret) > 0
    
    def test_address_validation(self):
        """Test XRP address validation"""
        from backend.services.xrp_service import xrp_service
        
        # Valid addresses
        assert xrp_service.validate_address("rN7n7enGRiLVpHJgWoEjPaXb7JkwD8nH5q")
        assert xrp_service.validate_address("rPEPPER7kfTD9w2To4CQk6UCfuHM9c6GDY")
        
        # Invalid addresses
        assert not xrp_service.validate_address("invalid")
        assert not xrp_service.validate_address("xN7n7enGRiLVpHJgWoEjPaXb7JkwD8nH5q")
        assert not xrp_service.validate_address("r123")
        assert not xrp_service.validate_address("")
        assert not xrp_service.validate_address(None)

class TestEncryption:
    """Test encryption service"""
    
    def test_encryption_decryption(self):
        """Test encrypt/decrypt cycle"""
        from backend.utils.encryption import EncryptionService
        
        service = EncryptionService()
        original = "secret_key_12345_test_data"
        
        encrypted = service.encrypt(original)
        assert encrypted != original
        assert len(encrypted) > 0
        
        decrypted = service.decrypt(encrypted)
        assert decrypted == original
    
    def test_empty_encryption(self):
        """Test encryption with empty data"""
        from backend.utils.encryption import EncryptionService
        
        service = EncryptionService()
        
        with pytest.raises(ValueError):
            service.encrypt("")
        
        with pytest.raises(ValueError):
            service.decrypt("")
    
    def test_key_generation(self):
        """Test encryption key generation"""
        from backend.utils.encryption import EncryptionService
        
        key1 = EncryptionService.generate_key()
        key2 = EncryptionService.generate_key()
        
        assert key1 != key2
        assert len(key1) == 44  # Fernet keys are 44 chars
        assert len(key2) == 44

class TestBotHandlers:
    """Test bot command handlers"""
    
    @pytest.mark.asyncio
    async def test_start_command(self):
        """Test /start command handler"""
        from bot.handlers.start import start_command
        
        # Mock Telegram update and context
        update = Mock()
        update.effective_user.id = 123456789
        update.effective_user.username = "testuser"
        update.effective_user.first_name = "Test"
        update.message.reply_text = AsyncMock()
        
        context = Mock()
        context.bot_data = {'api_url': 'http://localhost:8000'}
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'success': True,
                'user_id': 1,
                'telegram_id': '123456789',
                'xrp_address': 'rTestAddress123',
                'balance': 100.0,
                'is_new': True
            }
            mock_post.return_value = mock_response
            
            await start_command(update, context)
            
            # Verify reply was sent
            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args
            assert "Wallet Created Successfully" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_balance_command(self):
        """Test /balance command handler"""
        from bot.handlers.wallet import balance_command
        
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        
        context = Mock()
        context.bot_data = {'api_url': 'http://localhost:8000'}
        
        with patch('httpx.AsyncClient.get') as mock_get:
            # Mock balance response
            balance_response = Mock()
            balance_response.status_code = 200
            balance_response.json.return_value = {
                'success': True,
                'address': 'rTestAddress123',
                'balance': 100.0
            }
            
            # Mock price response
            price_response = Mock()
            price_response.status_code = 200
            price_response.json.return_value = {
                'price_usd': 0.5
            }
            
            mock_get.side_effect = [balance_response, price_response]
            
            await balance_command(update, context)
            
            # Verify reply was sent
            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args
            assert "Your Balance" in call_args[0][0]
            assert "100" in call_args[0][0]

class TestUserService:
    """Test user service"""
    
    @pytest.mark.asyncio
    async def test_create_user(self, test_db):
        """Test user creation"""
        from backend.services.user_service import user_service
        from backend.database.models import User
        
        # Get test database session
        db = next(test_db())
        
        with patch('backend.services.xrp_service.xrp_service.create_wallet') as mock_wallet:
            mock_wallet.return_value = (TEST_XRP_ADDRESS, "encrypted_secret")
            
            with patch('backend.services.xrp_service.xrp_service.fund_wallet_from_faucet') as mock_fund:
                mock_fund.return_value = {"success": True}
                
                with patch('backend.services.xrp_service.xrp_service.get_balance') as mock_balance:
                    mock_balance.return_value = 100.0
                    
                    result = await user_service.create_user(
                        db=db,
                        telegram_id=TEST_TELEGRAM_ID,
                        telegram_username="testuser"
                    )
                    
                    assert result["success"] is True
                    assert result["telegram_id"] == TEST_TELEGRAM_ID
                    assert result["xrp_address"] == TEST_XRP_ADDRESS
                    
                    # Verify user was created in database
                    user = db.query(User).filter(
                        User.telegram_id == TEST_TELEGRAM_ID
                    ).first()
                    assert user is not None
                    assert user.telegram_username == "testuser"

# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])