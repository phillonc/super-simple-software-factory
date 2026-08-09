# Category Analysis Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Assess the idea in `prompt` — or synthesise candidates from the frictions the earlier pass surfaced — and rank what comes out.

1. Read `<context_handoff_dir>/emergence.md` if it exists. A pattern classified `opportunity`, and a `risk` whose containment would be structural, are both candidate seeds.
2. For each candidate, state the mechanism: what becomes possible that was not.
3. Score all eight dimensions 0-1 with a rationale and evidence for each.
4. Compute the composite on 0-100 and set `band_before_gates` from the thresholds.
5. Apply the disqualifier gates. Declare every one that fires, with its severity and its resolution. Set `band` to what survives them.
6. Name the riskiest assumption — the dimension whose weighted shortfall costs the most.
7. Write the assessment to `specs/<adw_id>-category-assessment.md`, then emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `CategoryAnalysisOutput` — no prose before or after:

```json
{
  "status": "success",
  "candidates": [
    {
      "name": "<the feature>",
      "mechanism": "<what becomes structurally possible that was not>",
      "scores": [
        {
          "dimension": "latentSupplyUnlock",
          "score": 0.8,
          "rationale": "<why this number>",
          "evidence": ["<what supports it>"]
        }
      ],
      "composite": 66.0,
      "band_before_gates": "CATEGORY_EXTENDING",
      "band": "DIFFERENTIATING",
      "disqualifiers": [
        {
          "code": "PRIOR_ART_UNCHECKED",
          "severity": "DEMOTING",
          "detail": "no prior-art sweep has run against this candidate",
          "resolution": "run the sweep, then put the hits to a human adjudication"
        }
      ],
      "riskiest_assumption": "<the largest weighted shortfall, and how to test it>"
    }
  ],
  "ranked": ["<candidate names, best first>"],
  "commit_message": "sssf(<adw_id>): <what the assessment concluded>",
  "summary": "<one sentence: N candidates, the top band, what gated it>",
  "artifacts": ["specs/<adw_id>-category-assessment.md"],
  "notes_for_next_agent": "<the candidate to sweep for prior art, and on what terms>"
}
```

All eight dimensions per candidate, named verbatim: `latentSupplyUnlock`, `demandAggregation`, `frictionCollapse`, `trustInfrastructure`, `compoundingFlywheel`, `behaviourDefault`, `moatDurability`, `timingAlignment`. A gate recomputes the raw band from the composite and re-derives the gated band from your own disqualifiers — a BLOCKING one floors the candidate at `INCREMENTAL`, each DEMOTING one drops it a step.
