# Memory Recall Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Establish what is already known about the goal in `prompt`.

1. State the goal in one line, in your own words — everything downstream is scoped by it.
2. Search the repo for what bears on it: prior decisions in `adws/adw_decisions/`, prior write-ups in `app_docs/` and `specs/`, the code itself, and the commit history (`git log --oneline -20`, then `git log -S<term>` for anything you need the origin of).
3. Classify each recall by memory type, cite it, and score its relevance honestly.
4. Name the gaps — what the repository does not answer, that this goal needs answered.
5. Write your recall to `<context_handoff_dir>/recall.md`, then emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `ContextOutput` — no prose before or after:

```json
{
  "status": "success",
  "goal": "<the goal in one line>",
  "recalled": [
    {
      "memory_type": "semantic",
      "content": "<what is known>",
      "source": "src/auth/session.ts:88",
      "relevance": 0.9
    }
  ],
  "gaps": ["<what nothing in the repo answers>"],
  "summary": "<one sentence: N recalls across which types, M gaps>",
  "artifacts": ["<context_handoff_dir>/recall.md"],
  "notes_for_next_agent": "<what the capability specialist should look for>"
}
```

`memory_type` must be one of `episodic`, `semantic`, `procedural`, `working`, `long_term`, `associative`. Recalling nothing is a legitimate answer on a greenfield goal — report an empty list, and say in `summary` where you looked.
