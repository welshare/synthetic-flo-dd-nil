#!/usr/bin/env python3
"""
Upload synthetic T1D cohort to Nillion nilDB
Exports generated QuestionnaireResponse files to Nillion's encrypted storage
"""

import json
import os
import argparse
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


from secretvaults import SecretVaults, NillionUserCredentials



class NillionUploader:
    """Uploads synthetic cohort data to Nillion nilDB"""

    def __init__(self, builder_private_key: str, collection_id: str, nildb_nodes: List[str] = None):
        """
        Initialize Nillion uploader

        Args:
            builder_private_key: Builder's private key for creating NUCs
            collection_id: Target collection ID in nilDB
            nildb_nodes: List of nilDB node URLs (defaults to 3 standard nodes)
        """
        self.builder_private_key = builder_private_key
        self.collection_id = collection_id

        # Default nilDB nodes (update based on Nillion docs)
        if nildb_nodes is None:
            self.nildb_nodes = [
                "https://nildb-stg-n1.nillion.network",
                "https://nildb-stg-n2.nillion.network",
                "https://nildb-stg-n3.nillion.network"
            ]
        else:
            self.nildb_nodes = nildb_nodes

        # Initialize SecretVaults client
        self.client = SecretVaults(nodes=self.nildb_nodes)

    def create_nuc_for_user(self, user_private_key: str) -> NillionUserCredentials:
        """
        Create Nillion User Credentials (NUC) for a synthetic patient

        Args:
            user_private_key: Patient's secp256k1 private key (hex)

        Returns:
            NillionUserCredentials object
        """
        # Create NUC using builder's key to authorize the user's key
        nuc = self.client.create_user_credentials(
            builder_private_key=self.builder_private_key,
            user_private_key=user_private_key
        )
        return nuc

    def upload_patient_responses(
        self,
        patient_id: str,
        flo_response: Dict[str, Any],
        dao_response: Dict[str, Any],
        nuc: NillionUserCredentials
    ) -> Dict[str, str]:
        """
        Upload patient's questionnaire responses to nilDB

        Args:
            patient_id: Patient DID
            flo_response: Flo cycle questionnaire response
            dao_response: DiabetesDAO questionnaire response
            nuc: Nillion User Credentials for this patient

        Returns:
            Dict with document IDs for uploaded responses
        """
        # Upload Flo response
        flo_doc_id = self.client.store_document(
            collection_id=self.collection_id,
            document=flo_response,
            user_credentials=nuc,
            metadata={"patient_id": patient_id, "questionnaire": "flo-cycle-v2"}
        )

        # Upload DAO response
        dao_doc_id = self.client.store_document(
            collection_id=self.collection_id,
            document=dao_response,
            user_credentials=nuc,
            metadata={"patient_id": patient_id, "questionnaire": "dao-diabetes-insulin-cgm-v2"}
        )

        return {
            "patient_id": patient_id,
            "flo_document_id": flo_doc_id,
            "dao_document_id": dao_doc_id
        }

    def upload_single_patient(self, patient_did: str, output_dir: Path) -> Dict[str, str]:
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

        # Create NUC for this patient
        nuc = self.create_nuc_for_user(key_material["private_key"])

        # Upload responses
        result = self.upload_patient_responses(
            patient_id=patient_did,
            flo_response=flo_response,
            dao_response=dao_response,
            nuc=nuc
        )

        return result

    def upload_cohort_from_directory(self, output_dir: Path) -> List[Dict[str, str]]:
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

        for idx, key_file in enumerate(key_files, 1):
            # Extract patient ID from filename
            patient_pubkey = key_file.stem.replace(".key", "")
            patient_id = f"did:nil:{patient_pubkey}"

            print(f"[{idx}/{total_patients}] Uploading patient: {patient_id[:30]}...")

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

            # Create NUC for this patient
            try:
                nuc = self.create_nuc_for_user(key_material["private_key"])
            except Exception as e:
                print(f"  ERROR: Failed to create NUC: {e}")
                continue

            # Upload responses
            try:
                result = self.upload_patient_responses(
                    patient_id=patient_id,
                    flo_response=flo_response,
                    dao_response=dao_response,
                    nuc=nuc
                )
                upload_results.append(result)
                print(f"  ✓ Uploaded (Flo: {result['flo_document_id'][:16]}..., DAO: {result['dao_document_id'][:16]}...)")
            except Exception as e:
                print(f"  ERROR: Upload failed: {e}")
                continue

        return upload_results


def main():
    """Main CLI execution"""
    parser = argparse.ArgumentParser(
        description='Upload synthetic T1D cohort to Nillion nilDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload entire cohort
  %(prog)s --collection-id abc123

  # Upload single patient by DID
  %(prog)s --collection-id abc123 --did did:nil:03a1b2c3d4...

  # Upload from custom directory
  %(prog)s --collection-id abc123 --dir custom_output/

  # Save manifest to custom file
  %(prog)s --collection-id abc123 --save-manifest manifest.json

Environment Variables:
  NILLION_BUILDER_PRIVATE_KEY    Builder's private key for creating NUCs (required)
  NILLION_COLLECTION_ID          Default collection ID (optional, can use --collection-id)

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

    # Get collection ID
    collection_id = args.collection_id or os.getenv('NILLION_COLLECTION_ID')
    if not collection_id:
        print("ERROR: Collection ID required")
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

            result = uploader.upload_single_patient(args.did, output_dir)

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
            upload_results = uploader.upload_cohort_from_directory(output_dir)

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


if __name__ == "__main__":
    main()
