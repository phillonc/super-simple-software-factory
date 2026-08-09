# Journey Mapping Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Map the journey the goal in `prompt` touches, as the code actually implements it.

1. Find the entry point, then follow it: routes, handlers, guards, redirects, validation branches, error paths, retries, notifications.
2. Record each step with its channel, what it costs the person, and where in the code it lives.
3. Name the frictions worth removing, and what removing each one would make possible.
4. Write your map to `<context_handoff_dir>/journey.md`, then emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `InteractionOutput` — no prose before or after:

```json
{
  "status": "success",
  "journey": [
    {
      "step": "<what the person does>",
      "channel": "web",
      "friction": "<what it costs them, or empty if it is clean>",
      "evidence": "src/app/checkout/page.tsx:210"
    }
  ],
  "frictions": ["<the ones worth removing>"],
  "opportunities": ["<what becomes possible if they go>"],
  "summary": "<one sentence: N steps, where it hurts>",
  "artifacts": ["<context_handoff_dir>/journey.md"],
  "notes_for_next_agent": "<the friction most worth a mechanism>"
}
```

Every step cites where it lives. A journey you inferred from a README rather than from code is a description of the intent, which is the one thing this pass is not for.
