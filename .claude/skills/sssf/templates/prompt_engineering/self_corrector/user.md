# Self-Correction Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Audit the reasoning in `previous_envelope` and correct what is wrong with it.

1. Read `<context_handoff_dir>/reasoning.md` in full, and the original goal in `prompt`. The goal is the yardstick for drift.
2. Open every citation above 0.7 confidence and check it says what it is claimed to say.
3. Check each hypothesis against its own `contradicted_by`, and each inference against the hypotheses it names.
4. Classify each issue by one of the five kinds, name what it affects, and state the correction you applied.
5. Write your audit to `<context_handoff_dir>/correction.md`, then emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `CorrectionOutput` — no prose before or after:

```json
{
  "status": "success",
  "issues": [
    {
      "kind": "overconfidence",
      "detail": "H-02 is an inductive generalisation from two cases held at 0.9",
      "affects": ["H-02", "INF-03"],
      "correction": "lowered to 0.45; INF-03 now reads as a working assumption rather than a finding"
    }
  ],
  "clean": false,
  "revised_confidence": 0.6,
  "summary": "<one sentence: N issues of which kinds, and where the reasoning now stands>",
  "artifacts": ["<context_handoff_dir>/correction.md"],
  "notes_for_next_agent": "<what the gatekeeper should weigh, given what you corrected>"
}
```

`kind` must be one of `contradiction`, `unevidenced_claim`, `overconfidence`, `goal_drift`, `circular`. A gate refuses `clean: true` alongside any issue, and refuses any issue whose `correction` is empty.
