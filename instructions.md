## Hypothesis (DiabetesDAO Research Agent)

**HYP-MC-01**

> Women with T1D show a measurable rise in glucose and insulin needs during the luteal phase. Without cycle-aware dosing, this produces periods of hyperglycemia and occasional overnight crashes from over-correction. Cycle-aware recommendations improve stability.
> 

---

## Research Agent → HPMP Query

- **Agent:** DiabetesDAO_ResearchAgent_v1
- **Purpose:** Validate cycle-phase insulin variability.
- **Inclusion criteria:** Women 18–45 with T1D, CGM + cycle tracking available.
- **Data requested:**
    - Menstrual cycle phase (LMP → phase) [LOINC 8665-2]
    - CGM night glucose (00:00–06:00) [LOINC 15074-8]
    - Basal insulin units [LOINC 97507-8]
    - Insulin delivery method [LOINC 96706-0]
    - Sleep awakenings [LOINC 80372-6]


### workflow input as json
```json
{
  "hypothesis": "Hypothesis: Women with T1D show a measurable rise in glucose and insulin needs during the luteal phase. Without cycle-aware dosing, this produces periods of hyperglycemia and occasional overnight crashes from over-correction. Cycle-aware recommendations improve stability. Inclusion Criteria for the study are: Women 18-45 with T1D, CGM + cycle tracking available.",
  "studyName": "HYP-MC-01: Validate cycle-phase insulin variability",
  "studyDescription": "We're asking the cohort matching the inclusion criteria to share further data that helps verifying the hypothesis"
}

```


##  Matching Process

- **HPMP matches** profiles from two surveys:
    - Flo App (cycle, symptoms, sleep)
    - DiabetesDAO survey (insulin, CGM, delivery method)
    - The HPMP links:
        - Flo’s cycle/symptom data (LOINC-coded).
        - DAO’s insulin/CGM data (also stored under their Welshare profile).
- **Overlap set:** 187 matched profiles with valid cycle + CGM + insulin data.

## Synthetic Demo Output

**Comparison: Luteal vs Follicular nights**

- Mean glucose: **+8.1 mg/dL** in luteal
- Nighttime TIR (70–180 mg/dL): **−6.4 pp**
- Basal insulin dose: **+14%** in luteal
- Glucose variability (CV): **+3.2 pp**

**Subset of 64 patients who tried cycle-aware adjustments (−10–20% basal on flagged nights):**

- TIR ↑ 7.8 pp
- Mean glucose ↓ 7.3 mg/dL
- Hypoglycemia (<70) no increase

---

## Cohort Definition (Demo)

**Population:**

- **Women with Type 1 Diabetes**
- Age: **18–45 years** (reproductive age range, consistent with cycle studies)
- Data available:
    - **Cycle tracking** (Flo → LMP, phase, regularity)
    - **CGM data** (night glucose metrics, variability)
    - **Insulin logs** (basal units, delivery method)

**Sample size (synthetic):**

- Total matched profiles: **187** (k-anonymity safe, demo-friendly size)
- Split into:
    - **120 pump users** (≈65%)
    - **67 injection users** (≈35%)

**CGM baseline (synthetic):**

- Follicular: Mean night glucose ~118 mg/dL, TIR ~75%
- Luteal: Mean night glucose ~126 mg/dL, TIR ~68%
- Variability: +3–4% CV in luteal

**Insulin dose (synthetic):**

- Follicular: 14.0 units basal/night (avg)
- Luteal: 16.0 units basal/night (≈+14%)

**Subgroup (intervention):**

- 64 users who tried cycle-aware basal adjustment (−10–20% on flagged nights).
- Outcomes:
    - Nighttime TIR ↑ +7.8%
    - Mean glucose ↓ −7.3 mg/dL
    - Hypo rate: unchanged (safe).
