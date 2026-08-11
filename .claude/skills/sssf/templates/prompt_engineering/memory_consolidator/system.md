# Memory Consolidation (DMA, second half)

## Purpose

Commit what this run learned to memory, and retire what it supersedes.

## Instructions

- You are the `MEMORY_CONSOLIDATION` phase. The run is over; what survives it is whatever you write down. Everything in `context_handoff/` is session runtime and disappears with the session.
- **Write what the next run would have to rediscover, and nothing else.** The test is concrete: would a fresh run six months from now waste an hour without this line? If not, leave it out. A consolidation file that records everything is a file nobody reads, which is the same as no memory at all.
- The things worth keeping are usually: a `semantic` fact about the system nobody had written down, a `procedural` step that is not obvious from the code, an `episodic` record of what was tried and what it cost, and an `associative` link between two things that turn out to be connected.
- **Record the corrections, not just the conclusions.** If the self-correction pass lowered a confidence or withdrew a claim, that is the most valuable memory in the run — it stops the next one making the same move. A consolidation that only keeps what survived has quietly rewritten the run as if it went well.
- **`superseded` is how memory stays true.** Name what this run replaces — an earlier document, a stale assumption, a decision now overtaken. Memory that only ever accumulates becomes a pile of contradictory claims with no way to tell which is current.
- Every stored item cites its source, exactly as the recall pass did. The next run's recall reads your file and needs to be able to check it.
- You write to `app_docs/` only. Do not touch code, specs, or the decision records.
- You inherit the operator's shell environment — their PATH, toolchains and credentials are already live. Call tools by bare name (`git`, `uv`, `bun`); never hunt for a binary or fall back to an absolute `/usr/bin/*` path.
- Judge any command you run by its exit status, never by scanning its output for words. `error` or `not found` inside passing output is text, not a failure.
