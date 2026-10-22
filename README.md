# Warnings on Top

What the rise of "artificial intelligence" in Form 10-K annual reports, 2015 to 2026,
is made of: a preregistered, blinded measurement audit with a cross-filer phrase-reuse
detector. Formerly titled "The Boilerplate Decade".

**Paper:** [`paper/ai-disclosure-trend-audit.pdf`](paper/ai-disclosure-trend-audit.pdf) ·
**Preregistration:** [`docs/PREREGISTRATION.md`](docs/PREREGISTRATION.md) ·
**Every sentence and verdict:** [`docs/browser.html`](docs/browser.html) ·
**Human validation materials:** [`data/human_validation/`](data/human_validation/) ·
**Pilot study (2025 only):** [ai-claims-audit](https://github.com/ishaanshah101/ai-claims-audit)

---

## The result

The share of 10-K filings containing "artificial intelligence" rose from 0.50 percent
in 2015 to 49.2 percent in 2025 and 60.5 percent in 2026 to date. Across 315 sampled
filings and 2,242 AI sentences, design-weighted:

| per AI-mentioning filing | 2015 to 2019 | 2020 to 2023 | 2024 to 2026 |
|---|---:|---:|---:|
| capability claims (mean sentences) | 1.8 | 3.7 | 3.8 |
| risk-factor sentences (mean) | 0.3 | 1.0 | 6.4 |
| all AI sentences (mean) | 3.9 | 8.0 | 13.7 |
| share of AI sentences that are risk | 12.0% | 18.4% | 63.0% |
| share of AI sentences in Item 1A | 13.7% | 9.2% | 46.6% |
| filings with any own-use statement | 61.6% | 71.9% | 61.5% |
| filings with a substantive own-use statement | 59.8% | 70.0% | 50.5% |
| mention-to-assertion ratio (substantive) | 1.67 | 1.43 | 1.98 |

- **Risk language was added on top.** Capability claims per filing doubled, and risk
  sentences rose nineteen-fold, supplying 63 percent of the added volume. The falling
  capability share is dilution, not substitution.
- **Fewer filers assert use than the count implies.** On a substantive definition the
  own-use share fell from 60 to 51 percent (interval on the change includes zero).
  Holding the amount of AI text constant, recent filers are far less likely to assert
  use (odds ratio 0.21, interval 0.07 to 0.58).
- **Verbatim boilerplate is rare and is risk language.** No capability sentence is
  shared with five or more other registrants, against 18.4 percent of risk
  sentences.

The labels come from blinded language-model raters, checked against known answers
and a blinded model review but **not yet against human coders**. A stratified,
blinded sample of 300 sentences and a scoring script are published for that.

![Mean AI sentences per filing by class and era](figures/fig7_counts.png)

## Revision history

- **18 October 2026:** first version, preregistered, six dated amendments.
- **22 October 2026:** second revision after an independent referee-style review.
  Reframed from "inversion" to "addition", added a substantive own-use definition, a
  length adjustment, calibration propagated to the filing level, 10-K item tags,
  within-firm reuse, a deviations table, an AI-use statement and a human-validation
  sample, and cut the paper by about 40 percent. Recorded as Amendment 7.

## Reproducing it

```bash
pip install -r requirements.txt
./run_all.sh                    # analysis from the committed judgements
REBUILD_CORPUS=1 ./run_all.sh   # re-enumerate EDGAR and rebuild the corpus
./paper/build.sh                # rebuild the PDF (pandoc + xelatex)
```

`src/verify_paper.py` recomputes the headline era estimates, the filing-level
fractions and the corpus counts directly from the committed labels, checks every
other number quoted in the paper against `results/analysis.json` and
`results/revision2.json`, and exits non-zero on any mismatch. It runs **211 checks
with zero failures**. The item tags in `src/revision2.py` need the downloaded 10-K
documents, which `src/fetch_and_extract.py` reproduces.

## Layout

```
src/frame.py              enumerate the twelve yearly frames
src/denominators.py       count all 10-Ks per year from the EDGAR full index
src/sample_filings.py     seeded draw, one filing per registrant per year
src/fetch_and_extract.py  download main documents, split, extract AI sentences
src/term_audit.py         name-only and entity-suffix screens, apply verdicts
src/build_rating_sets.py  redact, shuffle, assign, insert controls
src/rating_status.py      which batches still lack output
src/validate_ratings.py   schema-check all 5,240 judgements
src/agreement.py          agreement, alpha, controls, leakage
src/third_pass.py         build and merge the third pass
src/build_calibration.py  build and score the blinded calibration
src/phrase_reuse.py       cross-filer phrase reuse against all of EDGAR
src/xbrl_size.py          total assets per filing from the XBRL API
src/analyze.py            the first-revision estimates
src/revision2.py          second-revision analyses (counts, substantive own use, items)
src/figures_rev2.py       figures 7 and 8
src/human_validation.py   build and score the human-validation sample
src/figures.py            figures
src/build_browser.py      the sentence browser page
src/verify_paper.py       recompute the headline numbers, check every quoted one, fail loudly
src/stats.py              Wilson, alpha, bootstrap helpers, self-checks

data/frame.json           all frame filings, twelve years, with raw hits
data/denominators.json    10-K counts per year
data/sample_filings.json  the 315 drawn filings
data/sentences.json       the 2,590 extracted sentences with term-audit flags
data/term_audit_*.json    screen candidates and the blinded verdicts
data/rating/              blinded items, all 108 batch files and outputs,
                          controls key, labels, third-pass sets and outputs
data/calibration/         blinded materials, key, reviewer judgements
data/phrase_reuse.json    reuse counts, L=12 (and phrase_reuse_L8.json)
data/phrase_pilot.json    the window-length pilot on the companion corpus
data/xbrl_size.json       total assets per filing
data/btos/                Census BTOS sector file and the extracted AI series
results/                  agreement.json, calibration.json, analysis.json,
                          analysis_unweighted.json (pooled-sample comparison)
data/companion_values.json the companion study's figures used for comparison
docs/PREREGISTRATION.md   written before sampling, with dated amendments 1 to 7
docs/HUMAN_CODING_GUIDE.md instructions for the two human coders
data/human_validation/    blinded coding sheets for 300 sentences and the sealed key
docs/RATER_PROMPT.md      the literal rater prompt, committed before dispatch
docs/PHRASE_PILOT.md      the pilot that fixed the window length
docs/REFERENCES_VERIFIED.md every reference, with the record it was checked against
docs/browser.html         every sentence with its verdicts, filterable
```

Raw 10-K documents (about 1.5 GB) are not committed, and `src/fetch_and_extract.py`
reproduces them from the accession numbers in `data/sample_filings.json`.

## AI use

The rating passes, the third pass, the term-audit read and the calibration reviewer
are language models, not people: six rater identities, each a separate instance of
a mid-sized commercial model, two per sentence, for the blind passes, one more
instance of that model for the term-audit read, a larger model from the same family
for the third pass, and the largest model in that family, which orchestrated the
study, for the calibration review.
Model identities and versions are recorded in a private model log and are available
from the author. No figure here should be read as human inter-rater agreement.
Every sentence and every judgement is published so that a reader who disputes a call
can look at the sentence and say so.

Beyond the measurement, an AI agent working under the author's direction proposed the
design, wrote the code, and drafted the preregistration and the paper. The paper's
AI-use statement gives the details.

## License

MIT, see [LICENSE](LICENSE). SEC filings are public domain works of the United States
government, and sentences quoted from them are reproduced for analysis. Census BTOS data
are public.
