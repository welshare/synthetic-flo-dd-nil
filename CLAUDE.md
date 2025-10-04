# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Synthetic Type 1 Diabetes (T1D) patient cohort generator that creates FHIR QuestionnaireResponse resources for research on menstrual cycle effects on insulin needs. This tool validates hypothesis HYP-MC-01: women with T1D show measurable glucose and insulin variability between follicular and luteal phases.

## Commands

### Setup
```bash
pip install -r requirements.txt
```

### Generate Cohort
```bash
# Default: 187 patients (374 response files)
python3 synth_cohort.py

# Custom cohort size
python3 synth_cohort.py 200

# With different random seed
python3 synth_cohort.py 150 --seed 123

# Show statistics only (no file output)
python3 synth_cohort.py 187 --stats

# Clean all generated files
python3 synth_cohort.py clean
```

### Upload to Nillion nilDB
```bash
# Upload entire cohort to Nillion
python3 upload_to_nildb.py --collection-id <collection_id>

# Upload single patient by DID
python3 upload_to_nildb.py --collection-id <collection_id> --did did:nil:03a1b2c3d4...

# Upload from custom directory
python3 upload_to_nildb.py --collection-id <collection_id> --dir custom_output/

# Save upload manifest to custom file
python3 upload_to_nildb.py --collection-id <collection_id> --save-manifest manifest.json

# Use custom nilDB nodes
python3 upload_to_nildb.py --collection-id <collection_id> --nildb-nodes https://node1.com https://node2.com
```

**Required Environment Variables:**
- `NILLION_BUILDER_PRIVATE_KEY`: Builder's private key for creating NUCs (Nillion User Credentials)
- `NILLION_COLLECTION_ID` (optional): Default collection ID

**How it works:**
1. Creates one NUC per synthetic patient using their secp256k1 private key
2. Uploads both questionnaire responses (Flo + DAO) to the specified collection
3. Generates an upload manifest JSON with all document IDs

### No Tests
This project does not currently have tests.

## Architecture

### Data Flow

1. **Input**: Two FHIR Questionnaire definitions (`fhir/` directory)
   - `flo-cycle-v2.fhir.json`: Menstrual cycle tracking (LMP date, cycle length)
   - `dao-diabetes-insulin-cgm-v2.fhir.json`: Insulin delivery & nighttime CGM data

2. **Generator Core** (`synth_cohort.py`):
   - `SyntheticCohortGenerator` class orchestrates patient generation
   - Each patient gets a decentralized identifier (DID): `did:welshare:{uuid}`
   - Generates **phase-correlated data**: menstrual cycle phase determines glucose/insulin values

3. **Output**: Individual FHIR QuestionnaireResponse files
   - Format: `output/{patient_id}_flo.json` and `output/{patient_id}_dao.json`
   - Each patient produces 2 files (one per questionnaire)
   - All files in `output/` are git-ignored

### Key Statistical Correlations

The generator creates realistic cycle-phase-dependent data:

- **Cycle Phase Determination**: Based on days since LMP (days 1-14 = follicular, 15-28 = luteal)
- **Follicular Phase**: ~118 mg/dL glucose, ~14 units basal insulin
- **Luteal Phase**: ~126 mg/dL glucose (+8 mg/dL), ~16 units basal insulin (+14%)
- **Delivery Method Split**: 65% insulin pump users, 35% multiple daily injections
- **Age Range**: 18-45 years (reproductive age)

### Critical Implementation Detail

**Phase-correlated generation** (synth_cohort.py:228-234): The same cycle phase that's calculated from the LMP date is used to generate both glucose and insulin values. This ensures synthetic patients have realistic correlations between their cycle phase and diabetes metrics, not independent random values.

## Project Context

This synthetic dataset supports testing of:
- Privacy-preserving profile matching systems (HPMP)
- Research queries that join data from multiple questionnaires via patient DID
- FHIR QuestionnaireResponse processing pipelines
- Hypothesis validation for cycle-aware insulin dosing recommendations

Statistical targets from `instructions.md`:
- 187 matched profiles (k-anonymity safe)
- Luteal vs Follicular comparison showing ~8 mg/dL glucose difference
- Subset analysis of 64 patients who tried cycle-aware adjustments
