# Phrase-reuse pilot

Run 2026-10-18 before any sentence from this study's corpus was queried, on 20
sentences drawn under seed 20261018 from the companion study's published 2025 corpus
(`ai-claims-audit/data/sentences.json`), which is a different sample from this
study's. Raw output is in `data/phrase_pilot.json`.

Question: does the core phrase, as constructed in `src/phrase_reuse.py`, find its own
filing in EDGAR full-text search, and does the window length matter?

| window L | sentences that found their own filing | `reuse_ciks` sorted |
|---|---|---|
| 8 | 20 of 20 | 0 ×13, 2, 6, 6, 13, 15, 17, 24 |
| 10 | 20 of 20 | 0 ×13, 1, 2, 6, 9, 13, 15, 21 |
| 12 | 20 of 20 | 0 ×13, 1, 2, 6, 8, 13, 13, 15 |
| 16 | 20 of 20 | 0 ×13, 1, 2, 6, 8, 12, 13, 14 |

Normalisation works at every length. Thirteen of the twenty sentences are used by no
other registrant at any length; the other seven are shared, and the count falls
slowly as the window lengthens, as it should. The five sentences with the highest
reuse at L = 12 are regulatory and definitional risk-factor language (an executive
order rescission, "the legal and regulatory environment relating to AI is uncertain
and rapidly evolving", and a "collectively, AI" definition), which is what the
measure is meant to find.

**Decision.** L = 12, as preregistered. The boilerplate flag stays at
`reuse_ciks >= 5`.

**One thing the pilot found that the preregistration did not anticipate.** The
distinct-registrant count comes from EDGAR's entity aggregation, which returns at
most 30 buckets. Queries for very common phrases ("artificial intelligence and
machine learning", 2,280 documents) therefore report 30 registrants whatever the true
number. The flag at 5 is unaffected. For the distribution and the medians, the full
run paginates the hits of any phrase that reaches the cap, up to 1,000 documents, and
counts distinct registrants directly, recording a censoring flag for the few phrases
that exceed that. This is recorded as Amendment 2 to the preregistration.
