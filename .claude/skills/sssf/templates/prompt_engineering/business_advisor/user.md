# Specialist Advice Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Report the specialist constraints that apply to the requirements in `previous_envelope`.

1. Read `<context_handoff_dir>/prl.md` for the full requirements, then investigate the repo for what would limit them.
2. For each constraint: name its area, state it, list the requirement ids it applies to, and cite where you found it.
3. Write your findings to `<context_handoff_dir>/constraints.md`, then emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `AdvisoryOutput` — no prose before or after:

```json
{
  "status": "success",
  "summary": "<one sentence: N constraints across which areas>",
  "constraints": [
    {
      "area": "security",
      "constraint": "<the limit, stated so it can be designed against>",
      "applies_to": ["REQ-01", "REQ-04"],
      "source": "src/auth/session.ts:88"
    }
  ],
  "artifacts": ["<context_handoff_dir>/constraints.md"],
  "notes_for_next_agent": "<what the technical coordinator must design around>"
}
```

A gate checks that every constraint has a non-empty `source`. Finding no constraints is a legitimate answer — report an empty list and say in `summary` where you looked.
