# Increment Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Build the requirements in `<context_handoff_dir>/timebox_requirements.md`, within the foundations in `<context_handoff_dir>/architecture.md` and `<context_handoff_dir>/development_approach.md`.

`previous_envelope` is one of three things, and it tells you which by its shape:

- the **ambassador's** sharpened requirements — this is the first pass; build in MoSCoW order.
- a **test result** (`passed`, `failures`) — the suite ran and something failed. The output is verbatim from the command; trust it over any summary, and fix what it reports.
- an **acceptance result** (`results`, `unmet_musts`) — the tester ruled and something is not met. Close the unmet criteria, starting with the Musts.

In every case: check `remaining_seconds` before you start, work in priority order, and report what you actually changed.

## Report

Respond with ONLY valid JSON matching `IncrementOutput` — no prose before or after:

```json
{
  "status": "success",
  "summary": "<one sentence: what now works that did not before>",
  "changed_files": ["src/<path>", "tests/<path>"],
  "requirements_addressed": ["REQ-01", "REQ-02"],
  "deferred": [
    { "requirement_id": "REQ-05", "moscow": "could", "reason": "<why it did not fit>" }
  ],
  "artifacts": [],
  "commit_message": "<imperative one-line git subject for THIS CODE CHANGE>",
  "notes_for_next_agent": "<what the tester should check first, and exactly where you stopped on anything unfinished>"
}
```

Two gates read this: every path in `changed_files` must exist, and nothing in `deferred` may be a `must`. If a Must did not fit, leave it out of `deferred`, say where you stopped in `notes_for_next_agent`, and let the checkpoint settle it.
