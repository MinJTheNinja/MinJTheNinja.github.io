# Minjong Sung — Economics Research

Public portfolio: https://minjtheninja.github.io/

## Site structure

- `index.html`: research index, concise findings and interpretation limits, about.
- `cps-duration.html`: full CPS analysis, estimates, robustness, interactive tables and downloads.
- `ai-exposure.html`: summary of the original [AI exposure study](https://minjtheninja.github.io/ai_immigrant_labor/).
- `notebook.html`: two method notes, six concepts, two explicitly untested research questions.
- `journal.html`: dated clarifications, retrospective notes and site updates.
- `portfolio.css` / `portfolio.js`: shared responsive styles, theme preference and concept search.

Existing study URLs and analysis outputs are retained. Notebook entries link to the exact supporting sections. Retrospective explanations are labelled with their compilation date; analysis dates remain distinct. No respondent-level data are published.

## Update the portfolio

Edit the static HTML pages. Use the same notebook format: definition or question, interpretation, limits, and a source link. Add only populated navigation destinations. Give proposed extensions an explicit untested status. Add journal entries when evidence or framing changes; include the old statement, clarified statement and supporting source where applicable.

The site is served by GitHub Pages from the existing repository. No frontend build or external dependencies are required. HTML content and evidence links work without JavaScript; theme controls and concept search enhance the pages when JavaScript is enabled.

## Reproduce the CPS analysis

1. Obtain the official [Basic Monthly CPS files and layouts](https://www.census.gov/data/datasets/time-series/demo/cps/cps-basic.html) for 2011–2025. October 2025 is absent; do not bridge the missing adjacent-month pairs. Use corrected January–July 2020 source files where available.
2. Obtain the [2018 Census occupation workbook](https://www2.census.gov/programs-surveys/demo/guidance/industry-occupation/2018-occupation-code-list-and-crosswalk.xlsx).
3. Install dependencies from `requirements.txt`.
4. Run:

```sh
python build_panel.py --cps-dir /path/to/monthly-zips --crosswalk /path/to/2018-occupation-code-list-and-crosswalk.xlsx
python analyze.py
python render_chapter.py
```

The maintained generator writes `cps-duration.html`, leaving the homepage intact. Keep `portfolio.css` and `portfolio.js` beside the chapter. The downloadable `reproduction.zip` remains the archived 8 October 2026 analysis snapshot; maintained source files are in this repository.

The primary outcome is entry into an unambiguously below-BA occupation among linked baseline jobseekers. The conditional below-BA share among resolved reemployment events has a different denominator. Baseline weights are cross-sectional; person-cluster inference does not reproduce the complete CPS survey design. The 2025 education classification is applied throughout the historical period. No causal duration or occupational-concession effect is identified.

## Verification and changes

1 November 2026: connected the research index, notebook and journal; clarified exposure wording; preserved the existing CPS numerical outputs; separated the report generator from the homepage. Changes to presentation and retrospective explanation do not constitute a new empirical analysis.
