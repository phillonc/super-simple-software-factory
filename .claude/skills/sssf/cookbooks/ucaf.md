# UCAF: the cognitive roster

The Universal Cognitive Agent Framework's seven agents, staffed as an SSSF roster.
Ported from `lhs-agents/agents/ucaf-agent-system/`, where the same seven run as
TypeScript services behind a `UCAFPrimaryAgent`. Nine agents here, two ADWs, one
rule that shapes all of it:

> **A claim is only as good as what could refute it.** Every strategy is named from
> a closed list, every confidence above 0.7 cites evidence, every score is
> recomputed by a gate, and the two verdicts nobody may self-issue — constitutional
> compliance and prior-art clearance — are held by an independent agent and a human
> respectively.

Everything below is that rule, made mechanical. Run it with `--config`:

```bash
# the standing cognitive loop
uv run adws/adw_ucaf_cognitive.py "Why does the queue drop jobs under retry pressure?" \
    --config adws/adw_sssf_config/sssf.config.ucaf.yaml

# with the interaction pass, for a goal that has a human journey in it
uv run adws/adw_ucaf_cognitive.py "Why do carts get abandoned at delivery selection?" \
    --config adws/adw_sssf_config/sssf.config.ucaf.yaml --journey

# the episodic pair: is this idea category-defining?
uv run adws/adw_ucaf_category.py "Let buyers underwrite stock a seller does not yet hold." \
    --config adws/adw_sssf_config/sssf.config.ucaf.yaml
```

Or through the recipes: `just ucaf "…"`, `just ucaf-journey "…"`, `just category "…"`.

---

## What this roster is, and what it is not

It **is** UCAF's cognitive model expressed as prompts and gates over this factory's
machinery. The vocabulary is copied exactly — the eight reasoning strategies, six
memory types, five ethical dimensions, seven constitutional pillars, eight category
dimensions and four bands — because a hand-run analysis here and a programmatic one
in `lhs-agents` have to reach the same verdict, and they cannot if the two disagree
about what things are called. Those lists live in `adw_modules/data_types.py`, not
in a prompt, so a gate and an agent read the same one.

It is **not** a client for the running UCAF service. Nothing here calls port 8100.
If you want the TypeScript agents themselves, use their HTTP surface; this roster is
for doing UCAF-shaped work on a codebase.

---

## The roster

| Agent | UCAF agent | Answers | Produces | May write |
|---|---|---|---|---|
| `memory_architect` | DMA (recall) | What do we already know? | recalls by memory type, and the gaps | nothing |
| `capability_specialist` | CIS | What can we do, and does it work? | capability registry, health checked | nothing |
| `reasoning_architect` | ARA | Given the goal and the evidence, what follows? | hypotheses and inferences, each by a named strategy | nothing |
| `self_corrector` | ARA (Ralph `SELF_CORRECTION`) | What is wrong with that reasoning? | issues and the corrections applied | nothing |
| `alignment_gatekeeper` | DAVS | Should we be doing this at all? | five dimensions, seven pillars, a verdict | nothing |
| `interaction_specialist` | IES | How do people actually move through this? | the lived journey and its frictions | nothing |
| `emergence_researcher` | ERA | What is this system doing that nobody designed? | patterns, classified, with containment | nothing |
| `category_feature_architect` | CDFA | What would change what is possible? | candidates scored on eight dimensions, gated, banded | `specs/` |
| `prior_art_searcher` | CDFA → IP adapters | What already exists, and what could not be reached? | hits and coverage gaps — never a clearance | nothing |
| `memory_consolidator` | DMA (consolidation) | What survives this run? | the durable memory, and what it retires | `app_docs/` |
| `workshop_facilitator` | — | What is the human actually deciding? | the decision pack | nothing |

Ten of the eleven are `writes: []`. That is not caution, it is the shape of the
work: a roster whose product is *understanding* leaves one document behind, and the
one agent that writes it is the one whose whole job is writing it.

### Splits that look like duplication and are not

| Split | Why |
|---|---|
| `memory_architect` / `memory_consolidator` | Both are DMA. Recall reads and writes nothing; consolidation writes the run's only durable artifact. One agent holding both would need the union of their permissions for the whole run, which makes the read-only recall phase writable. |
| `reasoning_architect` / `self_corrector` | UCAF's Ralph loop has `SELF_CORRECTION` as its own phase for one reason: an agent re-reading its own work in its own session agrees with itself. Different agent, **different model**, or the pass is theatre. |
| `category_feature_architect` / `prior_art_searcher` | The architect has an interest in its own candidate; the searcher must not. Separating them means the evidence that could sink a candidate is not gathered by the agent that proposed it. |

### Who is deliberately not here

| Thing | Why |
|---|---|
| **The message bus** | UCAF implements and tests an `AgentMessageBus` that no agent binds to. Porting an unused seam would make this roster claim a coupling neither system has. |
| **ERA and CDFA in the standing loop** | Absent from `UCAFRalphOrchestrator` there, absent from `adw_ucaf_cognitive.py` here. Both are episodic: running one on a schedule runs it against inputs nobody supplied. They get their own ADW. |
| **Prior-art clearance** | A human's, always. See below — this is the sharpest rule in the roster. |

---

## The claims, and what refutes each one

| Claim an agent could make | What stops it being taken on trust |
|---|---|
| "I reasoned abductively" | `gates.strategy_is_known` — UCAF has eight strategies and a ninth name is a rejection. An invented strategy is how an ordinary guess sounds principled. |
| "I'm 0.9 confident" | `gates.inferences_are_evidenced` — above 0.7 you cite a `file:line` or a command, and every `from_hypotheses` id must be one the envelope actually raised. |
| "I checked the reasoning, it's clean" | `gates.corrections_applied` — `clean: true` alongside any issue is refused, and an issue with an empty `correction` is refused. Detecting a contradiction and leaving it standing is worse than not looking. |
| "It scores 95 on alignment" | `gates.all_dimensions_scored` recomputes the weighted score from the published weights (privacy 0.25, transparency 0.20, autonomy 0.20, fairness 0.20, beneficence 0.15). Score the five honestly and the total is arithmetic. |
| "Compliant" | `gates.alignment_verdict_consistent` — refused alongside a high/critical breach, refused below 60, and refused without the Dual Newspaper Test. |
| "This is CATEGORY_DEFINING" | `gates.gates_not_bypassed` re-derives the raw band from the composite (`INCREMENTAL` 0 / `DIFFERENTIATING` 45 / `CATEGORY_EXTENDING` 62 / `CATEGORY_DEFINING` 78), then walks it down by the candidate's own disqualifiers: BLOCKING floors it at `INCREMENTAL`, each DEMOTING drops a band. |
| "Prior art is clear" | **Nothing may make this claim.** See below. |

---

## The one rule with three enforcements: a sweep is never a clearance

`prior_art_searcher` reports what the IP databases hold. It may never conclude the
way is clear, and the prohibition is written down three times:

1. **The type.** `PriorArtOutput.blocking` is `Literal[False]` and
   `requires_human_adjudication` is `Literal[True]` — an envelope saying otherwise
   fails to parse.
2. **The gate.** `gates.prior_art_is_not_a_clearance` re-checks both, and requires
   named databases, verbatim queries, and **at least one coverage gap**. Silence
   about gaps reads as "nothing is out there".
3. **The chain.** `adw_ucaf_category.py` ends at a human checkpoint. The verdict
   lands in `adws/adw_decisions/`, a `protected_files` path no agent may write.

The reason it is absolute rather than merely cautious: patent applications publish
up to eighteen months after filing, so the most relevant document may not exist in
any database on the day you search. Coverage varies by office and decade. The term
nobody thought of is the one that finds the blocking document. An automated sweep
that reported "clear" would be wrong in exactly the cases that matter — and wrong
*reassuringly*, which is worse than being wrong loudly.

This is hard rule 11 applied to a second kind of decision, and the general form is
worth keeping: **when a verdict is only trustworthy because a qualified person gave
it, no chain of agents may produce it, however well-evidenced the chain.**

---

## The chains

```
adw_ucaf_cognitive                      adw_ucaf_category
────────────────────                    ─────────────────
engineer(goal)                          engineer(request)
memory_architect      recall            emergence_researcher   patterns
capability_specialist registry          category_feature_architect  scored + gated
[interaction_specialist  --journey]     prior_art_searcher     hits + gaps
reasoning_architect   hypotheses        workshop_facilitator   pack
self_corrector        corrections     ◆ prior_art_adjudication ← YOU
alignment_gatekeeper  ◆ THE GATE        git(record) + git(commit)
memory_consolidator   app_docs/
git(commit_memory)
```

**Alignment runs before consolidation, and that ordering is the argument for the
whole roster.** A chain that consolidated first and reviewed afterwards would have
already written the conclusion into memory by the time it decided the conclusion was
wrong — and the next run's recall pass would read it back as established fact. One
bad run becomes the premise of every run after it. A non-compliant verdict here
skips consolidation entirely and finishes unaccepted.

**Nothing in either chain builds anything.** The cognitive chain leaves one document
in `app_docs/`; the category chain leaves one in `specs/`, and only after
adjudication. To act on what either concluded, hand its output to a delivery roster
— `adw_plan_build_test.py` on the starter roster, or `adw_dsdm_foundations.py` on
the DSDM one.

---

## Tuning it

- **`--journey` is opt-in on purpose.** IES maps how people move through a system.
  On a goal with no human journey in it there is nothing to map, and an agent asked
  to map one anyway will produce something rather than nothing.
- **`--skip-emergence`** assesses an idea as given. Without it, ERA runs first and
  CDFA synthesises candidates from what the system is already doing that nobody
  designed — which is the hand-off UCAF leaves manual and this chain automates.
- **The thresholds** are all in `data_types.py` and `gates.py`:
  `UCAF_ALIGNMENT_WEIGHTS`, `MIN_ALIGNMENT_SCORE` (60), `CONFIDENCE_NEEDS_EVIDENCE`
  (0.70), `CDF_BAND_THRESHOLDS`. Change them there, never in a prompt — the whole
  point of the lists living in code is that the gate and the agent read the same one.
- **Loosening a threshold is almost never the fix.** A run failing
  `inferences_are_evidenced` usually means the reasoning is confident about
  something it did not check, which is the gate working.
- **Adding an agent** follows [update_config.md](update_config.md), plus: give it
  `writes: []` unless it produces a durable artifact, and never grant it
  `adws/adw_decisions/`.
- **Running it on Claude Code** is a `coding_agent: claude_code` line in `defaults`
  and model aliases (`opus`, `sonnet`) in place of the `provider/id` patterns —
  exactly the DSDM roster's `.cc` variant, applied here. Keep `self_corrector` on a
  different model from `reasoning_architect` whichever agent you run.
