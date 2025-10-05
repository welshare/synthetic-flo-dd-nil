#!/usr/bin/env python3
"""
Upload synthetic T1D cohort to Nillion nilDB
Exports generated QuestionnaireResponse files to Nillion's encrypted storage
"""

import json
import os
import argparse
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from secretvaults.builder import SecretVaultBuilderClient
from secretvaults.user import SecretVaultUserClient
from secretvaults.common.keypair import Keypair
from secretvaults.common.blindfold import BlindfoldFactoryConfig, BlindfoldOperation
from secretvaults.dto.data import CreateOwnedDataRequest
from secretvaults.dto.users import AclDto, DeleteDocumentRequestParams
from nuc.builder import NucTokenBuilder
from nuc.token import Command
from secretvaults.common.nuc_cmd import NucCmd 



def into_seconds_from_now(minutes: int) -> int:
    """Convert minutes from now into Unix timestamp"""
    return int((datetime.now() + timedelta(minutes=minutes)).timestamp())


class NillionUploader:
    """Uploads synthetic cohort data to Nillion nilDB"""

    def __init__(
        self,
        builder_private_key: str,
        collection_id: str,
        nilchain_url: str = None,
        nilauth_url: str = None,
        nildb_nodes: List[str] = None
    ):
        """
        Initialize Nillion uploader

        Args:
            builder_private_key: Builder's private key (hex format)
            collection_id: Target collection ID in nilDB
            nilchain_url: Nillion chain URL
            nilauth_url: Nillion auth URL
            nildb_nodes: List of nilDB node URLs
        """
        self.builder_keypair = Keypair.from_hex(builder_private_key)
        self.collection_id = collection_id

        # Default URLs for staging environment
        self.nilchain_url = nilchain_url or os.getenv("NILCHAIN_URL", "http://rpc.testnet.nilchain-rpc-proxy.nilogy.xyz")
        self.nilauth_url = nilauth_url or os.getenv("NILAUTH_URL", "https://nilauth.sandbox.app-cluster.sandbox.nilogy.xyz")

        # Default nilDB nodes
        if nildb_nodes is None:
            default_nodes = os.getenv("NILDB_NODES", "")
            if default_nodes:
                self.nildb_nodes = default_nodes.split(",")
            else:
                self.nildb_nodes = [
                    "https://nildb-stg-n1.nillion.network",
                    "https://nildb-stg-n2.nillion.network",
                    "https://nildb-stg-n3.nillion.network"
                ]
        else:
            self.nildb_nodes = nildb_nodes

    async def create_builder_client(self) -> SecretVaultBuilderClient:
        """Create and initialize builder client"""
        urls = {
            "chain": [self.nilchain_url],
            "auth": self.nilauth_url,
            "dbs": self.nildb_nodes,
        }

        builder_client = await SecretVaultBuilderClient.from_options(
            keypair=self.builder_keypair,
            urls=urls,
            blindfold=BlindfoldFactoryConfig(
                operation=BlindfoldOperation.STORE,
                use_cluster_key=True,
            ),
        )
        return builder_client

    async def create_user_client(self, user_private_key: str) -> SecretVaultUserClient:
        """
        Create user client from patient's private key

        Args:
            user_private_key: Patient's secp256k1 private key (hex)

        Returns:
            SecretVaultUserClient
        """
        user_keypair = Keypair.from_hex(user_private_key)

        user_client = await SecretVaultUserClient.from_options(
            keypair=user_keypair,
            base_urls=self.nildb_nodes,
            blindfold=BlindfoldFactoryConfig(
                operation=BlindfoldOperation.STORE,
                use_cluster_key=True,
            ),
        )
        return user_client

    async def upload_patient_responses(
        self,
        builder_client: SecretVaultBuilderClient,
        patient_id: str,
        user_private_key: str,
        flo_response: Dict[str, Any],
        dao_response: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Upload patient's questionnaire responses to nilDB

        Args:
            builder_client: Builder client instance
            patient_id: Patient DID
            user_private_key: Patient's private key
            flo_response: Flo cycle questionnaire response
            dao_response: DiabetesDAO questionnaire response

        Returns:
            Dict with document IDs for uploaded responses
        """
        # Create user client for this patient
        user_client = await self.create_user_client(user_private_key)

        # Refresh builder's root token
        await builder_client.refresh_root_token()
        root_token_envelope = builder_client.root_token

        # Create delegation token for data creation
        delegation_token = (
            NucTokenBuilder.extending(root_token_envelope)
            .command(Command(NucCmd.NIL_DB_DATA_CREATE.value.split(".")))
            .audience(user_client.id)
            .expires_at(datetime.fromtimestamp(into_seconds_from_now(60)))
            .build(builder_client.keypair.private_key())
        )

        # Upload Flo response
        flo_request = CreateOwnedDataRequest(
            collection=self.collection_id,
            owner=user_client.id,
            data=[flo_response],
            acl=AclDto(
                grantee=builder_client.keypair.to_did_string(),
                read=True,
                write=False,
                execute=True,
            ),
        )

        flo_result = await user_client.create_data(
            delegation=delegation_token,
            body=flo_request,
        )

        # Refresh delegation token for second upload
        await builder_client.refresh_root_token()
        delegation_token = (
            NucTokenBuilder.extending(builder_client.root_token)
            .command(Command(NucCmd.NIL_DB_DATA_CREATE.value.split(".")))
            .audience(user_client.id)
            .expires_at(datetime.fromtimestamp(into_seconds_from_now(60)))
            .build(builder_client.keypair.private_key())
        )

        # Upload DAO response
        dao_request = CreateOwnedDataRequest(
            collection=self.collection_id,
            owner=user_client.id,
            data=[dao_response],
            acl=AclDto(
                grantee=builder_client.keypair.to_did_string(),
                read=True,
                write=False,
                execute=True,
            ),
        )

        dao_result = await user_client.create_data(
            delegation=delegation_token,
            body=dao_request,
        )

        await user_client.close()

        return {
            "patient_id": patient_id,
            "flo_document_id": flo_result.ids[0] if flo_result.ids else None,
            "dao_document_id": dao_result.ids[0] if dao_result.ids else None,
        }

    async def delete_document(
        self,
        user_did: str,
        user_private_key: str,
        document_id: str
    ) -> Dict[str, Any]:
        """
        Delete a document from nilDB using user credentials

        Args:
            user_did: User's DID (format: did:nil:{pubkey})
            user_private_key: User's private key (hex)
            document_id: Document ID to delete

        Returns:
            Dict with deletion result
        """
        # Create builder client for delegation token
        async with await self.create_builder_client() as builder_client:
            # Create user client
            user_client = await self.create_user_client(user_private_key)

            # Refresh builder's root token
            await builder_client.refresh_root_token()
            root_token_envelope = builder_client.root_token

            # Create delegation token for data deletion
            delegation_token = (
                NucTokenBuilder.extending(root_token_envelope)
                .command(Command(NucCmd.NIL_DB_DATA_DELETE.value.split(".")))
                .audience(user_client.id)
                .expires_at(datetime.fromtimestamp(into_seconds_from_now(60)))
                .build(builder_client.keypair.private_key())
            )

            # Create delete request
            delete_request = DeleteDocumentRequestParams(
                collection=self.collection_id,
                document=document_id
            )

            # Delete the document
            await user_client.delete_data(delete_request)

            await user_client.close()

            return {
                "user_did": user_did,
                "document_id": document_id,
                "status": "deleted"
            }

    async def upload_single_patient(self, patient_did: str, output_dir: Path) -> Dict[str, str]:
        """
        Upload a single patient's responses to nilDB

        Args:
            patient_did: Patient DID (format: did:nil:{pubkey})
            output_dir: Path to directory containing generated files

        Returns:
            Upload result dict
        """
        # Extract public key from DID
        if not patient_did.startswith("did:nil:"):
            raise ValueError(f"Invalid DID format. Expected 'did:nil:{{pubkey}}', got: {patient_did}")

        patient_pubkey = patient_did.split(":")[-1]

        # Load key material
        key_file = output_dir / f"{patient_pubkey}.key.json"
        if not key_file.exists():
            raise FileNotFoundError(f"Key file not found: {key_file}")

        with open(key_file, 'r') as f:
            key_material = json.load(f)

        # Load questionnaire responses
        flo_file = output_dir / f"{patient_pubkey}_flo.json"
        dao_file = output_dir / f"{patient_pubkey}_dao.json"

        if not flo_file.exists():
            raise FileNotFoundError(f"Flo response not found: {flo_file}")
        if not dao_file.exists():
            raise FileNotFoundError(f"DAO response not found: {dao_file}")

        with open(flo_file, 'r') as f:
            flo_response = json.load(f)

        with open(dao_file, 'r') as f:
            dao_response = json.load(f)

        # Create builder client and upload
        async with await self.create_builder_client() as builder_client:
            result = await self.upload_patient_responses(
                builder_client=builder_client,
                patient_id=patient_did,
                user_private_key=key_material["nillion_private_key"],
                flo_response=flo_response,
                dao_response=dao_response,
            )

        return result

    async def upload_cohort_from_directory(self, output_dir: Path) -> List[Dict[str, str]]:
        """
        Upload all patients from output directory to nilDB

        Args:
            output_dir: Path to directory containing generated files

        Returns:
            List of upload results
        """
        # Find all key files
        key_files = list(output_dir.glob("*.key.json"))

        if not key_files:
            raise ValueError(f"No key files found in {output_dir}")

        upload_results = []
        total_patients = len(key_files)

        print(f"Found {total_patients} patients to upload")
        print("=" * 70)

        # Create builder client once for all uploads
        async with await self.create_builder_client() as builder_client:
            for idx, key_file in enumerate(key_files, 1):
                # Extract patient ID from filename
                patient_pubkey = key_file.stem.replace(".key", "")
                patient_id = f"did:nil:{patient_pubkey}"

                print(f"[{idx}/{total_patients}] Uploading patient: {patient_id[:50]}...")

                # Load key material
                with open(key_file, 'r') as f:
                    key_material = json.load(f)

                # Load questionnaire responses
                flo_file = output_dir / f"{patient_pubkey}_flo.json"
                dao_file = output_dir / f"{patient_pubkey}_dao.json"

                if not flo_file.exists() or not dao_file.exists():
                    print(f"  ERROR: Missing response files for {patient_id}")
                    continue

                with open(flo_file, 'r') as f:
                    flo_response = json.load(f)

                with open(dao_file, 'r') as f:
                    dao_response = json.load(f)

                # Upload responses
                try:
                    result = await self.upload_patient_responses(
                        builder_client=builder_client,
                        patient_id=patient_id,
                        user_private_key=key_material["nillion_private_key"],
                        flo_response=flo_response,
                        dao_response=dao_response,
                    )
                    upload_results.append(result)
                    flo_id = result['flo_document_id'][:16] if result['flo_document_id'] else 'N/A'
                    dao_id = result['dao_document_id'][:16] if result['dao_document_id'] else 'N/A'
                    print(f"  ✓ Uploaded (Flo: {flo_id}..., DAO: {dao_id}...)")
                except Exception as e:
                    print(f"  ERROR: Upload failed: {e}")
                    continue

        return upload_results


async def async_main():
    """Async main execution"""
    parser = argparse.ArgumentParser(
        description='Upload synthetic T1D cohort to Nillion nilDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload entire cohort
  %(prog)s --collection-id abc123

  # Upload single patient by DID
  %(prog)s --collection-id abc123 --did did:nil:03a1b2c3d4...

  # Delete a document
  %(prog)s --did did:nil:03a1b2c3d4... --delete doc_id_123

  # Upload from custom directory
  %(prog)s --collection-id abc123 --dir custom_output/

  # Save manifest to custom file
  %(prog)s --collection-id abc123 --save-manifest manifest.json

Environment Variables:
  NILLION_BUILDER_PRIVATE_KEY    Builder's private key for creating NUCs (required)
  NILLION_COLLECTION_ID          Default collection ID (optional, can use --collection-id)
  NILCHAIN_URL                   Nillion chain URL (optional)
  NILAUTH_URL                    Nillion auth URL (optional)
  NILDB_NODES                    Comma-separated nilDB node URLs (optional)

Output:
  Creates upload manifest JSON file with document IDs for all uploaded responses
        """
    )

    parser.add_argument(
        '--collection-id',
        type=str,
        help='Target collection ID in nilDB (or set NILLION_COLLECTION_ID env var)'
    )

    parser.add_argument(
        '--did',
        type=str,
        help='Upload only a single patient by their DID (format: did:nil:{pubkey})'
    )

    parser.add_argument(
        '--delete',
        type=str,
        metavar='DOCUMENT_ID',
        help='Delete a document by ID (requires --did for user authentication)'
    )

    parser.add_argument(
        '--dir',
        type=str,
        default='output',
        help='Directory containing generated cohort files (default: output)'
    )

    parser.add_argument(
        '--save-manifest',
        type=str,
        default='upload_manifest.json',
        help='Save upload results to JSON manifest (default: upload_manifest.json)'
    )

    parser.add_argument(
        '--nildb-nodes',
        nargs='+',
        help='Custom nilDB node URLs (space-separated)'
    )

    args = parser.parse_args()

    # Get builder private key from environment
    builder_key = os.getenv('NILLION_BUILDER_PRIVATE_KEY')
    if not builder_key:
        print("ERROR: NILLION_BUILDER_PRIVATE_KEY environment variable not set")
        print("Add it to your .env file or export it:")
        print('  export NILLION_BUILDER_PRIVATE_KEY="your_key_here"')
        exit(1)

    # Handle delete command
    if args.delete:
        if not args.did:
            print("ERROR: --did is required when using --delete")
            print("Usage: --did did:nil:03a1b2c3... --delete <document_id>")
            exit(1)

        # Extract user public key from DID
        user_pubkey = args.did.split(":")[-1]

        # Validate output directory for key file
        output_dir = Path(args.dir)
        if not output_dir.exists():
            print(f"ERROR: Directory not found: {output_dir}")
            exit(1)

        # Load user's private key
        key_file = output_dir / f"{user_pubkey}.key.json"
        if not key_file.exists():
            print(f"ERROR: Key file not found: {key_file}")
            print(f"Make sure the user DID exists in {output_dir}/")
            exit(1)

        with open(key_file, 'r') as f:
            key_material = json.load(f)

        uploader = NillionUploader(
            builder_private_key=builder_key,
            collection_id = args.collection_id or os.getenv('NILLION_COLLECTION_ID'),
            nildb_nodes=args.nildb_nodes
        )

        # Delete document
        try:
            print(f"Deleting document: {args.delete}")
            print(f"User DID: {args.did}")
            print("=" * 70)

            result = await uploader.delete_document(
                user_did=args.did,
                user_private_key=key_material["nillion_private_key"],
                document_id=args.delete
            )

            print(f"\n✓ Document deleted successfully!")
            print(f"  User: {result['user_did']}")
            print(f"  Document ID: {result['document_id']}")
            print(f"  Status: {result['status']}")

        except Exception as e:
            print(f"ERROR: Delete failed: {e}")
            import traceback
            traceback.print_exc()
            exit(1)

        return

    # Get collection ID (required for upload operations)
    collection_id = args.collection_id or os.getenv('NILLION_COLLECTION_ID')
    if not collection_id:
        print("ERROR: Collection ID required for upload operations")
        print("Provide via --collection-id or set NILLION_COLLECTION_ID env var")
        exit(1)

    # Validate output directory
    output_dir = Path(args.dir)
    if not output_dir.exists():
        print(f"ERROR: Directory not found: {output_dir}")
        exit(1)

    # Initialize uploader
    print("Initializing Nillion uploader...")
    print(f"  Collection ID: {collection_id}")
    print(f"  Output directory: {output_dir}")

    uploader = NillionUploader(
        builder_private_key=builder_key,
        collection_id=collection_id,
        nildb_nodes=args.nildb_nodes
    )

    # Upload single patient or entire cohort
    try:
        if args.did:
            # Upload single patient
            print(f"\nUploading single patient: {args.did}")
            print("=" * 70)

            result = await uploader.upload_single_patient(args.did, output_dir)

            print(f"\n✓ Upload successful!")
            print(f"  Patient: {result['patient_id']}")
            print(f"  Flo document ID: {result['flo_document_id']}")
            print(f"  DAO document ID: {result['dao_document_id']}")

            # Save manifest
            if args.save_manifest:
                manifest = {
                    "collection_id": collection_id,
                    "total_patients": 1,
                    "uploads": [result]
                }

                with open(args.save_manifest, 'w') as f:
                    json.dump(manifest, f, indent=2)

                print(f"\nManifest saved to: {args.save_manifest}")

        else:
            # Upload entire cohort
            upload_results = await uploader.upload_cohort_from_directory(output_dir)

            print("\n" + "=" * 70)
            print(f"Upload complete: {len(upload_results)} patients uploaded")

            # Save manifest
            if args.save_manifest:
                manifest = {
                    "collection_id": collection_id,
                    "total_patients": len(upload_results),
                    "uploads": upload_results
                }

                with open(args.save_manifest, 'w') as f:
                    json.dump(manifest, f, indent=2)

                print(f"Manifest saved to: {args.save_manifest}")

    except Exception as e:
        print(f"ERROR: Upload failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


def main():
    """Main CLI entry point"""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
