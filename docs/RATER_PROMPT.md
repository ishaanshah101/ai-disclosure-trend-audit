# Rater prompt

This is the literal instruction given to every rating pass, committed before the
first batch was dispatched. The only thing that varies between batches is the block
of sentences at the end. The third pass received the same prompt with the same
schema. Nothing about the study, its hypotheses, the companion study, the year, the
registrant or any other rater's output was included.

---

You are classifying sentences taken from corporate annual reports. Each sentence
mentions artificial intelligence or a related term. You see only the sentence text.
Do not try to guess which company wrote it or when. Judge each sentence on what it
says, not on what you assume about the company.

For every sentence, record two things.

**class**: exactly one of

- `capability`: the sentence asserts that the registrant's own product, service or
  operation uses AI, and attributes a capability, benefit, efficiency or performance
  level to it. "Our platform uses machine learning to reduce claim processing time."
- `risk`: risk-factor language: competition, regulation, security, reputational or
  ethical risk arising from AI. "The use of AI by our competitors could render our
  products obsolete." "AI regulation may increase our compliance costs."
- `market`: describes AI in the industry, in the market, or at competitors, rather
  than at the registrant. "Demand for AI infrastructure has grown rapidly."
- `governance`: describes policy, board oversight, internal controls or responsible
  use programmes for AI. "Our board's audit committee oversees our AI governance
  framework."
- `other`: definitions, cross-references, forward-looking-statement boilerplate,
  table-of-contents fragments, and anything that fits none of the above. A sentence
  that says the registrant uses AI but attributes no capability, benefit or
  performance to it is `other`, not `capability`.

**own_use**: `true` or `false`, judged independently of class.

`true` when the sentence states that the registrant itself currently uses, deploys,
offers, licenses, develops, trains or is implementing AI in its own products,
services, operations or research, whether or not any benefit is attributed.
"We use machine learning to screen applications" is true. "Our platform incorporates
AI" is true. "We are integrating generative AI into our tools" is true. "We have
invested in AI capabilities" is true. "Our use of AI in underwriting exposes us to
model risk" is true, because it asserts actual use even though the sentence is about
risk.

`false` for hypothetical or conditional use ("if we incorporate AI", "to the extent
we use AI", "we may in the future use AI"), for statements about other companies,
competitors, customers, suppliers or the industry, for pure definitions, for
governance statements that do not assert use, and for risk language that does not
assert actual use. "Companies in our industry are adopting AI" is false. "AI could
disrupt our business model" is false.

Rules:

- Judge the sentence only. Do not infer from the registrant's probable identity.
- A fragment that has lost its context is still rated on what it says.
- If a sentence is a list item or heading fragment that cannot be classified, use
  `other` and `false`.
- Output one JSON object per line, in the same order as the input, with exactly these
  keys: `id`, `class`, `own_use`. No commentary, no markdown fences, no extra keys.

Example output line:

{"id": "s0001", "class": "risk", "own_use": false}

Sentences:

[batch of sentences, one per line, each as `id<TAB>text`]
