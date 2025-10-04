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

### Options

```bash
python3 synth_cohort.py [cohort_size] [options]

Arguments:
  cohort_size              Number of patients to generate (default: 187)

Options:
  -o, --output FILE       Output file path (default: synthetic_cohort.json)
  --seed SEED             Random seed for reproducibility (default: 42)
  --stats                 Show statistics only (no file output)
  --quiet                 Suppress output messages
  -h, --help              Show help message
```

### Examples

```bash
# Generate 200 patients
python3 synth_cohort.py 200

# Save to custom file
python3 synth_cohort.py 187 -o my_cohort.json

# Use different random seed
python3 synth_cohort.py 150 --seed 123

# Show statistics only (no file output)
python3 synth_cohort.py 187 --stats

# Quiet mode
python3 synth_cohort.py 200 --quiet
```

## Output Structure

Each patient record contains:

```json
{
  "patient_id": "did:welshare:...",
  "flo_response": {
    "resourceType": "QuestionnaireResponse",
    "questionnaire": "https://welshare.health/hpmp/questionnaire/flo-cycle-v2",
    "item": [...]
  },
  "dao_response": {
    "resourceType": "QuestionnaireResponse",
    "questionnaire": "https://welshare.health/hpmp/questionnaire/dao-diabetes-insulin-cgm-v2",
    "item": [...]
  },
  "metadata": {
    "age": 32,
    "delivery_method": "Insulin pump",
    "cycle_phase": "luteal",
    "lmp_date": "2025-09-20",
    "cycle_length": 28,
    "basal_insulin": 16.2,
    "nighttime_glucose": 127.5
  }
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
