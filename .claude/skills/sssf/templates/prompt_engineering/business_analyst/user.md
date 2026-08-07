# Prioritised Requirements Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Turn `prompt` into a Prioritised Requirements List.

1. Read enough of the repo to know what already exists. Requirements about work that is already done are the most expensive kind to get wrong.
2. Write the PRL to `<context_handoff_dir>/prl.md` — the copy every later agent reads. One section per requirement: id, need, why the business needs it, MoSCoW, effort, acceptance criteria.
3. Copy that file into the repo under `specs/`:
   - **List `specs/` before you pick the name** — a session that runs more than once reuses its `<adw_id>`, so the obvious name may be taken.
   - Base name: `specs/<adw_id>_prl.md`, where `<adw_id>` is the session directory inside `context_handoff_dir` (`.../sessions/<adw_id>/context_handoff`). If it exists, use `_v2`, then `_v3`. **Never overwrite an existing PRL** — the earlier list is the record of what was asked for then.
   - **Copy it, do not retype it:** `mkdir -p specs && cp "<context_handoff_dir>/prl.md" "specs/<adw_id>_prl.md"`. Re-emitting the document through `write` costs the whole thing again in output tokens and lets the two copies drift.
4. Emit your `Report` JSON, declaring both paths in `artifacts`.

## Report

Respond with ONLY valid JSON matching `PrioritisedRequirementsOutput` — no prose before or after:

```json
{
  "status": "success",
  "summary": "<one sentence: N requirements, M Must, across what>",
  "business_need": "<one paragraph: the problem being solved, in the business's words>",
  "requirements": [
    {
      "id": "REQ-01",
      "need": "<what the business needs, in its words>",
      "business_justification": "<what breaks, costs, or goes unserved without this>",
      "moscow": "must",
      "effort": 3,
      "acceptance_criteria": [
        { "id": "AC-01", "statement": "<observable, rulable by a business person>", "verified_by": "code: uv run pytest -q" }
      ]
    }
  ],
  "out_of_scope": ["<what was considered and deliberately excluded this time>"],
  "artifacts": ["<context_handoff_dir>/prl.md", "specs/<adw_id>_prl.md"],
  "commit_message": "<imperative one-line git subject for committing THIS PRL DOCUMENT, not the work it describes>",
  "notes_for_next_agent": "<what the advisor and technical coordinator must know>"
}
```

Both `artifacts` entries are the paths you ACTUALLY wrote, `_v2` suffix and all — gates open these files.

Two gates read the `requirements` array directly: every entry needs a unique id, a non-empty `business_justification`, and at least one acceptance criterion (with `verified_by` on every Must); and the effort-weighted Must share must be at most 60% with at least 20% held as Coulds.
