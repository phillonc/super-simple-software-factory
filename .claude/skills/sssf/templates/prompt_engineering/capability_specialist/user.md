# Capability Discovery Task

## Variables

### prompt

{{prompt}}

### previous_envelope

{{previous_envelope}}

### context_handoff_dir

{{context_handoff_dir}}

## Task

Report the capabilities this codebase brings to the goal, and their health.

1. Read `<context_handoff_dir>/recall.md` for what the memory pass already established.
2. Find the callers: the justfile, `package.json` scripts, `pyproject.toml`, route registrations, exported entry points, CLIs the repo assumes are on PATH.
3. For each one that bears on the goal, check whether it works, and record what you ran to decide.
4. Name what the goal needs that is **not** here.
5. Put the capabilities in dependency order.
6. Write your report to `<context_handoff_dir>/capabilities.md`, then emit your `Report` JSON.

## Report

Respond with ONLY valid JSON matching `CapabilityOutput` — no prose before or after:

```json
{
  "status": "success",
  "capabilities": [
    {
      "capability_id": "typecheck",
      "provider": "package.json scripts",
      "invocation": "npm run type-check",
      "healthy": true,
      "evidence": "ran it, exit 0 in 41s"
    }
  ],
  "execution_order": ["typecheck", "test"],
  "unavailable": ["<what the goal needs and this repo does not have>"],
  "summary": "<one sentence: N capabilities, M unhealthy, K missing>",
  "artifacts": ["<context_handoff_dir>/capabilities.md"],
  "notes_for_next_agent": "<what the reasoning architect can and cannot plan against>"
}
```

An unchecked capability is `healthy: false` with `evidence` saying why it was not checked. Never report `healthy: true` on the strength of a file existing.
