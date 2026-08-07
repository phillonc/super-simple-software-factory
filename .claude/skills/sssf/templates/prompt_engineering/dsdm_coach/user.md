# Principles Audit Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Audit the run named in `prompt` against the eight DSDM principles.

1. Read the trace: `sqlite3 adws/adw_data/sssf.db ".schema"` once, then query `sessions`, `phases`, `events`, `envelopes` and `gate_results` for that `adw_id`. Phase descriptions, gate checks and envelope summaries are where most of the evidence is.
2. Read the run's decision records under `adws/adw_decisions/<adw_id>/` — who decided what, when, and on what basis. A chain with no decision record has no evidence of human control, whatever its prompts claim.
3. Read the products in that session's `context_handoff/` — the PRL, the foundations, the acceptance report.
4. Rule on all eight principles, each with evidence. Name a corrective action for every one you do not uphold.
5. Write the audit to `<context_handoff_dir>/coach_audit.md`, then emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `CoachOutput` — no prose before or after:

```json
{
  "status": "success",
  "summary": "<one sentence: N of 8 principles upheld, and the most serious gap>",
  "findings": [
    {
      "principle": "demonstrate_control",
      "upheld": true,
      "evidence": "adws/adw_decisions/a1b2c3d4/01_foundations_approval.json — go, decided by <name>",
      "corrective_action": ""
    }
  ],
  "breaches": ["<one line per principle not upheld>"],
  "artifacts": ["<context_handoff_dir>/coach_audit.md"],
  "notes_for_next_agent": "<what the engineer should change in the factory itself>"
}
```

A gate checks that all eight principles appear, by their exact names, and that every `upheld: false` finding carries a `corrective_action`. `status` is `success` when the audit completed — finding breaches is the audit working, not failing.
