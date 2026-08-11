# Prior-Art Sweep Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Sweep for prior art against the top-ranked candidate in `previous_envelope`.

1. Read the assessment and take the candidate's **mechanism** — what it structurally makes possible — as your search subject. Not its name.
2. Plan the queries before you run them: the function, the structural effect, the problem solved, the nearest existing category, an examiner's synonyms. Write them all down, including the ones that return nothing.
3. Run what you can reach. If a database is unreachable — no credentials, no network, rate-limited — that is a coverage gap, recorded as one.
4. For each hit, record the database, the identifier, the title, why it might bear on the candidate, and a URL if you have one.
5. State the coverage gaps. Every sweep has them.
6. Write your report to `<context_handoff_dir>/prior-art.md`, then emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `PriorArtOutput` — no prose before or after:

```json
{
  "status": "success",
  "candidate": "<the candidate swept>",
  "databases_searched": ["EPO OPS", "Lens.org", "TMview"],
  "queries": ["<verbatim, including the ones that returned nothing>"],
  "hits": [
    {
      "database": "EPO OPS",
      "identifier": "EP1234567A1",
      "title": "<as published>",
      "relevance": "<why this might bear on the candidate>",
      "url": "<if you have one>"
    }
  ],
  "coverage_gaps": [
    "filings from the last 18 months are unpublished and cannot be searched",
    "<any database you could not reach, and why>",
    "<non-patent literature, offices outside TMview, terms not tried>"
  ],
  "blocking": false,
  "requires_human_adjudication": true,
  "summary": "<one sentence: N hits across which databases, and what a human now has to weigh>",
  "artifacts": ["<context_handoff_dir>/prior-art.md"],
  "notes_for_next_agent": "<the hits the facilitator should put in front of the adjudicator first>"
}
```

`blocking` is always `false` and `requires_human_adjudication` is always `true`. Do not write a summary that concludes the candidate is novel, clear, or unencumbered — report what the queries returned and what they could not reach, and leave the conclusion to the person who is qualified to draw it.
