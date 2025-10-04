#!/usr/bin/env python3
"""
Synthetic T1D Cohort Generator CLI
Generates FHIR QuestionnaireResponse resources for synthetic patients
"""

import json
import uuid
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random
import numpy as np


class SyntheticCohortGenerator:
    """Generates synthetic patient cohort with questionnaire responses"""

    def __init__(self, cohort_size: int, seed: int = 42):
        """
        Initialize generator

        Args:
            cohort_size: Total number of patients
            seed: Random seed for reproducibility
        """
        random.seed(seed)
        np.random.seed(seed)

        self.cohort_size = cohort_size
        self.pump_users = int(cohort_size * 0.65)  # ~65% pump users
        self.injection_users = cohort_size - self.pump_users  # ~35% injection users

        # Statistical parameters from instructions.md
        self.follicular_glucose_mean = 118  # mg/dL
        self.luteal_glucose_mean = 126  # mg/dL
        self.glucose_std = 12

        self.follicular_basal_mean = 14.0  # units
        self.luteal_basal_mean = 16.0  # units (+14%)
        self.basal_std = 3.0

        self.age_min = 18
        self.age_max = 45

        self.cycle_length_mean = 28
        self.cycle_length_std = 3

    def generate_patient_id(self) -> str:
        """Generate random UID for patient"""
        return f"did:welshare:{uuid.uuid4()}"

    def generate_delivery_method(self, patient_idx: int) -> str:
        """Assign insulin delivery method (65% pump, 35% injection)"""
        if patient_idx < self.pump_users:
            return "Insulin pump"
        return "Multiple daily injections"

    def generate_age(self) -> int:
        """Generate age between 18-45 (reproductive age)"""
        return random.randint(self.age_min, self.age_max)

    def determine_cycle_phase(self, lmp_date: datetime, reference_date: datetime) -> str:
        """
        Determine menstrual cycle phase based on days since LMP
        Follicular: Days 1-14
        Luteal: Days 15-28
        """
        days_since_lmp = (reference_date - lmp_date).days % 28
        return "follicular" if days_since_lmp <= 14 else "luteal"

    def generate_lmp_date(self, reference_date: datetime = None) -> str:
        """Generate last menstrual period date"""
        if reference_date is None:
            reference_date = datetime.now()

        days_ago = random.randint(1, 28)
        lmp_date = reference_date - timedelta(days=days_ago)
        return lmp_date.strftime("%Y-%m-%d")

    def generate_cycle_length(self) -> int:
        """Generate typical cycle length (normal distribution around 28 days)"""
        cycle_length = int(np.random.normal(self.cycle_length_mean, self.cycle_length_std))
        return max(21, min(35, cycle_length))

    def generate_basal_insulin(self, phase: str) -> float:
        """
        Generate basal insulin dose based on cycle phase
        Follicular: ~14.0 units
        Luteal: ~16.0 units (≈+14%)
        """
        if phase == "follicular":
            dose = np.random.normal(self.follicular_basal_mean, self.basal_std)
        else:  # luteal
            dose = np.random.normal(self.luteal_basal_mean, self.basal_std)

        return round(max(5.0, dose), 1)

    def generate_cgm_glucose(self, phase: str) -> float:
        """
        Generate nighttime (00:00-06:00) average CGM glucose based on cycle phase
        Follicular: ~118 mg/dL
        Luteal: ~126 mg/dL (+8.1 mg/dL)
        """
        if phase == "follicular":
            glucose = np.random.normal(self.follicular_glucose_mean, self.glucose_std)
        else:  # luteal
            glucose = np.random.normal(self.luteal_glucose_mean, self.glucose_std)

        return round(max(70.0, min(250.0, glucose)), 1)

    def create_flo_response(self, patient_id: str, lmp_date: str, cycle_length: int) -> Dict[str, Any]:
        """Create FHIR QuestionnaireResponse for Flo Cycle questionnaire"""
        return {
            "resourceType": "QuestionnaireResponse",
            "id": str(uuid.uuid4()),
            "questionnaire": "https://welshare.health/hpmp/questionnaire/flo-cycle-v2",
            "status": "completed",
            "subject": {
                "reference": patient_id
            },
            "authored": datetime.now().isoformat() + "Z",
            "item": [
                {
                    "linkId": "lmp",
                    "text": "When did your last menstrual period begin?",
                    "answer": [
                        {
                            "valueDate": lmp_date
                        }
                    ]
                },
                {
                    "linkId": "cycle-length",
                    "text": "What is your typical cycle length (days)?",
                    "answer": [
                        {
                            "valueInteger": cycle_length
                        }
                    ]
                }
            ]
        }

    def create_dao_response(
        self,
        patient_id: str,
        delivery_method: str,
        basal_dose: float,
        cgm_glucose: float,
        age: int
    ) -> Dict[str, Any]:
        """Create FHIR QuestionnaireResponse for DiabetesDAO questionnaire"""
        return {
            "resourceType": "QuestionnaireResponse",
            "id": str(uuid.uuid4()),
            "questionnaire": "https://welshare.health/hpmp/questionnaire/dao-diabetes-insulin-cgm-v2",
            "status": "completed",
            "subject": {
                "reference": patient_id
            },
            "authored": datetime.now().isoformat() + "Z",
            "item": [
                {
                    "linkId": "delivery-method",
                    "text": "Which insulin delivery method do you use?",
                    "answer": [
                        {
                            "valueString": delivery_method
                        }
                    ]
                },
                {
                    "linkId": "basal-dose-24h",
                    "text": "What is your total basal insulin over 24 hours (units/day)?",
                    "answer": [
                        {
                            "valueDecimal": basal_dose
                        }
                    ]
                },
                {
                    "linkId": "cgm-avg-0006",
                    "text": "What was your average CGM glucose from 00:00-06:00 (nighttime) over your usual reporting period?",
                    "answer": [
                        {
                            "valueDecimal": cgm_glucose
                        }
                    ]
                },
                {
                    "linkId": "age",
                    "text": "Age (years)",
                    "answer": [
                        {
                            "valueInteger": age
                        }
                    ]
                }
            ]
        }

    def generate_cohort(self) -> List[Dict[str, Any]]:
        """
        Generate complete synthetic cohort with both questionnaire responses

        Returns:
            List of patient records, each containing:
            - patient_id
            - flo_response
            - dao_response
            - metadata
        """
        cohort = []
        reference_date = datetime.now()

        for i in range(self.cohort_size):
            # Generate patient identity
            patient_id = self.generate_patient_id()

            # Generate Flo cycle data
            lmp_date_str = self.generate_lmp_date(reference_date)
            lmp_date = datetime.strptime(lmp_date_str, "%Y-%m-%d")
            cycle_length = self.generate_cycle_length()
            phase = self.determine_cycle_phase(lmp_date, reference_date)

            # Generate DiabetesDAO data (phase-dependent)
            delivery_method = self.generate_delivery_method(i)
            age = self.generate_age()
            basal_dose = self.generate_basal_insulin(phase)
            cgm_glucose = self.generate_cgm_glucose(phase)

            # Create questionnaire responses
            flo_response = self.create_flo_response(patient_id, lmp_date_str, cycle_length)
            dao_response = self.create_dao_response(
                patient_id, delivery_method, basal_dose, cgm_glucose, age
            )

            # Compile patient record
            patient_record = {
                "patient_id": patient_id,
                "flo_response": flo_response,
                "dao_response": dao_response,
                "metadata": {
                    "age": age,
                    "delivery_method": delivery_method,
                    "cycle_phase": phase,
                    "lmp_date": lmp_date_str,
                    "cycle_length": cycle_length,
                    "basal_insulin": basal_dose,
                    "nighttime_glucose": cgm_glucose
                }
            }

            cohort.append(patient_record)

        return cohort

    def calculate_statistics(self, cohort: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate cohort statistics"""
        follicular_patients = [p for p in cohort if p["metadata"]["cycle_phase"] == "follicular"]
        luteal_patients = [p for p in cohort if p["metadata"]["cycle_phase"] == "luteal"]
        pump_patients = [p for p in cohort if p["metadata"]["delivery_method"] == "Insulin pump"]
        injection_patients = [p for p in cohort if p["metadata"]["delivery_method"] == "Multiple daily injections"]

        stats = {
            "total_patients": len(cohort),
            "follicular_count": len(follicular_patients),
            "luteal_count": len(luteal_patients),
            "pump_users": len(pump_patients),
            "injection_users": len(injection_patients),
            "follicular_stats": {
                "mean_glucose": np.mean([p["metadata"]["nighttime_glucose"] for p in follicular_patients]),
                "mean_basal": np.mean([p["metadata"]["basal_insulin"] for p in follicular_patients]),
            },
            "luteal_stats": {
                "mean_glucose": np.mean([p["metadata"]["nighttime_glucose"] for p in luteal_patients]),
                "mean_basal": np.mean([p["metadata"]["basal_insulin"] for p in luteal_patients]),
            },
            "age_range": {
                "min": min(p["metadata"]["age"] for p in cohort),
                "max": max(p["metadata"]["age"] for p in cohort),
                "mean": np.mean([p["metadata"]["age"] for p in cohort])
            }
        }

        return stats


def main():
    """Main CLI execution"""
    parser = argparse.ArgumentParser(
        description='Generate synthetic T1D patient cohort with FHIR QuestionnaireResponses',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 187                    Generate 187 patients (default)
  %(prog)s 200 -o cohort.json    Generate 200 patients, save to cohort.json
  %(prog)s 150 --seed 123         Generate 150 patients with seed 123
  %(prog)s 187 --stats            Show statistics only
        """
    )

    parser.add_argument(
        'cohort_size',
        type=int,
        nargs='?',
        default=187,
        help='Number of patients to generate (default: 187)'
    )

    parser.add_argument(
        '-o', '--output',
        type=str,
        default='synthetic_cohort.json',
        help='Output file path (default: synthetic_cohort.json)'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only (no file output)'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress output messages'
    )

    args = parser.parse_args()

    # Validate cohort size
    if args.cohort_size < 1:
        parser.error("Cohort size must be at least 1")

    # Generate cohort
    if not args.quiet:
        print(f"Generating synthetic T1D cohort...")
        print("=" * 70)

    generator = SyntheticCohortGenerator(cohort_size=args.cohort_size, seed=args.seed)
    cohort = generator.generate_cohort()
    stats = generator.calculate_statistics(cohort)

    # Display statistics
    if not args.quiet or args.stats:
        print(f"\nCohort Statistics:")
        print(f"  Total patients: {stats['total_patients']}")
        print(f"  Follicular phase: {stats['follicular_count']}")
        print(f"  Luteal phase: {stats['luteal_count']}")
        print(f"  Pump users: {stats['pump_users']} ({stats['pump_users']/stats['total_patients']*100:.1f}%)")
        print(f"  Injection users: {stats['injection_users']} ({stats['injection_users']/stats['total_patients']*100:.1f}%)")
        print(f"\nFollicular Phase (avg):")
        print(f"  Nighttime glucose: {stats['follicular_stats']['mean_glucose']:.1f} mg/dL")
        print(f"  Basal insulin: {stats['follicular_stats']['mean_basal']:.1f} units")
        print(f"\nLuteal Phase (avg):")
        print(f"  Nighttime glucose: {stats['luteal_stats']['mean_glucose']:.1f} mg/dL")
        print(f"  Basal insulin: {stats['luteal_stats']['mean_basal']:.1f} units")
        print(f"\nDifference (Luteal - Follicular):")
        print(f"  Glucose: +{stats['luteal_stats']['mean_glucose'] - stats['follicular_stats']['mean_glucose']:.1f} mg/dL")
        print(f"  Basal insulin: +{stats['luteal_stats']['mean_basal'] - stats['follicular_stats']['mean_basal']:.1f} units")
        print(f"\nAge range: {stats['age_range']['min']}-{stats['age_range']['max']} (mean: {stats['age_range']['mean']:.1f})")

    # Save cohort
    if not args.stats:
        with open(args.output, 'w') as f:
            json.dump(cohort, f, indent=2)

        if not args.quiet:
            print("\n" + "=" * 70)
            print(f"Saved {len(cohort)} patient records to {args.output}")


if __name__ == "__main__":
    main()
