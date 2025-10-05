#!/usr/bin/env python3
"""
Test Key Derivation Against Known Test Vectors

This test verifies that the Python implementation of the Ethereum-to-Nillion
key derivation matches the expected output from the TypeScript implementation.

Test vectors are loaded from .env file:
- TEST_USER_PRIVATE_KEY: Known Ethereum private key
- TEST_USER_ACCOUNT: Expected Ethereum address (for verification)
- TEST_USER_DERIVED_NILLION_DID: Expected derived did:nil identity
"""

import os
from dotenv import load_dotenv
from eth_account import Account
from key_derivation import (
    derive_nillion_keypair,
    SessionKeyAuthMessage,
    verify_derived_keypair
)

# Load test vectors from environment
load_dotenv()


def test_ethereum_account_derivation():
    """Test that we can correctly recreate the Ethereum account from private key"""
    print("=" * 70)
    print("TEST 1: Ethereum Account Derivation")
    print("=" * 70)

    test_private_key = os.getenv("TEST_USER_PRIVATE_KEY")
    expected_address = os.getenv("TEST_USER_ACCOUNT")

    if not test_private_key or not expected_address:
        print("❌ FAILED: Missing TEST_USER_PRIVATE_KEY or TEST_USER_ACCOUNT in .env")
        return False

    # Convert hex string to bytes
    private_key_bytes = bytes.fromhex(test_private_key)

    # Derive Ethereum account
    Account.enable_unaudited_hdwallet_features()
    eth_account = Account.from_key(private_key_bytes)

    print(f"Test Private Key: {test_private_key[:16]}...{test_private_key[-16:]}")
    print(f"Expected Address: {expected_address}")
    print(f"Derived Address:  {eth_account.address}")

    if eth_account.address == expected_address:
        print("✅ PASSED: Ethereum address matches expected value")
        print()
        return True
    else:
        print(f"❌ FAILED: Address mismatch!")
        print()
        return False


def test_nillion_keypair_derivation():
    """Test that the Nillion keypair derivation matches expected DID"""
    print("=" * 70)
    print("TEST 2: Nillion Keypair Derivation from Ethereum Key")
    print("=" * 70)

    test_private_key = os.getenv("TEST_USER_PRIVATE_KEY")
    expected_did = os.getenv("TEST_USER_DERIVED_NILLION_DID")

    if not test_private_key or not expected_did:
        print("❌ FAILED: Missing TEST_USER_PRIVATE_KEY or TEST_USER_DERIVED_NILLION_DID in .env")
        return False

    # Convert hex string to bytes
    private_key_bytes = bytes.fromhex(test_private_key)

    # Create authentication message for storage key derivation
    # This matches the TypeScript deriveStorageKeypair function
    auth_message = SessionKeyAuthMessage(
        key_id="1",
        context="nillion"
    )

    print(f"Auth Message:")
    print(f"  keyId: {auth_message.key_id}")
    print(f"  context: {auth_message.context}")
    print()

    # Derive Nillion keypair
    print("Deriving Nillion keypair...")
    nillion_keypair = derive_nillion_keypair(
        ethereum_private_key=private_key_bytes,
        auth_message=auth_message,
        user_secret="user@secret.com"
    )

    print(f"Expected DID:    {expected_did}")
    print(f"Derived DID:     {nillion_keypair.did}")
    print()
    print(f"Derived Details:")
    print(f"  Nillion Private Key: {nillion_keypair.private_key.hex()[:32]}...")
    print(f"  Nillion Public Key (compressed): {nillion_keypair.public_key_compressed.hex()[:32]}...")
    print(f"  EIP-712 Signature: {nillion_keypair.eip712_signature.hex()[:32]}...")
    print()

    if nillion_keypair.did == expected_did:
        print("✅ PASSED: Derived DID matches expected value")
        print()
        return True
    else:
        print(f"❌ FAILED: DID mismatch!")
        print()
        return False


def test_derivation_is_deterministic():
    """Test that the derivation is deterministic (same input = same output)"""
    print("=" * 70)
    print("TEST 3: Deterministic Derivation Verification")
    print("=" * 70)

    test_private_key = os.getenv("TEST_USER_PRIVATE_KEY")

    if not test_private_key:
        print("❌ FAILED: Missing TEST_USER_PRIVATE_KEY in .env")
        return False

    private_key_bytes = bytes.fromhex(test_private_key)

    auth_message = SessionKeyAuthMessage(
        key_id="1",
        context="nillion"
    )

    # Derive keypair twice
    print("Deriving keypair (attempt 1)...")
    keypair1 = derive_nillion_keypair(
        ethereum_private_key=private_key_bytes,
        auth_message=auth_message,
        user_secret="user@secret.com"
    )

    print("Deriving keypair (attempt 2)...")
    keypair2 = derive_nillion_keypair(
        ethereum_private_key=private_key_bytes,
        auth_message=auth_message,
        user_secret="user@secret.com"
    )

    print()
    print(f"Attempt 1 DID: {keypair1.did}")
    print(f"Attempt 2 DID: {keypair2.did}")
    print()

    # Check all components match
    checks = [
        ("DID", keypair1.did == keypair2.did),
        ("Private Key", keypair1.private_key == keypair2.private_key),
        ("Public Key (compressed)", keypair1.public_key_compressed == keypair2.public_key_compressed),
        ("Public Key (uncompressed)", keypair1.public_key_uncompressed == keypair2.public_key_uncompressed),
        ("EIP-712 Signature", keypair1.eip712_signature == keypair2.eip712_signature)
    ]

    all_match = True
    for check_name, result in checks:
        status = "✓" if result else "✗"
        print(f"{status} {check_name}: {'Match' if result else 'Mismatch'}")
        if not result:
            all_match = False

    print()
    if all_match:
        print("✅ PASSED: Derivation is deterministic")
        print()
        return True
    else:
        print("❌ FAILED: Derivation is not deterministic")
        print()
        return False


def test_verification_function():
    """Test that the verification function works correctly"""
    print("=" * 70)
    print("TEST 4: Verification Function")
    print("=" * 70)

    test_private_key = os.getenv("TEST_USER_PRIVATE_KEY")

    if not test_private_key:
        print("❌ FAILED: Missing TEST_USER_PRIVATE_KEY in .env")
        return False

    private_key_bytes = bytes.fromhex(test_private_key)

    auth_message = SessionKeyAuthMessage(
        key_id="1",
        context="nillion"
    )

    # Derive keypair
    print("Deriving keypair...")
    keypair = derive_nillion_keypair(
        ethereum_private_key=private_key_bytes,
        auth_message=auth_message,
        user_secret="user@secret.com"
    )

    # Verify it
    print("Verifying derived keypair...")
    is_valid = verify_derived_keypair(keypair, private_key_bytes)

    print()
    if is_valid:
        print("✅ PASSED: Verification function confirms keypair is valid")
        print()
        return True
    else:
        print("❌ FAILED: Verification function failed")
        print()
        return False


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "KEY DERIVATION TEST SUITE" + " " * 28 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    results = []

    # Run all tests
    results.append(("Ethereum Account Derivation", test_ethereum_account_derivation()))
    results.append(("Nillion Keypair Derivation", test_nillion_keypair_derivation()))
    results.append(("Deterministic Derivation", test_derivation_is_deterministic()))
    results.append(("Verification Function", test_verification_function()))

    # Print summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")

    print()
    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)

    if passed_tests == total_tests:
        print(f"🎉 ALL TESTS PASSED ({passed_tests}/{total_tests})")
        print()
        return 0
    else:
        print(f"⚠️  SOME TESTS FAILED ({passed_tests}/{total_tests} passed)")
        print()
        return 1


if __name__ == "__main__":
    exit(main())
