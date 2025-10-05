# Synthetic T1D Cohort Generator

Generates synthetic patient cohort with FHIR QuestionnaireResponse resources for Type 1 Diabetes menstrual cycle research.

## Overview

This CLI tool creates FHIR QuestionnaireResponse resources for synthetic patients responding to two questionnaires:

1. **Flo App** - Menstrual cycle tracking (LMP date, cycle length)
2. **DiabetesDAO** - Insulin & nighttime CGM data (delivery method, basal insulin, glucose)

The synthetic data matches the statistical distributions specified in `instructions.md` for validating cycle-phase insulin variability (Hypothesis HYP-MC-01).

## Features

- Configurable cohort size
- Decentralized identifiers (DIDs) for patient privacy
- **~65% pump users / ~35% injection users** distribution
- **Cycle phase matching**: Correlates menstrual cycle phase with glucose/insulin patterns
- **Probabilistic generation**:
  - Follicular phase: ~118 mg/dL glucose, ~14 units basal insulin
  - Luteal phase: ~126 mg/dL glucose (+8 mg/dL), ~16 units basal insulin (+14%)
- **Age range**: 18-45 years (reproductive age)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Generate 187 patients (default):
```bash
python3 synth_cohort.py
```

Generate custom cohort size:
```bash
python3 synth_cohort.py 200
```

Clean output directory:
```bash
python3 synth_cohort.py clean
```

### Options

```bash
python3 synth_cohort.py [command|cohort_size] [options]

Arguments:
  command|cohort_size     Command (clean) or number of patients (default: 187)

Options:
  --seed SEED             Random seed for reproducibility (default: 42)
  --stats                 Show statistics only (no file output)
  --quiet                 Suppress output messages
  -h, --help              Show help message
```

### Examples

```bash
# Generate 200 patients (creates 400 response files)
python3 synth_cohort.py 200

# Use different random seed
python3 synth_cohort.py 150 --seed 123

# Show statistics only (no file output)
python3 synth_cohort.py 187 --stats

# Quiet mode
python3 synth_cohort.py 200 --quiet

# Clean all generated files
python3 synth_cohort.py clean
```

### Output Structure

Each patient generates **2 individual response files** in the `output/` directory:

```
output/
├── {patient_id}_flo.json    # Flo cycle questionnaire response
├── {patient_id}_dao.json    # DiabetesDAO questionnaire response
├── ...
```

For example, generating 187 patients creates **374 files** (187 × 2).

All files in `output/` are git-ignored. Use `python3 synth_cohort.py clean` to remove all generated files.

## File Format

Each file contains a single FHIR QuestionnaireResponse resource:

**Example: `{patient_id}_flo.json`**
```json
{
  "resourceType": "QuestionnaireResponse",
  "id": "...",
  "questionnaire": "38a97cfa-532d-4a38-9541-c9f366a6e1ed",
  "status": "completed",
  "subject": {
    "reference": "did:welshare:..."
  },
  "authored": "2025-10-04T...",
  "item": [
    {
      "linkId": "lmp",
      "text": "When did your last menstrual period begin?",
      "answer": [{"valueDate": "2025-09-20"}]
    },
    {
      "linkId": "cycle-length",
      "text": "What is your typical cycle length (days)?",
      "answer": [{"valueInteger": 28}]
    }
  ]
}
```

**Example: `{patient_id}_dao.json`**
```json
{
  "resourceType": "QuestionnaireResponse",
  "id": "...",
  "questionnaire": "dbb1ea85-af98-4a86-b2a1-39fb656462da",
  "status": "completed",
  "subject": {
    "reference": "did:welshare:..."
  },
  "authored": "2025-10-04T...",
  "item": [
    {
      "linkId": "delivery-method",
      "answer": [{"valueString": "Insulin pump"}]
    },
    {
      "linkId": "basal-dose-24h",
      "answer": [{"valueDecimal": 16.2}]
    },
    {
      "linkId": "cgm-avg-0006",
      "answer": [{"valueDecimal": 127.5}]
    },
    {
      "linkId": "age",
      "answer": [{"valueInteger": 32}]
    }
  ]
}
```

## Statistical Validation

The generator ensures:
- **Glucose difference**: Luteal phase ~8 mg/dL higher than follicular
- **Basal insulin**: ~14% increase in luteal phase
- **Delivery method split**: ~65% pumps, ~35% injections
- **Cycle phase distribution**: Random but realistic based on LMP dates

## Questionnaire Definitions

FHIR Questionnaire resources are located in `fhir/`:
- `flo-cycle-v2.fhir.json` - Flo App menstrual cycle questionnaire (LOINC: 8665-2, 64700-8)
- `dao-diabetes-insulin-cgm-v2.fhir.json` - DiabetesDAO insulin/CGM questionnaire (LOINC: 41936-6, 41944-0, 97507-8, 30525-0)

## Uploading to Nillion nilDB

After generating the synthetic cohort, you can upload the questionnaire responses to Nillion's encrypted storage using `upload_to_nildb.py`. The scripts are designed to work sequentially for easier debugging.

### Setup

1. **Configure environment variables** in `.env`:
```bash
# Required
NILLION_BUILDER_PRIVATE_KEY=your_builder_private_key_here

# Optional (use defaults if not specified)
NILLION_COLLECTION_ID=your_collection_id
NILCHAIN_URL=http://rpc.testnet.nilchain-rpc-proxy.nilogy.xyz
NILAUTH_URL=https://nilauth.sandbox.app-cluster.sandbox.nilogy.xyz
NILDB_NODES=https://nildb-stg-n1.nillion.network,https://nildb-stg-n2.nillion.network,https://nildb-stg-n3.nillion.network
```

2. **Install additional dependencies** (if not already installed):
```bash
pip install -r requirements.txt
```

### Workflow: Generate → Upload

```bash
# Step 1: Generate synthetic cohort
python3 synth_cohort.py 187

# Step 2: Upload entire cohort to Nillion
python3 upload_to_nildb.py --collection-id <collection_id>
```

### Upload Options

**Upload entire cohort:**
```bash
python3 upload_to_nildb.py --collection-id abc123
```

**Upload single patient by DID:**
```bash
python3 upload_to_nildb.py --collection-id abc123 --did did:nil:03a1b2c3d4e5f6...
```

**Upload from custom directory:**
```bash
python3 upload_to_nildb.py --collection-id abc123 --dir custom_output/
```

**Save upload manifest to custom file:**
```bash
python3 upload_to_nildb.py --collection-id abc123 --save-manifest my_manifest.json
```

**Use custom nilDB nodes:**
```bash
python3 upload_to_nildb.py --collection-id abc123 --nildb-nodes https://node1.com https://node2.com https://node3.com
```

**Delete a document:**
```bash
python3 upload_to_nildb.py --did did:nil:03a1b2c3d4e5f6... --delete <document_id>
```

### How Upload Works

1. **NUC Creation**: For each synthetic patient, the script creates a Nillion User Credential (NUC) using their secp256k1 private key from the `.key.json` file
2. **Document Upload**: Both questionnaire responses (Flo + DAO) are uploaded to the specified collection with ACL permissions
3. **Manifest Generation**: An upload manifest JSON file is created containing all document IDs for later retrieval
4. **Authentication**: Delete operations use the user's DID and private key to authenticate

### Upload Manifest Format

The upload creates a JSON manifest (`upload_manifest.json` by default) with the following structure:

```json
{
  "collection_id": "abc123",
  "total_patients": 187,
  "uploads": [
    {
      "patient_id": "did:nil:03a1b2c3d4e5f6...",
      "flo_document_id": "doc_flo_123...",
      "dao_document_id": "doc_dao_456..."
    },
    ...
  ]
}
```

### Common Upload Patterns

**Full pipeline with verification:**
```bash
# Clean previous data
python3 synth_cohort.py clean

# Generate fresh cohort
python3 synth_cohort.py 187

# Upload to Nillion
python3 upload_to_nildb.py --collection-id abc123

# Verify manifest was created
cat upload_manifest.json
```

**Test with small cohort first:**
```bash
# Generate small test cohort
python3 synth_cohort.py 5 --seed 999

# Upload test cohort
python3 upload_to_nildb.py --collection-id test_collection --save-manifest test_manifest.json
```

## Use Case

This synthetic cohort provides realistic test data for:
- Privacy-preserving profile matching systems
- Clinical research on menstrual cycle effects on diabetes management
- FHIR QuestionnaireResponse processing
- Aggregate analysis of cycle-aware insulin dosing
- Testing Nillion nilDB encrypted storage and retrieval
