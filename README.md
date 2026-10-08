# Graduate unemployment duration and below-BA reemployment

Exploratory monthly CPS analysis, 2011–2025. Outcome is the education threshold
of the actual next-month primary occupation, using BLS typical entry education.
Both birth groups are age 25–64 with BA or higher and actively looking at baseline.

## Reproduce

1. Obtain the official ZIPs `jan11pub.zip` through `dec25pub.zip` from
   https://www.census.gov/data/datasets/time-series/demo/cps/cps-basic.html.
   October 2025 does not exist. Do not bridge its missing adjacent-month pairs.
   Use the revised January–July 2020 source files where available.
2. Obtain the official 2018 Census occupation workbook:
   https://www2.census.gov/programs-surveys/demo/guidance/industry-occupation/2018-occupation-code-list-and-crosswalk.xlsx
3. Install dependencies: `python -m pip install -r requirements.txt`.
4. Run:

```sh
python build_panel.py --cps-dir /path/to/monthly-zips --crosswalk /path/to/2018-occupation-code-list-and-crosswalk.xlsx
python analyze.py
python render_chapter.py
```

`panel.csv.gz` is an intermediate respondent-level file; it is not included in
the public outputs or reproduction archive. The scripts read raw inputs without
modification. They write only beside the scripts (or build_panel.py --out).
If using --out, put the analysis scripts in the same output directory before running.

## Public outputs

- `duration_rates.csv`: weighted descriptive rates and nominal clustered intervals.
- `duration_rates_unweighted.csv`: corresponding unweighted rates.
- `occupation_crosswalk.csv`: vintage-specific mapping and unresolved categories.
- `linkage_diagnostics.csv`: scheduled follow-up and retention by birth group/duration.
- `results.json`: adjusted models, sensitivity estimates, multinomial predictions.
- `input_manifest.json`: source ZIP sizes, member CRCs and duplicate diagnostics.
- `bls_thresholds.py`: all 831 BLS occupations, classified at the BA threshold.
- `versions.json`: package versions used in this execution.

BLS Table 5.4 public HTML, 2025 vintage, was read 2026-10-08:
https://www.bls.gov/emp/tables/education-and-training-by-occupation.htm
The threshold transcription was validated against the observed table using
FNV-1a hashes of sorted comma-separated SOC codes: all `a64b743f`, BA+ `d54ebd6d`.

## Estimands and limitations

Primary: next-month entry into an unambiguously below-BA occupation among all
valid linked baseline jobseekers. Conditional: below-BA share among resolved
reemployment events. Do not substitute the second for the first.

Baseline final CPS weights are cross-sectional, not calibrated longitudinal
weights. Person-cluster uncertainty does not reproduce the full survey design.
Main linear probability models use exact baseline year-month effects.
Multinomial competing risks use year and calendar-month effects and retain
unresolved employment as a fifth outcome. Both include age, age squared, sex,
degree, rotation controls, log2(1 + duration), nativity, and their interaction.

Strict birth comparison: PRCITSHP 4/5 vs 1. Categories 2/3 excluded.
Baseline MIS 1/2/3/5/6/7; follow-up MIS +1, stable sex and group, age +0/+1.
Baseline eligibility is retained across age/education changes at follow-up.
Only consecutive observed months are linked. Duration is already elapsed;
complete unemployment spells are not observed for every respondent.

2025 BLS requirements are applied to the whole historical period. Mixed and
unmapped occupational codes are not assigned arbitrarily. Broad numeric SOC
groups and published combined BLS occupations are expanded conservatively;
residual Census X groups exclude separately coded precise SOC occupations.
Older codes require agreement across all newer Census-code destinations.

The revision status of local 2020 files was not independently established
against a newly retrieved source checksum. An exclusion of 2020–2021 is reported.
No causal duration, immigration, or occupational-concession effect is claimed.
