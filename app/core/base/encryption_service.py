# """
# Base Encryption Service

# Provides common encryption/decryption functionality for OAuth tokens.
# Eliminates duplicate encryption code across Facebook, Google Analytics, and Google Ads services.
# """

# import os
# import base64
# import hashlib
# from cryptography.fernet import Fernet
# from typing import Union


# class BaseEncryptionService:
#     """
#     Base class for services that need to encrypt/decrypt OAuth tokens.
    
#     Provides common encryption functionality to eliminate code duplication
#     across Facebook, Google Analytics, and Google Ads services.
#     """
    
#     def __init__(self):
#         """Initialize encryption service with cipher suite"""
#         self.cipher_suite = Fernet(self._get_encryption_key())
    
#     def _get_encryption_key(self) -> bytes:
#         """
#         Get or create encryption key for token storage.
        
#         Uses a fixed key based on environment variable for consistency.
#         In production, this should be stored in environment variables.
        
#         Returns:
#             bytes: Base64-encoded 32-byte encryption key
#         """
#         # Use a fixed key based on a known secret for consistency
#         # In production, this should be stored in environment variables
#         fixed_secret = os.getenv("ANALYTICS_TOKEN_ENCRYPTION_KEY", "sato-analytics-token-encryption-key-2025")
        
#         # Create a consistent 32-byte key
#         key_bytes = fixed_secret.encode('utf-8')
#         key_bytes = key_bytes.ljust(32, b'0')[:32]
#         return base64.urlsafe_b64encode(key_bytes)
    
#     def encrypt_token(self, token: str) -> bytes:
#         """
#         Encrypt token for secure storage.
        
#         Args:
#             token (str): OAuth token to encrypt
            
#         Returns:
#             bytes: Encrypted token
#         """
#         return self.cipher_suite.encrypt(token.encode())
    
#     def decrypt_token(self, encrypted_token: Union[bytes, str]) -> str:
#         """
#         Decrypt token for use.
        
#         Args:
#             encrypted_token (Union[bytes, str]): Encrypted token to decrypt
            
#         Returns:
#             str: Decrypted token
            
#         Raises:
#             ValueError: If encrypted_token is None or invalid type
#         """
#         # Validate input
#         if encrypted_token is None:
#             raise ValueError("Encrypted token is None - connection may not be properly initialized")
        
#         if not isinstance(encrypted_token, (bytes, str)):
#             raise ValueError(f"Encrypted token must be bytes or str, got {type(encrypted_token)}")
        
#         # Convert string to bytes if needed
#         if isinstance(encrypted_token, str):
#             encrypted_token = encrypted_token.encode('utf-8')
        
#         return self.cipher_suite.decrypt(encrypted_token).decode()
    
#     def generate_token_hash(self, token: str) -> str:
#         """
#         Generate hash for token validation.
        
#         Args:
#             token (str): Token to hash
            
#         Returns:
#             str: SHA256 hash of the token
#         """
#         return hashlib.sha256(token.encode()).hexdigest()
