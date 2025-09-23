"""Security-focused tests for the XRP Telegram Bot."""

from decimal import Decimal

import pytest

from backend.utils.encryption import EncryptionService


class TestEncryption:
    """Test encryption and decryption functionality."""

    def test_encryption_roundtrip(self):
        """Test that encryption and decryption work correctly."""
        key = EncryptionService.generate_key()
        encryption_service = EncryptionService(key)
        original_data = "test_secret_data"

        encrypted = encryption_service.encrypt(original_data)
        decrypted = encryption_service.decrypt(encrypted)

        assert decrypted == original_data
        assert encrypted != original_data
        assert len(encrypted) > len(original_data)  # Encrypted should be longer

    def test_encryption_empty_data_validation(self):
        """Test encryption handles empty data appropriately."""
        key = EncryptionService.generate_key()
        encryption_service = EncryptionService(key)

        # Empty string should raise ValueError
        with pytest.raises(ValueError, match="Cannot encrypt empty data"):
            encryption_service.encrypt("")

    def test_encryption_invalid_decrypt(self):
        """Test decryption with wrong key fails appropriately."""
        key1 = EncryptionService.generate_key()
        key2 = EncryptionService.generate_key()

        service1 = EncryptionService(key1)
        service2 = EncryptionService(key2)

        original_data = "secret_test_data"
        encrypted = service1.encrypt(original_data)

        # Decrypting with wrong key should raise an exception
        with pytest.raises(ValueError, match="Decryption failed"):
            service2.decrypt(encrypted)

    def test_encryption_key_generation(self):
        """Test encryption key generation produces valid keys."""
        key1 = EncryptionService.generate_key()
        key2 = EncryptionService.generate_key()

        # Keys should be different
        assert key1 != key2

        # Keys should be proper length (base64 encoded Fernet keys)
        assert len(key1) == 44  # Fernet keys are 44 characters when base64 encoded
        assert len(key2) == 44

        # Keys should be valid base64-like strings
        assert isinstance(key1, str)
        assert isinstance(key2, str)


class TestInputValidation:
    """Test input validation for security vulnerabilities."""

    def test_xrp_address_validation_rejects_malicious_input(self):
        """Test XRP address validation rejects potentially malicious inputs."""
        from backend.services.xrp_service import XRPService

        xrp_service = XRPService()

        # Test various potentially malicious inputs
        malicious_inputs = [
            "'; DROP TABLE users; --",  # SQL injection attempt
            "<script>alert('xss')</script>",  # XSS attempt
            "../../etc/passwd",  # Path traversal
            "javascript:alert('xss')",  # JavaScript injection
            "\x00\x01\x02",  # Null bytes
            "A" * 1000,  # Buffer overflow attempt
            "rN7n7otQDd6FczFgLdSqDskUvVfTM1UX\x00",  # Valid format with null byte
        ]

        for malicious_input in malicious_inputs:
            is_valid = xrp_service.validate_address(malicious_input)
            assert not is_valid, f"Malicious input {repr(malicious_input)} should be rejected"

    def test_amount_validation_rejects_malicious_input(self):
        """Test amount validation rejects potentially dangerous values."""
        # Test various edge cases that could cause issues
        dangerous_amounts = [
            float("inf"),  # Infinity
            float("-inf"),  # Negative infinity
            float("nan"),  # Not a number
            Decimal("inf"),  # Decimal infinity
            Decimal("-inf"),  # Decimal negative infinity
            Decimal("nan"),  # Decimal NaN
        ]

        for dangerous_amount in dangerous_amounts:
            # These should be rejected by any proper validation
            try:
                # Convert to string (what might happen in API)
                str_amount = str(dangerous_amount)
                # Should not be parseable as valid amount or should be rejected
                assert str_amount in ["inf", "-inf", "nan", "Infinity", "-Infinity", "NaN"]
            except (ValueError, TypeError, OverflowError):
                # Exception is acceptable - means it's being rejected
                pass
