# Emergent Pattern Detection Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Sweep the area named in `prompt` for behaviour nobody designed.

1. Establish the baseline: what this area is specified, typed, tested, or documented to do. Name it — it goes in the report.
2. Look for the gap between that and what the code makes possible. Route tables versus literal paths. Defaults nobody chose. Error branches that return success. Features composing into a third thing. Workarounds that became interfaces.
3. Score each pattern's novelty against the baseline, classify it, and cite what shows it.
4. For anything you classify a risk, say what containing it would look like.
5. Write your sweep to `<context_handoff_dir>/emergence.md`, then emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `EmergenceOutput` — no prose before or after:

```json
{
  "status": "success",
  "baseline": "<what 'designed for' was measured against>",
  "patterns": [
    {
      "id": "PAT-01",
      "pattern": "<what is happening that nobody designed>",
      "novelty": 0.7,
      "classification": "risk",
      "evidence": ["src/api/[id]/route.ts:34 — the literal 'mine' binds as :id"],
      "containment": "<what containing it would look like — you are not applying it>"
    }
  ],
  "summary": "<one sentence: N patterns, how they classify>",
  "artifacts": ["<context_handoff_dir>/emergence.md"],
  "notes_for_next_agent": "<the friction most worth a new mechanism>"
}
```

`classification` is one of `benign`, `opportunity`, `risk`, `unknown`. Finding nothing is a legitimate result — report an empty list and say in `summary` what you swept and against what baseline.
