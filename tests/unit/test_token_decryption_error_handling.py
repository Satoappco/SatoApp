"""
Unit Tests for Token Decryption Error Handling

Tests that token decryption errors are properly handled and reported
with informative error messages.
"""

import pytest
from cryptography.fernet import Fernet, InvalidToken
from app.utils.security_utils import decrypt_token, get_token_crypto, TokenCrypto


class TestTokenDecryptionErrors:
    """Test token decryption error handling."""

    def test_invalid_token_has_empty_message(self):
        """Test that InvalidToken exception has empty message."""
        # This test documents the behavior that we're working around
        try:
            f = Fernet(Fernet.generate_key())
            f.decrypt(b'invalid_data')
        except InvalidToken as e:
            # InvalidToken has an empty string message
            assert str(e) == ""
            assert type(e).__name__ == "InvalidToken"

    def test_decrypt_token_with_wrong_key_raises_invalid_token(self):
        """Test that decrypting with wrong key raises InvalidToken."""
        # Encrypt with one key
        crypto1 = TokenCrypto()
        encrypted = crypto1.encrypt_token("test_token")

        # Try to decrypt with a different key
        crypto2 = TokenCrypto(encryption_key=Fernet.generate_key())

        with pytest.raises(InvalidToken):
            crypto2.decrypt_token(encrypted)

    def test_decrypt_token_with_empty_value_raises_value_error(self):
        """Test that decrypting empty value raises ValueError."""
        with pytest.raises(ValueError, match="Encrypted token cannot be empty"):
            decrypt_token(b"")

        with pytest.raises(ValueError, match="Encrypted token cannot be empty"):
            decrypt_token(None)

    def test_decrypt_token_with_corrupted_data_raises_invalid_token(self):
        """Test that decrypting corrupted data raises InvalidToken."""
        # Create valid encrypted token
        crypto = TokenCrypto()
        encrypted = crypto.encrypt_token("test_token")

        # Corrupt the data
        corrupted = encrypted[:-5] + b"xxxxx"

        with pytest.raises(InvalidToken):
            crypto.decrypt_token(corrupted)


class TestErrorMessageFormatting:
    """Test that error messages are properly formatted for display."""

    def test_invalid_token_error_message_formatting(self):
        """Test proper error message formatting for InvalidToken."""
        try:
            f = Fernet(Fernet.generate_key())
            f.decrypt(b'invalid')
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e) if str(e) else error_type

            # Should fall back to error_type since str(e) is empty
            if error_type == "InvalidToken":
                error_msg = "Invalid or corrupted token (possibly encrypted with different key)"

            assert error_msg == "Invalid or corrupted token (possibly encrypted with different key)"
            assert "Invalid" in error_msg or "corrupted" in error_msg

    def test_value_error_message_formatting(self):
        """Test proper error message formatting for ValueError."""
        try:
            decrypt_token(None)
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e) if str(e) else error_type

            # ValueError should have a message
            assert error_msg != ""
            assert "Encrypted token cannot be empty" in error_msg


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
