"""
Security Utilities

Centralized utilities for token encryption, decryption, and hashing.
"""

import os
import hashlib
import base64
from typing import Optional
from cryptography.fernet import Fernet


class TokenCrypto:
    """
    Centralized token encryption and hashing utilities.

    Provides consistent token encryption/decryption and hashing across all services.
    Uses Fernet (symmetric encryption) with a key derived from environment variables.
    """

    def __init__(self, encryption_key: Optional[bytes] = None):
        """
        Initialize TokenCrypto with encryption key.

        Args:
            encryption_key: Optional pre-computed Fernet key.
                          If not provided, will be derived from environment.
        """
        if encryption_key is None:
            encryption_key = self._get_encryption_key()

        self.encryption_key = encryption_key
        self.cipher_suite = Fernet(self.encryption_key)

    def _get_encryption_key(self) -> bytes:
        """
        Get or create encryption key for token storage.

        Derives a Fernet-compatible key from the ANALYTICS_TOKEN_ENCRYPTION_KEY
        environment variable. If not set, uses a default (NOT recommended for production).

        Returns:
            Base64-encoded 32-byte key suitable for Fernet
        """
        # Get secret from environment
        fixed_secret = os.getenv(
            "ANALYTICS_TOKEN_ENCRYPTION_KEY",
            "sato-analytics-token-encryption-key-2025"  # Default for dev only
        )

        # Create a consistent 32-byte key
        key_bytes = fixed_secret.encode("utf-8")
        key_bytes = key_bytes.ljust(32, b"0")[:32]

        # Fernet requires base64-encoded key
        return base64.urlsafe_b64encode(key_bytes)

    def encrypt_token(self, token: str) -> bytes:
        """
        Encrypt a token for secure storage.

        Args:
            token: Plain text token to encrypt

        Returns:
            Encrypted token as bytes

        Example:
            >>> crypto = TokenCrypto()
            >>> encrypted = crypto.encrypt_token("my_access_token")
            >>> print(type(encrypted))
            <class 'bytes'>
        """
        if not token:
            raise ValueError("Token cannot be empty")

        return self.cipher_suite.encrypt(token.encode())

    def decrypt_token(self, encrypted_token: bytes) -> str:
        """
        Decrypt a token for use.

        Args:
            encrypted_token: Encrypted token bytes

        Returns:
            Decrypted token as string

        Raises:
            cryptography.fernet.InvalidToken: If token is invalid or corrupted

        Example:
            >>> crypto = TokenCrypto()
            >>> encrypted = crypto.encrypt_token("my_access_token")
            >>> decrypted = crypto.decrypt_token(encrypted)
            >>> print(decrypted)
            'my_access_token'
        """
        if not encrypted_token:
            raise ValueError("Encrypted token cannot be empty")

        return self.cipher_suite.decrypt(encrypted_token).decode()

    def generate_token_hash(self, token: str) -> str:
        """
        Generate SHA256 hash for token validation.

        Used to verify token integrity without decrypting.

        Args:
            token: Plain text token to hash

        Returns:
            Hex string of SHA256 hash

        Example:
            >>> crypto = TokenCrypto()
            >>> hash1 = crypto.generate_token_hash("token123")
            >>> hash2 = crypto.generate_token_hash("token123")
            >>> print(hash1 == hash2)
            True
        """
        if not token:
            raise ValueError("Token cannot be empty")

        return hashlib.sha256(token.encode()).hexdigest()

    def verify_token_hash(self, token: str, expected_hash: str) -> bool:
        """
        Verify a token matches an expected hash.

        Args:
            token: Plain text token to verify
            expected_hash: Expected SHA256 hash

        Returns:
            True if hash matches, False otherwise

        Example:
            >>> crypto = TokenCrypto()
            >>> token_hash = crypto.generate_token_hash("token123")
            >>> print(crypto.verify_token_hash("token123", token_hash))
            True
            >>> print(crypto.verify_token_hash("wrong", token_hash))
            False
        """
        if not token or not expected_hash:
            return False

        actual_hash = self.generate_token_hash(token)
        return actual_hash == expected_hash


# Global singleton instance
_token_crypto_instance: Optional[TokenCrypto] = None


def get_token_crypto() -> TokenCrypto:
    """
    Get global TokenCrypto singleton instance.

    Returns:
        TokenCrypto instance

    Example:
        >>> from app.utils.security_utils import get_token_crypto
        >>> crypto = get_token_crypto()
        >>> encrypted = crypto.encrypt_token("my_token")
    """
    global _token_crypto_instance

    if _token_crypto_instance is None:
        _token_crypto_instance = TokenCrypto()

    return _token_crypto_instance


# Convenience functions that use the global instance
def encrypt_token(token: str) -> bytes:
    """
    Encrypt a token using the global TokenCrypto instance.

    Convenience function for quick encryption without managing instances.

    Args:
        token: Plain text token to encrypt

    Returns:
        Encrypted token as bytes
    """
    return get_token_crypto().encrypt_token(token)


def decrypt_token(encrypted_token: bytes) -> str:
    """
    Decrypt a token using the global TokenCrypto instance.

    Convenience function for quick decryption without managing instances.

    Args:
        encrypted_token: Encrypted token bytes

    Returns:
        Decrypted token as string
    """
    return get_token_crypto().decrypt_token(encrypted_token)


def generate_token_hash(token: str) -> str:
    """
    Generate token hash using the global TokenCrypto instance.

    Convenience function for quick hashing without managing instances.

    Args:
        token: Plain text token to hash

    Returns:
        Hex string of SHA256 hash
    """
    return get_token_crypto().generate_token_hash(token)


def verify_token_hash(token: str, expected_hash: str) -> bool:
    """
    Verify token hash using the global TokenCrypto instance.

    Convenience function for quick verification without managing instances.

    Args:
        token: Plain text token to verify
        expected_hash: Expected SHA256 hash

    Returns:
        True if hash matches, False otherwise
    """
    return get_token_crypto().verify_token_hash(token, expected_hash)
