#!/usr/bin/env python3
"""
Cohort Analytics Script
Analyzes synthetic cohort and validates statistical properties
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


OUTPUT_DIR = Path("output")


def extract_answer_value(item: Dict[str, Any]) -> Any:
    """Extract the answer value from a FHIR item"""
    if "answer" not in item or not item["answer"]:
        return None

    answer = item["answer"][0]

    # Handle different value types
    if "valueDate" in answer:
        return answer["valueDate"]
    elif "valueInteger" in answer:
        return answer["valueInteger"]
    elif "valueDecimal" in answer:
        return answer["valueDecimal"]
    elif "valueString" in answer:
        return answer["valueString"]

    return None


def parse_flo_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract data from Flo questionnaire response"""
    data = {}

    for item in response.get("item", []):
        link_id = item.get("linkId")
        value = extract_answer_value(item)

        if link_id == "lmp":
            data["lmp_date"] = value
        elif link_id == "cycle-length":
            data["cycle_length"] = value

    return data


def parse_dao_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract data from DiabetesDAO questionnaire response"""
    data = {}

    for item in response.get("item", []):
        link_id = item.get("linkId")
        value = extract_answer_value(item)

        if link_id == "delivery-method":
            data["delivery_method"] = value
        elif link_id == "basal-dose-24h":
            data["basal_insulin"] = value
        elif link_id == "cgm-avg-0006":
            data["nighttime_glucose"] = value
        elif link_id == "age":
            data["age"] = value

    return data


def calculate_cycle_phase(lmp_date: str) -> str:
    """
    Calculate cycle phase based on days since LMP
    Follicular: Days 1-14, Luteal: Days 15-28
    """
    try:
        lmp = datetime.strptime(lmp_date, "%Y-%m-%d")
        reference_date = datetime.now()
        days_since_lmp = (reference_date - lmp).days % 28
        return "follicular" if days_since_lmp <= 14 else "luteal"
    except:
        return "unknown"


def load_cohort_data(input_dir: Path = OUTPUT_DIR) -> List[Dict[str, Any]]:
    """
    Load and combine questionnaire responses from all patients

    Returns:
        List of patient records with combined data from both questionnaires
    """
    patients = {}

    # Iterate through all JSON files
    for json_file in sorted(input_dir.glob("*.json")):
        # Skip .key.json files
        if json_file.name.endswith(".key.json"):
            continue

        with open(json_file, 'r') as f:
            response = json.load(f)

        # Extract subject ID (DID)
        subject_id = response.get("subject", {}).get("id")
        if not subject_id:
            continue

        # Initialize patient record if not exists
        if subject_id not in patients:
            patients[subject_id] = {
                "subject_id": subject_id
            }

        # Determine questionnaire type and extract data
        questionnaire_id = response.get("questionnaire")

        if questionnaire_id == "38a97cfa-532d-4a38-9541-c9f366a6e1ed":  # Flo
            flo_data = parse_flo_response(response)
            patients[subject_id].update(flo_data)
        elif questionnaire_id == "dbb1ea85-af98-4a86-b2a1-39fb656462da":  # DAO
            dao_data = parse_dao_response(response)
            patients[subject_id].update(dao_data)

    # Calculate cycle phase for each patient
    for patient_id, patient_data in patients.items():
        if "lmp_date" in patient_data:
            patient_data["cycle_phase"] = calculate_cycle_phase(patient_data["lmp_date"])

    return list(patients.values())


def analyze_cohort(cohort_data: List[Dict[str, Any]]):
    """
    Analyze cohort and compute key statistics

    Args:
        cohort_data: List of patient records
    """
    if not cohort_data:
        print("No data to analyze")
        return

    # Separate by cycle phase
    follicular_patients = [p for p in cohort_data if p.get("cycle_phase") == "follicular"]
    luteal_patients = [p for p in cohort_data if p.get("cycle_phase") == "luteal"]

    print("=" * 70)
    print("COHORT ANALYTICS")
    print("=" * 70)
    print()

    print(f"Total Patients: {len(cohort_data)}")
    print(f"  Follicular phase: {len(follicular_patients)} ({len(follicular_patients)/len(cohort_data)*100:.1f}%)")
    print(f"  Luteal phase: {len(luteal_patients)} ({len(luteal_patients)/len(cohort_data)*100:.1f}%)")
    print()

    # Compute follicular phase statistics
    if follicular_patients:
        follicular_glucose_values = [p.get("nighttime_glucose") for p in follicular_patients if p.get("nighttime_glucose") is not None]
        follicular_insulin_values = [p.get("basal_insulin") for p in follicular_patients if p.get("basal_insulin") is not None]

        mean_follicular_glucose = sum(follicular_glucose_values) / len(follicular_glucose_values) if follicular_glucose_values else 0
        mean_follicular_insulin = sum(follicular_insulin_values) / len(follicular_insulin_values) if follicular_insulin_values else 0

        print("FOLLICULAR PHASE STATISTICS")
        print("-" * 70)
        print(f"  Sample size: {len(follicular_patients)} patients")
        print(f"  Mean nighttime glucose: {mean_follicular_glucose:.2f} mg/dL")
        print(f"  Mean basal insulin: {mean_follicular_insulin:.2f} units/day")
        print()

    # Compute luteal phase statistics
    if luteal_patients:
        luteal_glucose_values = [p.get("nighttime_glucose") for p in luteal_patients if p.get("nighttime_glucose") is not None]
        luteal_insulin_values = [p.get("basal_insulin") for p in luteal_patients if p.get("basal_insulin") is not None]

        mean_luteal_glucose = sum(luteal_glucose_values) / len(luteal_glucose_values) if luteal_glucose_values else 0
        mean_luteal_insulin = sum(luteal_insulin_values) / len(luteal_insulin_values) if luteal_insulin_values else 0

        print("LUTEAL PHASE STATISTICS")
        print("-" * 70)
        print(f"  Sample size: {len(luteal_patients)} patients")
        print(f"  Mean nighttime glucose: {mean_luteal_glucose:.2f} mg/dL")
        print(f"  Mean basal insulin: {mean_luteal_insulin:.2f} units/day")
        print()

    # Compute differences (Luteal - Follicular)
    if follicular_patients and luteal_patients:
        glucose_diff = mean_luteal_glucose - mean_follicular_glucose
        insulin_diff = mean_luteal_insulin - mean_follicular_insulin
        glucose_diff_pct = (glucose_diff / mean_follicular_glucose * 100) if mean_follicular_glucose > 0 else 0
        insulin_diff_pct = (insulin_diff / mean_follicular_insulin * 100) if mean_follicular_insulin > 0 else 0

        print("PHASE COMPARISON (Luteal - Follicular)")
        print("-" * 70)
        print(f"  Nighttime glucose difference: {glucose_diff:+.2f} mg/dL ({glucose_diff_pct:+.1f}%)")
        print(f"  Basal insulin difference: {insulin_diff:+.2f} units/day ({insulin_diff_pct:+.1f}%)")
        print()

    # Additional cohort statistics
    all_ages = [p.get("age") for p in cohort_data if p.get("age") is not None]
    pump_users = [p for p in cohort_data if p.get("delivery_method") == "Insulin pump"]
    injection_users = [p for p in cohort_data if p.get("delivery_method") == "Multiple daily injections"]

    print("ADDITIONAL COHORT CHARACTERISTICS")
    print("-" * 70)
    if all_ages:
        print(f"  Age range: {min(all_ages)}-{max(all_ages)} years (mean: {sum(all_ages)/len(all_ages):.1f})")
    print(f"  Insulin pump users: {len(pump_users)} ({len(pump_users)/len(cohort_data)*100:.1f}%)")
    print(f"  Multiple daily injection users: {len(injection_users)} ({len(injection_users)/len(cohort_data)*100:.1f}%)")
    print()

    print("=" * 70)
    print("STATISTICAL VALIDATION")
    print("=" * 70)
    print()
    print("Expected values (from CLAUDE.md):")
    print("  Follicular: ~118 mg/dL glucose, ~14 units insulin")
    print("  Luteal: ~126 mg/dL glucose (+8 mg/dL), ~16 units insulin (+14%)")
    print("  Pump users: ~65%")
    print()

    # Validation checks
    if follicular_patients and luteal_patients:
        glucose_diff_target = 8.0
        insulin_pct_target = 14.0

        glucose_check = "✓" if abs(glucose_diff - glucose_diff_target) < 2.0 else "✗"
        insulin_check = "✓" if abs(insulin_diff_pct - insulin_pct_target) < 5.0 else "✗"
        pump_check = "✓" if abs(len(pump_users)/len(cohort_data) - 0.65) < 0.10 else "✗"

        print(f"{glucose_check} Glucose difference: {glucose_diff:.1f} mg/dL (target: ~{glucose_diff_target} mg/dL)")
        print(f"{insulin_check} Insulin difference: {insulin_diff_pct:.1f}% (target: ~{insulin_pct_target}%)")
        print(f"{pump_check} Pump users: {len(pump_users)/len(cohort_data)*100:.1f}% (target: ~65%)")
        print()

    print("=" * 70)


def main():
    """Main CLI execution"""
    parser = argparse.ArgumentParser(
        description='Analyze synthetic cohort statistics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    Analyze cohort from output/
  %(prog)s --dir custom/      Analyze cohort from custom directory
        """
    )

    parser.add_argument(
        '--dir',
        type=Path,
        default=OUTPUT_DIR,
        help='Input directory containing JSON files (default: output/)'
    )

    args = parser.parse_args()

    # Validate input directory
    if not args.dir.exists():
        print(f"Error: Input directory does not exist: {args.dir}")
        return 1

    # Load cohort data
    cohort_data = load_cohort_data(args.dir)

    if not cohort_data:
        print("No questionnaire response files found")
        return 1

    # Analyze cohort
    analyze_cohort(cohort_data)

    return 0


if __name__ == "__main__":
    exit(main())
