# Timebox Investigation Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Prepare the requirements this timebox will address, from `<context_handoff_dir>/prl.md`.

1. Read the PRL, the constraints, and the foundations documents in `<context_handoff_dir>`. Read the timebox status in `previous_envelope` — it tells you how long this box has.
2. Select the requirements that belong in this timebox: Musts first, then Shoulds, then Coulds, only as far as the box can plausibly hold. Carry their ids, needs, justifications, MoSCoW and effort through unchanged.
3. Sharpen each one until a developer could build it and a tester could rule on it with no further questions. Make every acceptance criterion observable and give each a `verified_by`.
4. Anything that would change scope, priority, or the agreed definition of done goes in `escalations` — not into your own judgement.
5. Write the result to `<context_handoff_dir>/timebox_requirements.md`, then emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `AmbassadorOutput` — no prose before or after:

```json
{
  "status": "success",
  "summary": "<one sentence: N requirements taken into this timebox, M escalations>",
  "timebox": "<the timebox name from previous_envelope>",
  "requirements": [
    {
      "id": "REQ-01",
      "need": "<carried through from the PRL, sharpened only for clarity>",
      "business_justification": "<carried through unchanged>",
      "moscow": "must",
      "effort": 3,
      "acceptance_criteria": [
        { "id": "AC-01", "statement": "<observable, unambiguous>", "verified_by": "code: uv run pytest -q" }
      ]
    }
  ],
  "escalations": [
    {
      "question": "<the thing you are refusing to settle>",
      "why_human": "<why an agent must not answer this one>",
      "options": ["<the readings or paths available>"],
      "blocks": ["REQ-04"]
    }
  ],
  "artifacts": ["<context_handoff_dir>/timebox_requirements.md"],
  "notes_for_next_agent": "<what the developer must know before starting>"
}
```

The same gates that checked the PRL check your `requirements`: unique ids, a business justification on every one, at least one acceptance criterion, and `verified_by` on every Must criterion. An empty `escalations` list is a fine answer when nothing genuinely needed a human.
