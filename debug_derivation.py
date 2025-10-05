#!/usr/bin/env python3
"""
Debug script to output all intermediate values in key derivation
"""

from key_derivation import (
    sign_eip712_message,
    SessionKeyAuthMessage,
    hkdf,
    ensure_valid_secp256k1_key
)
import json
from ecdsa import SigningKey, SECP256k1

# Test private key
# NOTE: This key can be considered public and safe to use. It's the 0th account from 11x test junk Ganache / Hardhat / Anvil sample seed. 
test_private_key = bytes.fromhex("ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")

# Auth message
auth_message = SessionKeyAuthMessage(key_id="1", context="nillion")

print("=" * 70)
print("KEY DERIVATION DEBUG OUTPUT")
print("=" * 70)
print()

print("INPUT:")
print(f"  Ethereum Private Key: {test_private_key.hex()}")
print(f"  Auth Message: {auth_message.to_dict()}")
print(f"  User Secret: user@secret.com")
print()

# Step 1: EIP-712 Signature
print("STEP 1: EIP-712 Signature")
binding_signature = sign_eip712_message(test_private_key, auth_message)
print(f"  Signature (65 bytes): {binding_signature.hex()}")
print(f"  Signature r (32 bytes): {binding_signature[:32].hex()}")
print(f"  Signature s (32 bytes): {binding_signature[32:64].hex()}")
print(f"  Signature v (1 byte): {binding_signature[64]:02x}")
print()

# Step 2: Derivation Data
print("STEP 2: Derivation Data")
derivation_data = json.dumps(auth_message.to_dict(), separators=(',', ':')).encode('utf-8')
print(f"  JSON: {derivation_data.decode('utf-8')}")
print(f"  Bytes (hex): {derivation_data.hex()}")
print()

# Step 3: Input Key Material
print("STEP 3: Input Key Material")
user_secret_bytes = "user@secret.com".encode('utf-8')
input_key_material = user_secret_bytes + binding_signature
print(f"  User secret: {user_secret_bytes.decode('utf-8')}")
print(f"  User secret (hex): {user_secret_bytes.hex()}")
print(f"  Combined length: {len(input_key_material)} bytes")
print(f"  Combined (hex): {input_key_material.hex()}")
print()

# Step 4: HKDF
print("STEP 4: HKDF Derivation")
derived_key_material = hkdf(
    input_key_material=input_key_material,
    context_information=derivation_data
)
print(f"  Derived key material (32 bytes): {derived_key_material.hex()}")
print()

# Step 5: Ensure valid
print("STEP 5: Ensure Valid secp256k1 Key")
private_key = ensure_valid_secp256k1_key(derived_key_material, derivation_data)
print(f"  Final private key (32 bytes): {private_key.hex()}")
print()

# Step 6: Public Key
print("STEP 6: Derive Public Key")
signing_key = SigningKey.from_string(private_key, curve=SECP256k1)
verifying_key = signing_key.get_verifying_key()
public_key_uncompressed = verifying_key.to_string()

x_coord = public_key_uncompressed[:32]
y_coord = public_key_uncompressed[32:]
y_is_odd = y_coord[-1] & 1
prefix = b'\x03' if y_is_odd else b'\x02'
public_key_compressed = prefix + x_coord

print(f"  Public key (uncompressed, 64 bytes): {public_key_uncompressed.hex()}")
print(f"  Public key x-coord (32 bytes): {x_coord.hex()}")
print(f"  Public key y-coord (32 bytes): {y_coord.hex()}")
print(f"  Y is odd: {y_is_odd}")
print(f"  Prefix: {prefix.hex()}")
print(f"  Public key (compressed, 33 bytes): {public_key_compressed.hex()}")
print()

print("=" * 70)
print("RESULT:")
print(f"  DID: did:nil:{public_key_compressed.hex()}")
print()
print(f"EXPECTED:")
print(f"  DID: did:nil:03ecd47816bb8f475734b77aa9a3f4cc19a6075f3f603de0eebe6e11a784bb2e2d")
print("=" * 70)
