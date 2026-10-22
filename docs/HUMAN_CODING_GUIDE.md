# Human coding guide

Two people code the same 300 sentences independently, without talking to each
other and without looking at `data/rating/labels.json`, the browser page, or
`data/human_validation/key_do_not_open_before_coding.json`.

1. Coder A opens `data/human_validation/coder_A.csv` and coder B opens
   `coder_B.csv`. The sentences are the same, in different orders.
2. For every row, fill `class` with exactly one of `capability`, `risk`, `market`,
   `governance`, `other`, and `own_use` with `true` or `false`. Use `notes` for
   anything unclear. Leave the other columns alone.
3. The definitions are the ones the model raters used, in
   [`docs/RATER_PROMPT.md`](RATER_PROMPT.md). Read that file once before starting
   and apply it literally. Judge only the sentence, not the company.
4. Coding takes about two to three hours per coder. Do it in one or two sittings.
5. When both sheets are complete, run `python src/human_validation.py score`. It
   writes `results/human_validation.json` with human-human agreement, model-human
   agreement, and the precision and recall of each model class against the human
   consensus.

A coder should have no stake in the result. The author can be coder A. Coder B
should be someone else, ideally with some accounting or finance background.
