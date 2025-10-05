#!/usr/bin/env python3
"""
Key Derivation Module for Welshare Nillion Integration

Implements EIP-712 signature-based key derivation to create did:nil keypairs
from Ethereum EOA accounts. Based on the TypeScript implementation and follows
the process described at https://docs.welshare.app/basics/key-management

Process:
1. Sign an EIP-712 structured message with Ethereum EOA private key
2. Use the signature as entropy with HKDF to derive key material
3. Ensure the derived key is valid for secp256k1 curve
4. Create did:nil keypair from the derived private key
"""

import hashlib
import hmac
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from eth_account import Account
from eth_account.messages import encode_typed_data
from ecdsa import SigningKey, VerifyingKey, SECP256k1


# Constants
COMMON_KDF_SALT = b"SIGNATURE_INTEGRATED_KDF_v1"
SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


@dataclass
class SessionKeyAuthMessage:
    """Authentication message for key derivation"""
    key_id: str
    context: str

    def to_dict(self) -> Dict[str, str]:
        """
        Convert to dictionary for EIP-712 encoding

        IMPORTANT: The order must match TypeScript's JSON.stringify output,
        which follows alphabetical ordering: context before keyId
        """
        # Alphabetical order to match TypeScript: context first, then keyId
        d = {}
        d["context"] = self.context
        d["keyId"] = self.key_id
        return d


@dataclass
class DerivedNillionKeypair:
    """Result of key derivation containing did:nil keypair and metadata"""
    did: str
    private_key: bytes
    public_key_compressed: bytes
    public_key_uncompressed: bytes
    ethereum_address: str
    auth_message: SessionKeyAuthMessage
    eip712_signature: bytes


def hkdf(
    input_key_material: bytes,
    context_information: bytes,
    salt: bytes = COMMON_KDF_SALT,
    output_length: int = 32
) -> bytes:
    """
    HKDF (HMAC-based Key Derivation Function) implementation using HMAC-SHA256

    Args:
        input_key_material: Initial keying material (e.g., signature)
        context_information: Application-specific context data
        salt: Optional salt value (default: COMMON_KDF_SALT)
        output_length: Length of output key material in bytes (default: 32)

    Returns:
        Derived key material of specified length
    """
    # Extract phase: derive a pseudorandom key
    pseudo_random_key = hmac.new(salt, input_key_material, hashlib.sha256).digest()

    # Expand phase: generate output key material
    output = bytearray()
    hash_len = 32  # SHA256 output length
    n = (output_length + hash_len - 1) // hash_len  # Ceiling division

    t = b''
    for i in range(1, n + 1):
        t = hmac.new(
            pseudo_random_key,
            t + context_information + bytes([i]),
            hashlib.sha256
        ).digest()
        output.extend(t)

    return bytes(output[:output_length])


def bytes_to_int(data: bytes) -> int:
    """Convert bytes to integer (big-endian)"""
    return int.from_bytes(data, byteorder='big')


def ensure_valid_secp256k1_key(
    key_material: bytes,
    derivation_data: bytes,
    max_attempts: int = 1000
) -> bytes:
    """
    Ensure the derived key material is valid for secp256k1 curve

    A valid private key must be in range (0, n) where n is the curve order.
    If the key is invalid, re-derive with a counter until a valid key is found.

    Args:
        key_material: Initial key material (32 bytes)
        derivation_data: Context data for re-derivation
        max_attempts: Maximum number of derivation attempts

    Returns:
        Valid secp256k1 private key (32 bytes)

    Raises:
        ValueError: If unable to generate valid key after max_attempts
    """
    candidate = key_material
    counter = 0

    while counter < max_attempts:
        key_value = bytes_to_int(candidate)

        # Check if key is in valid range: 0 < key < n
        if 0 < key_value < SECP256K1_ORDER:
            return candidate

        # If invalid, derive a new candidate with counter
        counter += 1
        counter_bytes = counter.to_bytes(4, byteorder='big')

        candidate = hkdf(
            input_key_material=candidate + counter_bytes,
            context_information=b"SECP256K1_RETRY",
            salt=derivation_data,
            output_length=32
        )

    raise ValueError(f"Failed to generate valid secp256k1 key after {max_attempts} attempts")


def create_eip712_typed_data(
    auth_message: SessionKeyAuthMessage,
    domain_name: str = "Welshare Health Wallet",
    domain_version: str = "1.0"
) -> Dict[str, Any]:
    """
    Create EIP-712 typed data structure for signing

    Args:
        auth_message: Authentication message to sign
        domain_name: EIP-712 domain name
        domain_version: EIP-712 domain version

    Returns:
        EIP-712 typed data structure
    """
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"}
            ],
            "SessionKeyAuthorization": [
                {"name": "context", "type": "string"},
                {"name": "keyId", "type": "string"}
            ]
        },
        "primaryType": "SessionKeyAuthorization",
        "domain": {
            "name": domain_name,
            "version": domain_version
        },
        "message": {
            "context": auth_message.context,
            "keyId": auth_message.key_id
        }
    }


def sign_eip712_message(
    private_key: bytes,
    auth_message: SessionKeyAuthMessage,
    domain_name: str = "Welshare Health Wallet",
    domain_version: str = "1.0"
) -> bytes:
    """
    Sign an EIP-712 typed message with Ethereum private key

    Args:
        private_key: Ethereum EOA private key (32 bytes)
        auth_message: Authentication message to sign
        domain_name: EIP-712 domain name
        domain_version: EIP-712 domain version

    Returns:
        Signature bytes (65 bytes: r + s + v)
    """
    # Create account from private key
    Account.enable_unaudited_hdwallet_features()
    account = Account.from_key(private_key)

    # Create typed data
    typed_data = create_eip712_typed_data(auth_message, domain_name, domain_version)

    # Encode and sign
    encoded_message = encode_typed_data(full_message=typed_data)
    signed_message = account.sign_message(encoded_message)

    # Return signature bytes (65 bytes: r + s + v)
    return signed_message.signature


def derive_nillion_keypair(
    ethereum_private_key: bytes,
    auth_message: SessionKeyAuthMessage,
    user_secret: str = "user@secret.com"
) -> DerivedNillionKeypair:
    """
    Derive a Nillion did:nil keypair from an Ethereum EOA private key

    This implements the signature-based key derivation process:
    1. Sign EIP-712 message with Ethereum private key
    2. Combine user secret and signature as HKDF input
    3. Derive key material with context information
    4. Ensure key is valid for secp256k1
    5. Create did:nil keypair

    Args:
        ethereum_private_key: Ethereum EOA private key (32 bytes)
        auth_message: Authentication message (keyId + context)
        user_secret: Application-specific user secret

    Returns:
        DerivedNillionKeypair with did:nil keypair and metadata
    """
    # Step 1: Sign EIP-712 message to create binding signature
    binding_signature = sign_eip712_message(ethereum_private_key, auth_message)

    # Step 2: Create derivation data from auth message
    # Important: Do NOT sort keys - preserve insertion order to match TypeScript
    derivation_data = json.dumps(auth_message.to_dict(), separators=(',', ':')).encode('utf-8')

    # Step 3: Combine user secret and binding signature as input key material
    user_secret_bytes = user_secret.encode('utf-8')
    input_key_material = user_secret_bytes + binding_signature

    # Step 4: Derive key material using HKDF
    derived_key_material = hkdf(
        input_key_material=input_key_material,
        context_information=derivation_data
    )

    # Step 5: Ensure the derived key is valid for secp256k1
    private_key = ensure_valid_secp256k1_key(derived_key_material, derivation_data)

    # Step 6: Create secp256k1 keypair
    signing_key = SigningKey.from_string(private_key, curve=SECP256k1)
    verifying_key = signing_key.get_verifying_key()

    # Get uncompressed public key (64 bytes)
    public_key_uncompressed = verifying_key.to_string()

    # Create compressed public key (33 bytes: prefix + x-coordinate)
    x_coord = public_key_uncompressed[:32]
    y_coord = public_key_uncompressed[32:]
    y_is_odd = y_coord[-1] & 1
    prefix = b'\x03' if y_is_odd else b'\x02'
    public_key_compressed = prefix + x_coord

    # Create DID from compressed public key
    did = f"did:nil:{public_key_compressed.hex()}"

    # Get Ethereum address for reference
    Account.enable_unaudited_hdwallet_features()
    eth_account = Account.from_key(ethereum_private_key)
    ethereum_address = eth_account.address

    return DerivedNillionKeypair(
        did=did,
        private_key=private_key,
        public_key_compressed=public_key_compressed,
        public_key_uncompressed=public_key_uncompressed,
        ethereum_address=ethereum_address,
        auth_message=auth_message,
        eip712_signature=binding_signature
    )


def verify_derived_keypair(
    keypair: DerivedNillionKeypair,
    ethereum_private_key: bytes
) -> bool:
    """
    Verify that a derived keypair can be reproduced from the Ethereum private key

    Args:
        keypair: Previously derived keypair
        ethereum_private_key: Original Ethereum private key

    Returns:
        True if verification succeeds
    """
    # Re-derive the keypair
    re_derived = derive_nillion_keypair(
        ethereum_private_key=ethereum_private_key,
        auth_message=keypair.auth_message
    )

    # Compare all components
    return (
        re_derived.did == keypair.did and
        re_derived.private_key == keypair.private_key and
        re_derived.public_key_compressed == keypair.public_key_compressed and
        re_derived.eip712_signature == keypair.eip712_signature
    )
