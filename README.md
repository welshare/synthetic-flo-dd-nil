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
  "questionnaire": "https://welshare.health/hpmp/questionnaire/flo-cycle-v2",
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
  "questionnaire": "https://welshare.health/hpmp/questionnaire/dao-diabetes-insulin-cgm-v2",
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

## Use Case

This synthetic cohort provides realistic test data for:
- Privacy-preserving profile matching systems
- Clinical research on menstrual cycle effects on diabetes management
- FHIR QuestionnaireResponse processing
- Aggregate analysis of cycle-aware insulin dosing
