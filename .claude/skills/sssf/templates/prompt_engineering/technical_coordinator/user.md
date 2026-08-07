# Foundations Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Establish foundations for the requirements in `<context_handoff_dir>/prl.md`, within the constraints in `<context_handoff_dir>/constraints.md`.

1. Read both, then read the parts of the repo the work will touch.
2. Write the **Solution Architecture Definition** to `<context_handoff_dir>/architecture.md`: components, where each lands in this repo, interfaces, what is reused, and which decisions are expensive to reverse.
3. Write the **Development Approach Definition** to `<context_handoff_dir>/development_approach.md`: how each Must will be verified, what the test strategy is, what standards apply, and what "done" means for this increment.
4. Copy both into the repo under `specs/`, using `<adw_id>` — the session directory inside `context_handoff_dir` — as the prefix: `specs/<adw_id>_architecture.md` and `specs/<adw_id>_development_approach.md`. **List `specs/` first and never overwrite**: if a name is taken, use `_v2`, then `_v3`. Copy with `cp`, do not retype the documents.
5. Emit your `Report` JSON with all four paths in `artifacts`.

## Report

Respond with ONLY valid JSON matching `FoundationsOutput` — no prose before or after:

```json
{
  "status": "success",
  "summary": "<one sentence: the shape of the solution and how it will be assured>",
  "architecture_path": "specs/<adw_id>_architecture.md",
  "development_approach_path": "specs/<adw_id>_development_approach.md",
  "risks": ["<a risk someone could act on, not a generality>"],
  "open_questions": ["<a conflict or unknown that a human must settle before building>"],
  "firm_enough_to_start": true,
  "artifacts": [
    "<context_handoff_dir>/architecture.md",
    "<context_handoff_dir>/development_approach.md",
    "specs/<adw_id>_architecture.md",
    "specs/<adw_id>_development_approach.md"
  ],
  "commit_message": "<imperative one-line git subject for committing THESE FOUNDATION DOCUMENTS, not the work they describe>",
  "notes_for_next_agent": "<what the facilitator must put in front of the human>"
}
```

`firm_enough_to_start` is your judgement, and saying `false` is a legitimate, cheap outcome — put what is missing in `open_questions`. Every path in `artifacts` is opened by a gate, so declare what you actually wrote.
