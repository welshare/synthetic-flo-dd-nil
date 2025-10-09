#!/usr/bin/env python3
"""
Cohort CSV Exporter
Converts generated FHIR QuestionnaireResponse files into a single CSV for verification
"""

import argparse
import csv
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
                "subject_id": subject_id,
                "questionnaire_id": None,
                "response_id": response.get("id"),
                "authored": response.get("authored")
            }

        # Determine questionnaire type and extract data
        questionnaire_id = response.get("questionnaire")

        if questionnaire_id == "38a97cfa-532d-4a38-9541-c9f366a6e1ed":  # Flo
            flo_data = parse_flo_response(response)
            patients[subject_id].update(flo_data)
            patients[subject_id]["flo_response_id"] = response.get("id")
            patients[subject_id]["flo_authored"] = response.get("authored")
        elif questionnaire_id == "dbb1ea85-af98-4a86-b2a1-39fb656462da":  # DAO
            dao_data = parse_dao_response(response)
            patients[subject_id].update(dao_data)
            patients[subject_id]["dao_response_id"] = response.get("id")
            patients[subject_id]["dao_authored"] = response.get("authored")

    # Calculate cycle phase for each patient
    for patient_id, patient_data in patients.items():
        if "lmp_date" in patient_data:
            patient_data["cycle_phase"] = calculate_cycle_phase(patient_data["lmp_date"])

    return list(patients.values())


def export_to_csv(cohort_data: List[Dict[str, Any]], output_path: Path):
    """Export cohort data to CSV file"""
    if not cohort_data:
        print("No data to export")
        return

    # Define CSV columns
    fieldnames = [
        "subject_id",
        "age",
        "delivery_method",
        "lmp_date",
        "cycle_length",
        "cycle_phase",
        "basal_insulin",
        "nighttime_glucose",
        "flo_response_id",
        "flo_authored",
        "dao_response_id",
        "dao_authored"
    ]

    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for patient in cohort_data:
            writer.writerow(patient)

    print(f"Exported {len(cohort_data)} patients to {output_path}")


def print_statistics(cohort_data: List[Dict[str, Any]]):
    """Print basic statistics about the cohort"""
    if not cohort_data:
        print("No data to analyze")
        return

    follicular = [p for p in cohort_data if p.get("cycle_phase") == "follicular"]
    luteal = [p for p in cohort_data if p.get("cycle_phase") == "luteal"]
    pump_users = [p for p in cohort_data if p.get("delivery_method") == "Insulin pump"]

    print("\nCohort Summary:")
    print("=" * 70)
    print(f"Total patients: {len(cohort_data)}")
    print(f"Follicular phase: {len(follicular)}")
    print(f"Luteal phase: {len(luteal)}")
    print(f"Pump users: {len(pump_users)} ({len(pump_users)/len(cohort_data)*100:.1f}%)")

    if follicular:
        avg_fol_glucose = sum(p.get("nighttime_glucose", 0) for p in follicular) / len(follicular)
        avg_fol_insulin = sum(p.get("basal_insulin", 0) for p in follicular) / len(follicular)
        print(f"\nFollicular avg: {avg_fol_glucose:.1f} mg/dL glucose, {avg_fol_insulin:.1f} units insulin")

    if luteal:
        avg_lut_glucose = sum(p.get("nighttime_glucose", 0) for p in luteal) / len(luteal)
        avg_lut_insulin = sum(p.get("basal_insulin", 0) for p in luteal) / len(luteal)
        print(f"Luteal avg: {avg_lut_glucose:.1f} mg/dL glucose, {avg_lut_insulin:.1f} units insulin")

        if follicular:
            print(f"Difference: +{avg_lut_glucose - avg_fol_glucose:.1f} mg/dL glucose, +{avg_lut_insulin - avg_fol_insulin:.1f} units insulin")


def main():
    """Main CLI execution"""
    parser = argparse.ArgumentParser(
        description='Convert synthetic cohort FHIR responses to CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           Convert cohort to cohort.csv
  %(prog)s --output my_cohort.csv    Save to custom file
  %(prog)s --stats                   Show statistics only
  %(prog)s --dir custom_output/      Read from custom directory
        """
    )

    parser.add_argument(
        '--output',
        '-o',
        type=Path,
        default=Path("cohort.csv"),
        help='Output CSV file path (default: cohort.csv)'
    )

    parser.add_argument(
        '--dir',
        type=Path,
        default=OUTPUT_DIR,
        help='Input directory containing JSON files (default: output/)'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only (no CSV output)'
    )

    args = parser.parse_args()

    # Validate input directory
    if not args.dir.exists():
        print(f"Error: Input directory does not exist: {args.dir}")
        return 1

    # Load cohort data
    print(f"Reading cohort data from {args.dir}/...")
    cohort_data = load_cohort_data(args.dir)

    if not cohort_data:
        print("No questionnaire response files found")
        return 1

    # Show statistics
    print_statistics(cohort_data)

    # Export to CSV (unless stats-only mode)
    if not args.stats:
        print("\n" + "=" * 70)
        export_to_csv(cohort_data, args.output)

    return 0


if __name__ == "__main__":
    exit(main())
