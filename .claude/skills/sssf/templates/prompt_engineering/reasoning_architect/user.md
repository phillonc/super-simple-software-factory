# Reasoning Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Reason about the goal in `prompt`, against what the earlier passes established.

1. Read `<context_handoff_dir>/recall.md` and `<context_handoff_dir>/capabilities.md`. Treat a stated gap or an unavailable capability as a hard fact about the world, not an obstacle to argue around.
2. Raise your hypotheses first — candidate answers, each with a confidence and its evidence, and anything that cuts against it.
3. Draw your inferences from them, each naming its strategy and the hypotheses it rests on.
4. Verify what you can rather than assuming it: read the code, run the command, check the schema.
5. State your overall uncertainty and what you could not resolve.
6. Write your working to `<context_handoff_dir>/reasoning.md`, then emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `ReasoningOutput` — no prose before or after:

```json
{
  "status": "success",
  "goal": "<the goal being reasoned about>",
  "hypotheses": [
    {
      "id": "H-01",
      "statement": "<the candidate answer>",
      "confidence": 0.8,
      "evidence": ["src/queue/worker.ts:142", "ran `npm test -- queue`, 3 failures"],
      "contradicted_by": ["<evidence that cuts against it>"]
    }
  ],
  "inferences": [
    {
      "id": "INF-01",
      "conclusion": "<what follows>",
      "strategy": "abductive",
      "from_hypotheses": ["H-01"],
      "confidence": 0.75,
      "evidence": ["<what supports the step itself>"]
    }
  ],
  "uncertainty": 0.3,
  "unresolved": ["<what the evidence cannot settle>"],
  "summary": "<one sentence: what follows, and how firmly>",
  "artifacts": ["<context_handoff_dir>/reasoning.md"],
  "notes_for_next_agent": "<where you are least sure — point the self-corrector at it>"
}
```

`strategy` must be one of `deductive`, `inductive`, `abductive`, `analogical`, `causal`, `probabilistic`, `constraint_based`, `monte_carlo`. Gates check that, that confidences sit in 0-1, that anything above 0.7 cites evidence, and that every `from_hypotheses` id is one you actually raised.
