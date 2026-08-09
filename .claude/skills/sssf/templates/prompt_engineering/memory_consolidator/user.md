# Memory Consolidation Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Commit what this run learned, so the next one does not rediscover it.

1. Read everything the run produced in `<context_handoff_dir>/` — recall, capabilities, reasoning, correction, alignment, and whatever else the chain wrote.
2. Keep only what a fresh run would otherwise have to rediscover. Include what the self-correction pass changed and why.
3. Name what this run supersedes: an earlier write-up, an assumption now known to be wrong, a convention that has moved.
4. Write it to `app_docs/<adw_id>-memory.md`, then emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `ConsolidationOutput` — no prose before or after:

```json
{
  "status": "success",
  "stored": [
    {
      "memory_type": "procedural",
      "content": "<what the next run needs to know>",
      "source": "src/queue/worker.ts:142",
      "relevance": 0.9
    }
  ],
  "superseded": ["<what this run replaces, and where it lives>"],
  "commit_message": "sssf(<adw_id>): <what this run learned>",
  "summary": "<one sentence: N memories kept, M things retired>",
  "artifacts": ["app_docs/<adw_id>-memory.md"],
  "notes_for_next_agent": "<what a future run should start from>"
}
```

`memory_type` is one of `episodic`, `semantic`, `procedural`, `working`, `long_term`, `associative`. Keeping little is a good outcome on a small run — say so in `summary` rather than padding the list.
