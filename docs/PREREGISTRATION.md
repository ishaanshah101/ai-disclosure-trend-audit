# Preregistration

**Study.** The Boilerplate Decade: how much of the rise in artificial-intelligence
language in annual reports is substantive, 2015 to 2026.

**Status.** Written before the sample was drawn and before any sentence was read or
scored. The only data consulted before writing this document are the yearly frame
counts in Section 3.1, which are population totals returned by EDGAR full-text search
and contain no sentence text. Every later change is recorded as a numbered, dated
amendment at the bottom of this file, with the reason.

**Relation to prior work by the same author.** The companion study
`ai-claims-audit` (September 2026) classified every AI sentence in 60 annual reports
filed in calendar 2025 and found that a calibrated 60.5 percent were risk-factor
language and 12.2 percent were claims about the registrant's own AI. Its limitations
section named three things it could not do: say anything about trend, log the rater
prompts, or detect boilerplate without a model reading every sentence. This study is
built to do those three things. It reuses the companion's five-class rubric, sentence
splitter and extraction rules without change so that the 2025 results are directly
comparable, and it adds one binary judgement, one computational measure and eleven
more years.

---

## 1. Why this question

Keyword counts of "artificial intelligence" in Form 10-K are used, by researchers,
by the financial press and by index providers, as a measure of how far AI has spread
through public companies. The count has risen by two orders of magnitude in a decade.
The question this study asks is what the count is counting. If most of the growth is
risk-factor and industry-commentary language that every registrant's counsel now adds
by default, then a mention is not an adoption, the trend in mentions overstates the
trend in adoption, and the overstatement grows with time. If instead the growth is
mostly companies describing their own use of AI, the keyword measure is roughly
honest. Either answer is useful. Nobody has measured which one is true across years.

## 2. Research questions

- **RQ1 (composition over time).** Of the sentences in a 10-K that mention AI, what
  fraction in each calendar year from 2015 to 2026 is a capability claim, risk-factor
  language, market description, governance description, or other, and what fraction
  states that the registrant itself uses or develops AI?
- **RQ2 (corrected adoption trend).** In each year, what share of all 10-K filers
  (a) mention AI at all, (b) contain at least one sentence stating their own use of
  AI, and (c) contain at least one capability claim? How large is the gap between (a)
  and (b), and does it grow over time?
- **RQ3 (a computational boilerplate detector).** Does the number of other registrants
  that have used the same phrase, measured against the whole EDGAR 10-K corpus,
  separate risk-factor and other non-substantive sentences from own-use and capability
  sentences? How well does a phrase-reuse threshold perform as a classifier of
  "not a statement of own use"?
- **RQ4 (sector).** Do own-use rates differ between technology, healthcare, finance
  and real estate, and other registrants, and does the ordering of sectors under the
  raw mention measure differ from the ordering under the own-use measure?
- **RQ5 (external anchor, exploratory).** How do sector-level rates under the raw
  mention measure and under the own-use measure compare with the share of businesses
  reporting AI use in the Census Bureau's Business Trends and Outlook Survey?

## 3. Corpus and sampling

### 3.1 The frame

For each calendar year Y from 2015 to 2026 (2026 through 2026-10-18, the day this
document was written), the frame is every filing with root form 10-K whose full text
matches the exact phrase "artificial intelligence" in EDGAR full-text search. EDGAR
returns one hit per document, so hits are collapsed to filings by accession number,
and the frame is restricted to filings in which the main 10-K document itself matched
rather than only an exhibit. Both counts are recorded. `src/frame.py` reproduces the
enumeration.

Frame sizes reported by EDGAR before collapsing to filings, as of 2026-10-18:

| year | 10-K hits, "artificial intelligence" | 10-K hits, "machine learning" |
|---|---:|---:|
| 2015 | 41 | 45 |
| 2016 | 52 | 64 |
| 2017 | 116 | 137 |
| 2018 | 294 | 244 |
| 2019 | 445 | 360 |
| 2020 | 558 | 439 |
| 2021 | 848 | 619 |
| 2022 | 1,156 | 867 |
| 2023 | 1,295 | 896 |
| 2024 | 2,436 | 1,243 |
| 2025 | 3,324 | 1,645 |
| 2026 to 18 Oct | 3,883 | 2,050 |

The 2025 figure is identical to the one the companion study enumerated on
2026-09-26, which is the expected behaviour of a closed index.

### 3.2 The denominator

The number of 10-K filings in each calendar year is taken from the EDGAR full index
(`form.idx` for each quarter), counting rows whose form type is exactly `10-K`.
`src/denominators.py` reproduces it. The raw mention share for year Y is the frame
size divided by this count.

### 3.3 The sample

Within each year, filings are collapsed to one per registrant (CIK), choosing at
random among a registrant's filings when it has more than one, and a simple random
sample of registrants is drawn without replacement under seed 20261018. The draw is
30 filings in each of 2015, 2016 and 2017 and 25 filings in each year from 2018 to
2026, 315 filings in all. Early years get more filings because early filings contain
fewer AI sentences. Within a year the draw is not stratified by sector, so that the
sample's sector mix tracks the frame's, which is itself part of the trend being
measured. Sector comparisons pool across years.

A registrant can be drawn in more than one year. That is allowed, recorded, and
reported.

### 3.4 Sentence extraction

Each filing's main document is downloaded from the EDGAR archives, stripped of markup
and split into sentences by the companion study's deterministic splitter, unchanged.
A sentence enters the corpus if it matches the AI term list, is between 60 and 1,200
characters, and is less than 25 percent digits by character. Those three rules are
the companion study's rules.

The term list is changed in exactly two ways from the companion study, both in
response to the false positives that study documented: the pattern `\bml\b` is
dropped, because it matched millilitres in pharmacology tables, and the standalone
abbreviation is matched case-sensitively as `\bAI\b` rather than case-insensitively.
The list is: "artificial intelligence", "artificial-intelligence", "machine
learning", "generative ai", "large language model", "deep learning", "neural
network", "foundation model", `\bgenai\b` (case-insensitive), and `\bAI\b`, `\bAI-`
(case-sensitive). The pattern that matched is recorded for every sentence, and the
companion study's term audit is rerun: every sentence whose only match is the
standalone abbreviation is screened and read blind, and confirmed non-AI sentences
are removed from every denominator with the removed count reported.

**Every extracted sentence is rated. There is no second-stage sampling and no
per-filing cap.** A cap would bias the filing-level measures in RQ2 downward, because
a filing's one own-use sentence could be dropped.

## 4. What gets recorded for each sentence

**Part A, class.** Exactly one of the companion study's five classes, with the
companion's definitions verbatim:

- `capability`: asserts that the registrant's own product, service or operation uses
  AI, and attributes a capability, benefit, efficiency or performance level to it
- `risk`: risk-factor language: competition, regulation, security, reputational or
  ethical risk arising from AI
- `market`: describes AI in the industry, in the market, or at competitors, rather
  than at the registrant
- `governance`: describes policy, board oversight, internal controls or responsible
  use programmes for AI
- `other`: definitions, cross-references, forward-looking boilerplate and anything
  that fits none of the above

**Part B, own use.** One binary judgement, `own_use`, recorded for every sentence
regardless of class. It is `true` when the sentence states that the registrant
itself currently uses, deploys, offers, licenses, develops, trains or is implementing
AI in its own products, services, operations or research, whether or not any benefit
is attributed. "We use machine learning to screen applications", "our platform
incorporates AI", "we are integrating generative AI into our tools" and "we have
invested in AI capabilities" are all `true`. It is `false` for hypothetical or
conditional use ("if we incorporate AI", "to the extent we use AI", "we may in the
future use AI"), for statements about other companies, competitors, customers or the
industry, for pure definitions, and for risk language that does not assert actual
use. A risk-factor sentence that asserts actual use in passing ("our use of AI in
underwriting exposes us to model risk") is `true`.

`own_use` is the adoption-relevant judgement. The companion study found that the
passes' overturned capability calls were sentences saying a company uses AI without
saying what it achieves, which the rubric sends to `other`. Those sentences are
exactly the ones an adoption measure should count, and Part B exists to count them.

## 5. Blinding

Raters see the sentence text and nothing else. They are not told the company, the
sector, the filing year or the sentence's position in the document. The registrant's
name and ticker are removed from the sentence text where they appear. Sentences are
presented in a seeded shuffle that mixes filings and years together, so a rater
cannot reconstruct a company or a year from a run of consecutive sentences.

Year blinding is imperfect by construction: a sentence that says "generative AI" or
"large language model" reveals that it was written after 2022. The fraction of
sentences carrying such an era cue is measured and reported, and agreement on those
sentences is compared with agreement on the rest, as the companion study did for name
leakage.

## 6. Passes, controls, adjudication and calibration

**Two blind passes.** Each sentence is assigned to exactly two of six rater
identities by a fixed rule applied before rating begins. The raters are independent
instances of the blind-pass model with no shared context, dispatched as subagents in
batches of about 40 sentences. The literal prompt is written to
`docs/RATER_PROMPT.md` and committed before the first batch is dispatched, which
closes the gap the companion study reported. Raters return one JSON line per
sentence with the class and the own-use judgement.

**Known-answer controls.** Thirty sentences from the companion study's calibration
key, whose class was fixed by a blinded reviewer in September 2026 and published, are
inserted unmarked into the rating stream. Rater accuracy on them is reported as an
independent error estimate. Controls are excluded from every composition rate.

**Third pass.** Every sentence on which the two passes disagree on class or on own
use is rated a third time, blind to both prior verdicts and to the fact of
disagreement, by an instance of the third-pass model, a larger model from the same
family, mixed with an equal number of agreed
sentences so that selection does not reveal disagreement. Composition is reported two
ways: agreed-only with the disputed set shown as a bound, which is the companion's
convention, and majority-of-three.

**Calibration pass.** A seeded sample of 120 sentences stratified over the five
majority classes and three eras (2015 to 2019, 2020 to 2023, 2024 to 2026), with 10
duplicated under a second identifier as self-consistency controls, is re-read blind by
the orchestrating model, which records a class and an own-use
judgement for each before the key is opened. The survival rate of each class and of
each own-use value is measured. If a systematic bias appears, every rate in the paper
is corrected by the companion's forward-transfer method and the correction is
reported alongside the uncorrected rate.

## 7. The phrase-reuse measure

For every corpus sentence, a core phrase is formed: the sentence is lower-cased and
reduced to alphanumeric tokens, and the window of L consecutive tokens beginning at
the first AI term is taken, shifted left if the sentence ends first. The phrase is
submitted to EDGAR full-text search as an exact phrase over root form 10-K for all
dates. Two things are recorded: the total number of document hits, and
`reuse_ciks`, the number of distinct registrants other than the sentence's own that
have filed a 10-K containing the phrase.

L is fixed at 12 after a pilot on 20 sentences from the companion study's published
2025 corpus, which is a different sample. The pilot and its outcome are recorded in
`docs/PHRASE_PILOT.md` before any sentence from this study's corpus is queried. The
preregistered boilerplate flag is `reuse_ciks >= 5`. The full distribution is
published so that any other threshold can be read off it.

A sentence whose core phrase returns zero hits, including its own filing, indicates a
normalisation failure rather than a rare phrase; such sentences are counted,
reported, and excluded from the reuse analysis.

## 8. Statistics

- Proportions carry Wilson score intervals at 95 percent.
- Sentences within a filing share an author and a legal reviewer, so every
  sentence-level and filing-level uncertainty comes from a percentile bootstrap that
  resamples filings, within year where the estimate is yearly, 10,000 replicates under
  a fixed seed.
- The corrected adoption share for year Y is the raw mention share times the sampled
  proportion of AI-mentioning filings with at least one own-use sentence (or at least
  one capability sentence); its interval comes from bootstrapping that proportion.
  The overstatement factor is the raw share divided by the corrected share.
- Era contrasts (2015 to 2019 against 2024 to 2026) use the bootstrap difference in
  rates. Trend is also summarised by Spearman's rank correlation between year and
  the yearly point estimate, and by a sentence-level logistic regression of the
  own-use indicator on calendar year with standard errors clustered by filing.
- The phrase-reuse classifier is evaluated against the majority-of-three own-use
  label with precision, recall and the area under the ROC curve, and against the
  class labels by the median and the distribution of `reuse_ciks` per class.
- `src/stats.py` carries its own self-checks.

## 9. Who the raters are

The raters, the third pass and the calibration pass are language models, not people:
a mid-sized commercial language model for the two blind passes, a larger model from
the same family for the third pass, and the largest model in that family, the model
orchestrating the study, for the calibration pass. Model identities and versions are
recorded in a private model log held by the author. This
study therefore does not measure human inter-rater agreement and no figure in it
should be read that way. What it measures is whether independent, protocol-driven
passes over the same text reach the same classification, how each pass performs on
sentences with a previously fixed answer, and how far each survives review by a more
careful pass. Every sentence and every judgement is published.

## 10. Predictions, stated in advance

1. The risk share of AI sentences is higher in 2024 to 2026 than in 2015 to 2019.
2. The own-use share of AI sentences is lower in 2024 to 2026 than in 2015 to 2019.
3. In 2024 to 2026, fewer than 60 percent of AI-mentioning filings contain any
   own-use sentence.
4. Risk sentences have higher cross-filer phrase reuse than capability sentences:
   the median `reuse_ciks` for risk is at least three times that for capability, and
   the boilerplate-flag rate is at least double.
5. The share of AI sentences flagged as boilerplate rises from 2015 to 2019 to
   2024 to 2026.
6. The overstatement factor is larger in 2024 to 2026 than in 2015 to 2019.
7. Technology registrants have a higher own-use rate than the other three strata
   pooled.

## 11. What would falsify the thesis

If the composition of AI language is stable over the decade, meaning the risk share
in 2024 to 2026 is within five percentage points of the risk share in 2015 to 2019,
and the overstatement factor does not grow, then a mention is a reasonable proxy for
adoption and the keyword measure is roughly honest. That result would be reported in
those words and with the same prominence as the opposite.

## 12. Exploratory analyses, declared as such

- Sector-level comparison of the raw mention share and the own-use share of 10-K
  filers against the Census Bureau BTOS AI-use rate by NAICS sector, using a coarse
  SIC-division to NAICS-sector mapping that is published with the code. Public
  registrants are a different population from the survey's, so this is an anchor,
  not a validation.
- Association between registrant size (total assets from the SEC XBRL frames API for
  the filing's fiscal year) and the own-use rate.
- A replication of the companion's 2025 composition from this study's 2025 filings,
  as a check that the two studies' pipelines agree.

## 13. Amendments

**Amendment 1, 2026-10-18, before sampling. The frame excludes amendments and
exhibit-only matches, and the Section 3.1 table is a table of raw hits.** When the
enumeration ran it became clear that the `forms=10-K` filter in EDGAR full-text
search also returns hits on Form 10-K/A and on exhibits filed with a 10-K. Section
3.1 already said hits are collapsed to filings and restricted to main-document
matches; this amendment makes the exclusion of amendments explicit, so that the
frame is the set of original 10-K filings whose main document matches, and it
records that the companion study's 3,324 figure and this document's table are raw
hit counts on the same basis. The restricted frame for 2025 is 3,162 filings from
3,153 registrants. Both counts are published in `data/frame.json`.

**Amendment 2, 2026-10-18, before any corpus sentence was queried. The distinct
registrant count for the phrase-reuse measure is paginated past the aggregation
cap.** The pilot in `docs/PHRASE_PILOT.md` found that EDGAR's entity aggregation
returns at most 30 registrants per query. The preregistered flag at five is
unaffected. For any phrase that reaches the cap, the full run paginates the hit list
up to 1,000 documents and counts distinct registrants directly, with a censoring flag
when the phrase has more hits than that. The window length L = 12 was confirmed by
the pilot and is unchanged.

**Amendment 3, 2026-10-18, at extraction and before any sentence was rated.
Sentence-level rates are reported with filings weighted equally as the primary
presentation, beside the sentence-weighted rates the preregistration implied.**
Extraction found that one 2023 registrant whose name contains the letters AI
(C3.ai) contributed 448 of the 2,590 extracted sentences, and 154 of the 2,242
that survive the term audit, so a sentence-weighted composition for 2023 is largely
the composition of one filing. Section 8 already committed to bootstrapping over
filings. This amendment adds that every sentence-level estimand (class shares and
the own-use share, overall, by era and by year) is computed and reported two ways:
weighting each sentence once, as Section 2 implied, and weighting each filing once,
using its within-filing shares. The filing-weighted version is treated as primary in
the paper's text and the sentence-weighted version is published beside it. The
predictions in Section 10 are evaluated on the filing-weighted, majority-of-three
basis, with the other bases reported. Nothing about the rubric, the passes, the
calibration or the phrase-reuse measure changes.

**Amendment 4, 2026-10-18, after rating and before the paper was written. The
C3.ai ticker is not redacted.** Section 5 said tickers are removed from the sentence
text. C3.ai's ticker is "AI", and removing it would erase the very term being rated
from every one of its sentences, so a ticker that is itself an AI term is left in
place. The registrant's name is still removed. This is recorded as a deviation
rather than silently absorbed because it means that one registrant's sentences were
shown with slightly less redaction than the others.

**Amendment 5, 2026-10-18, before publication. Model vendor and version names are
held in a private log rather than printed.** Sections 6 and 9 originally named the
specific commercial models used for each pass. Those names are replaced here and in
the paper by role descriptions (blind-pass model, third-pass model, orchestrating
model, all from one commercial family) and the identities and versions are recorded
in a private model log kept by the author and available on request. Nothing about
which pass did what, or about the design, changes; the substitution is one of
labels. The full statement of AI involvement in this study is being prepared as a
separate document.

**Note, not an amendment, 2026-10-18.** The usage limit on the rating model paused
the blind passes for about seven hours after 45 of 108 batches had completed; the
remaining batches ran under the same committed prompt and the same assignment when
the limit reset. No batch was rated twice and no judgement was discarded.
