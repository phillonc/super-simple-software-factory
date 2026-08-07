# Acceptance Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Rule on the increment in `previous_envelope` against the acceptance criteria in `<context_handoff_dir>/timebox_requirements.md`.

1. Read the criteria first, so the code does not tell you what to look for.
2. Read what was actually built, starting from `previous_envelope.changed_files`.
3. Rule on **every** criterion of every requirement the timebox took on — including the ones the developer says it deferred, because "not built" is a ruling with evidence.
4. Run what you need to run. A criterion whose `verified_by` names a command is settled by that command's exit status.
5. Write the acceptance report to `<context_handoff_dir>/acceptance.md`, then emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `AcceptanceOutput` — no prose before or after:

```json
{
  "status": "success",
  "accepted": false,
  "summary": "<one sentence: N of M criteria met, K Musts outstanding>",
  "results": [
    {
      "requirement_id": "REQ-01",
      "moscow": "must",
      "criterion_id": "AC-01",
      "passed": true,
      "evidence": "src/server.ts:42 — handler registered; `uv run pytest -q` exit 0"
    }
  ],
  "unmet_musts": ["REQ-03"],
  "artifacts": ["<context_handoff_dir>/acceptance.md"],
  "notes_for_next_agent": "<what the developer must close, or how to verify if accepted>"
}
```

`status` is `success` when the review itself completed — it is not the verdict. The verdict is `accepted`, and a gate checks it against your own rulings: it is true only when no `must` result failed and `unmet_musts` is empty, and `unmet_musts` must match the failing Musts in `results` exactly.
