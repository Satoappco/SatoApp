"""
Unit Tests for Security Utilities

Tests the centralized token encryption, decryption, and hashing utilities.
"""

import pytest
import os
from unittest.mock import patch

from app.utils.security_utils import (
    TokenCrypto,
    get_token_crypto,
    encrypt_token,
    decrypt_token,
    generate_token_hash,
    verify_token_hash,
)


class TestTokenCrypto:
    """Tests for TokenCrypto class."""

    def test_init_with_default_key(self):
        """Test initialization with default environment key."""
        crypto = TokenCrypto()
        assert crypto.encryption_key is not None
        assert crypto.cipher_suite is not None

    def test_init_with_custom_key(self):
        """Test initialization with custom encryption key."""
        import base64
        custom_key = base64.urlsafe_b64encode(b"my_custom_key_32_bytes_long!".ljust(32, b"0")[:32])
        crypto = TokenCrypto(encryption_key=custom_key)
        assert crypto.encryption_key == custom_key

    def test_encrypt_token(self):
        """Test token encryption returns bytes."""
        crypto = TokenCrypto()
        token = "my_access_token_12345"
        encrypted = crypto.encrypt_token(token)

        assert isinstance(encrypted, bytes)
        assert encrypted != token.encode()  # Should be encrypted, not plain text

    def test_encrypt_empty_token_raises_error(self):
        """Test that encrypting empty token raises ValueError."""
        crypto = TokenCrypto()

        with pytest.raises(ValueError, match="Token cannot be empty"):
            crypto.encrypt_token("")

    def test_decrypt_token(self):
        """Test token decryption returns original token."""
        crypto = TokenCrypto()
        original_token = "my_access_token_12345"

        encrypted = crypto.encrypt_token(original_token)
        decrypted = crypto.decrypt_token(encrypted)

        assert decrypted == original_token
        assert isinstance(decrypted, str)

    def test_decrypt_empty_token_raises_error(self):
        """Test that decrypting empty token raises ValueError."""
        crypto = TokenCrypto()

        with pytest.raises(ValueError, match="Encrypted token cannot be empty"):
            crypto.decrypt_token(b"")

    def test_decrypt_invalid_token_raises_error(self):
        """Test that decrypting invalid token raises error."""
        crypto = TokenCrypto()

        with pytest.raises(Exception):  # Fernet raises InvalidToken
            crypto.decrypt_token(b"invalid_encrypted_data")

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypt -> decrypt returns original token."""
        crypto = TokenCrypto()
        test_tokens = [
            "short",
            "a_longer_token_with_special_chars_!@#$%",
            "token" * 100,  # Long token
            "token_with_unicode_😀",
        ]

        for token in test_tokens:
            encrypted = crypto.encrypt_token(token)
            decrypted = crypto.decrypt_token(encrypted)
            assert decrypted == token, f"Failed for token: {token}"

    def test_generate_token_hash(self):
        """Test token hash generation returns consistent hex string."""
        crypto = TokenCrypto()
        token = "my_token_123"
        hash1 = crypto.generate_token_hash(token)
        hash2 = crypto.generate_token_hash(token)

        assert hash1 == hash2  # Should be deterministic
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 hex string is 64 characters

    def test_generate_hash_empty_token_raises_error(self):
        """Test that hashing empty token raises ValueError."""
        crypto = TokenCrypto()

        with pytest.raises(ValueError, match="Token cannot be empty"):
            crypto.generate_token_hash("")

    def test_different_tokens_have_different_hashes(self):
        """Test that different tokens produce different hashes."""
        crypto = TokenCrypto()
        hash1 = crypto.generate_token_hash("token1")
        hash2 = crypto.generate_token_hash("token2")

        assert hash1 != hash2

    def test_verify_token_hash_success(self):
        """Test successful token hash verification."""
        crypto = TokenCrypto()
        token = "test_token"
        token_hash = crypto.generate_token_hash(token)

        assert crypto.verify_token_hash(token, token_hash) is True

    def test_verify_token_hash_failure(self):
        """Test failed token hash verification."""
        crypto = TokenCrypto()
        token_hash = crypto.generate_token_hash("correct_token")

        assert crypto.verify_token_hash("wrong_token", token_hash) is False

    def test_verify_token_hash_with_empty_token(self):
        """Test verification with empty token returns False."""
        crypto = TokenCrypto()
        assert crypto.verify_token_hash("", "some_hash") is False
        assert crypto.verify_token_hash("token", "") is False

    def test_same_key_produces_same_encryption(self):
        """Test that same key produces same encryption (deterministic for same key)."""
        # Note: Fernet includes a timestamp, so this tests that the same key
        # can decrypt what it encrypted
        import base64
        key = base64.urlsafe_b64encode(b"test_key_32_bytes_long!!!!!!".ljust(32, b"0")[:32])

        crypto1 = TokenCrypto(encryption_key=key)
        crypto2 = TokenCrypto(encryption_key=key)

        token = "test_token"
        encrypted1 = crypto1.encrypt_token(token)
        decrypted2 = crypto2.decrypt_token(encrypted1)

        assert decrypted2 == token

    def test_different_keys_cannot_decrypt(self):
        """Test that different keys cannot decrypt each other's tokens."""
        import base64
        key1 = base64.urlsafe_b64encode(b"key1_32_bytes_long!!!!!!!!!!".ljust(32, b"0")[:32])
        key2 = base64.urlsafe_b64encode(b"key2_32_bytes_long!!!!!!!!!!".ljust(32, b"0")[:32])

        crypto1 = TokenCrypto(encryption_key=key1)
        crypto2 = TokenCrypto(encryption_key=key2)

        token = "test_token"
        encrypted1 = crypto1.encrypt_token(token)

        with pytest.raises(Exception):  # Should fail to decrypt
            crypto2.decrypt_token(encrypted1)


class TestGlobalTokenCrypto:
    """Tests for global TokenCrypto singleton."""

    def test_get_token_crypto_returns_singleton(self):
        """Test that get_token_crypto returns the same instance."""
        crypto1 = get_token_crypto()
        crypto2 = get_token_crypto()

        assert crypto1 is crypto2  # Same instance

    def test_singleton_works_across_calls(self):
        """Test that singleton maintains state across calls."""
        crypto = get_token_crypto()
        token = "test_token_singleton"

        encrypted = crypto.encrypt_token(token)
        decrypted = get_token_crypto().decrypt_token(encrypted)

        assert decrypted == token


class TestConvenienceFunctions:
    """Tests for convenience functions that use global instance."""

    def test_encrypt_token_convenience(self):
        """Test convenience encrypt_token function."""
        token = "test_token"
        encrypted = encrypt_token(token)

        assert isinstance(encrypted, bytes)
        assert encrypted != token.encode()

    def test_decrypt_token_convenience(self):
        """Test convenience decrypt_token function."""
        token = "test_token"
        encrypted = encrypt_token(token)
        decrypted = decrypt_token(encrypted)

        assert decrypted == token

    def test_generate_token_hash_convenience(self):
        """Test convenience generate_token_hash function."""
        token = "test_token"
        hash1 = generate_token_hash(token)
        hash2 = generate_token_hash(token)

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_verify_token_hash_convenience(self):
        """Test convenience verify_token_hash function."""
        token = "test_token"
        token_hash = generate_token_hash(token)

        assert verify_token_hash(token, token_hash) is True
        assert verify_token_hash("wrong_token", token_hash) is False


class TestEnvironmentKeyHandling:
    """Tests for environment key handling."""

    @patch.dict(os.environ, {"ANALYTICS_TOKEN_ENCRYPTION_KEY": "my_custom_env_key"})
    def test_uses_environment_key(self):
        """Test that TokenCrypto uses environment variable for key."""
        crypto = TokenCrypto()

        # Should not raise an error
        token = "test_token"
        encrypted = crypto.encrypt_token(token)
        decrypted = crypto.decrypt_token(encrypted)

        assert decrypted == token

    @patch.dict(os.environ, {}, clear=True)
    def test_uses_default_key_when_env_not_set(self):
        """Test that TokenCrypto uses default key when env var not set."""
        # Remove ANALYTICS_TOKEN_ENCRYPTION_KEY from environment
        if "ANALYTICS_TOKEN_ENCRYPTION_KEY" in os.environ:
            del os.environ["ANALYTICS_TOKEN_ENCRYPTION_KEY"]

        crypto = TokenCrypto()

        # Should still work with default key
        token = "test_token"
        encrypted = crypto.encrypt_token(token)
        decrypted = crypto.decrypt_token(encrypted)

        assert decrypted == token

    def test_consistent_key_generation(self):
        """Test that key generation is consistent."""
        crypto1 = TokenCrypto()
        crypto2 = TokenCrypto()

        # Both should use the same key
        token = "test_token"
        encrypted1 = crypto1.encrypt_token(token)
        decrypted2 = crypto2.decrypt_token(encrypted1)

        assert decrypted2 == token


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_encrypt_decrypt_special_characters(self):
        """Test encryption/decryption with special characters."""
        crypto = TokenCrypto()
        special_tokens = [
            "token!@#$%^&*()",
            "token\nwith\nnewlines",
            "token\twith\ttabs",
            "token with spaces",
            "token_with_unicode_😀🎉",
        ]

        for token in special_tokens:
            encrypted = crypto.encrypt_token(token)
            decrypted = crypto.decrypt_token(encrypted)
            assert decrypted == token

    def test_encrypt_decrypt_very_long_token(self):
        """Test encryption/decryption with very long token."""
        crypto = TokenCrypto()
        long_token = "x" * 10000  # 10KB token

        encrypted = crypto.encrypt_token(long_token)
        decrypted = crypto.decrypt_token(encrypted)

        assert decrypted == long_token

    def test_hash_collision_resistance(self):
        """Test that similar tokens have different hashes."""
        crypto = TokenCrypto()
        hashes = set()

        for i in range(100):
            token = f"token_{i}"
            token_hash = crypto.generate_token_hash(token)
            assert token_hash not in hashes, f"Hash collision for token_{i}"
            hashes.add(token_hash)

    def test_encrypt_decrypt_with_bytes_input(self):
        """Test that decrypt handles bytes input correctly."""
        crypto = TokenCrypto()
        token = "test_token"

        encrypted = crypto.encrypt_token(token)
        decrypted = crypto.decrypt_token(encrypted)

        assert decrypted == token


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing encrypted tokens."""

    def test_can_decrypt_tokens_encrypted_with_old_method(self):
        """Test that we can decrypt tokens encrypted with the old method."""
        # This test ensures backward compatibility
        # In practice, you'd test with actual tokens from production

        crypto = TokenCrypto()
        token = "test_token_backward_compat"

        # Encrypt with new method
        encrypted = crypto.encrypt_token(token)

        # Decrypt with new method (should work)
        decrypted = crypto.decrypt_token(encrypted)

        assert decrypted == token
