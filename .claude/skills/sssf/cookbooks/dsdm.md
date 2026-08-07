# DSDM: the governed roster

An AI-first agentic framework built on the DSDM Agile Project Framework, where the
roles DSDM keeps human stay human. Eight agents, three ADWs, one rule that shapes
all of it:

> **An agent may prepare a decision. It may not take one that belongs to a person,
> and it cannot forge the record of one being taken.**

Everything below is that rule, made mechanical. Run it with `--config`:

```bash
# on Pi
uv run adws/adw_dsdm_foundations.py "Add SSO so enterprise customers stop sharing logins." \
    --config adws/adw_sssf_config/sssf.config.dsdm.yaml

# the same roster on Claude Code — same agents, same prompts, same boundaries
uv run adws/adw_dsdm_foundations.py "Add SSO so enterprise customers stop sharing logins." \
    --config adws/adw_sssf_config/sssf.config.dsdm.cc.yaml
```

Two rosters, one workflow. `coding_agent:` is the only meaningful difference
between them, which is the point: ADWs, gates and prompts are written once.

or through the recipes: `just foundations "…"`, `just timebox --adw-id <id> "…"`,
`just coach <id>`, `just decisions`.

---

## The roster

| Agent | DSDM role | Produces | May write |
|---|---|---|---|
| `business_analyst` | Business Analyst | Prioritised Requirements List, MoSCoW + effort + acceptance criteria | `specs/` |
| `business_advisor` | Business Advisor | specialist constraints, each one sourced | nothing |
| `technical_coordinator` | Technical Coordinator | Solution Architecture Definition, Development Approach Definition | `specs/` |
| `workshop_facilitator` | Workshop Facilitator | the decision pack for a human checkpoint | nothing |
| `business_ambassador` | Business Ambassador | timebox requirements, sharpened; escalations | nothing |
| `solution_developer` | Solution Developer | the increment | anything but `protected_files` |
| `solution_tester` | Solution Tester | acceptance rulings against agreed criteria | nothing |
| `dsdm_coach` | DSDM Coach | an audit of a run against the eight principles | nothing |

### Who is deliberately not an agent

| Role | Who does it | Why |
|---|---|---|
| **Business Sponsor** | **a human** | Owns the business case and the money. Appears in every chain as a checkpoint. |
| **Business Visionary** | **a human** | Owns the vision and settles priority conflicts. Same. |
| Project Manager, Team Leader | the ADW script | Sequencing, retries and acceptance are deterministic. That is the factory's founding trade — agent proposes, code disposes. A "manager agent" re-deciding the chain each run would make the one part of the system that is predictable stop being so. |
| The test *runner* | `quality.py`, a `kind="code"` phase | `bun test` is a command, not a judgement call (hard rule 8). `solution_tester` rules on acceptance criteria, which genuinely needs reading and deciding. |
| The timebox keeper | `timebox.py` | An agent asked to watch the clock has no clock. A subprocess does. |

---

## The eight principles, and what enforces each one

A principle nobody checks is a slogan. Each row names the code that keeps it.

| # | Principle | Mechanism |
|---|---|---|
| 1 | Focus on the business need | `gates.requirements_traceable` — every requirement needs a `business_justification` and at least one acceptance criterion, or the phase fails |
| 2 | Deliver on time | `gates.moscow_balanced` (Musts ≤ 60% of effort, Coulds ≥ 20%) + `timebox.py`'s wall clock + `gates.musts_not_descoped` |
| 3 | Collaborate | typed envelopes; the advisor's constraints are an *input* to the coordinator, the criteria an input to the tester |
| 4 | Never compromise quality | `gates.acceptance_consistent` — `accepted` is arithmetic over the rulings, not a mood; the agreed level lives in the Development Approach Definition |
| 5 | Build incrementally from firm foundations | foundations are a separate ADW that builds nothing, and `firm_enough_to_start` reaches the human as part of the question |
| 6 | Develop iteratively | the bounded build → test → accept loop inside the timebox |
| 7 | Communicate continuously and clearly | every phase earns a description; every decision gets a prose record beside its JSON |
| 8 | Demonstrate control | `human.py` + `gates.decision_is_the_humans` + `adws/adw_decisions/` in `protected_files` — see below |

---

## Keeping the human in control

Four mechanisms, none of which is a prompt asking an agent to behave.

**1. The verdict is not an agent-writable field.** `HumanDecision` is constructed
only in `adw_modules/human.py`. No agent's output type contains one. The
facilitator produces a `DecisionPackOutput` — question, two or more options,
consequences, reversibility, impact on Musts, a recommendation — and
`gates.decision_is_the_humans` fails the phase if it arrives with `decided: true`,
with one option, with no question, or with no stated cost of doing nothing.

**2. There is no default verdict.** A checkpoint with nobody to answer it stops
the run:

```
checkpoint 'foundations_approval' needs a human and this run has no way to reach
one: stdin is not a terminal, no --decision-file was given, and no --decide
foundations_approval=... was passed. Answer it one of those three ways and
re-run — there is no verdict this can assume on your behalf.
```

Three ways to answer, each recorded as which one it was:

| Mode | How | Recorded `source` |
|---|---|---|
| interactive | a terminal; the pack prints, you answer | `prompt` |
| file | `--decision-file answer.json` — the run writes the question to `answer.json.request.json` and blocks until a person writes the verdict. `--decision-timeout` failing is a failure, never a yes. | `file` |
| in advance | `--decide foundations_approval=go:"budget agreed"` | `preapproved` |

**3. The record is evidence.** Every answer lands in `adws/adw_decisions/<adw_id>/`
as JSON and as prose, and is committed in its own commit *before* the work it
authorises — including a `no_go`, which is the verdict most worth keeping and the
one a chain is most tempted to drop.

That directory is in `defaults.protected_files` and no agent names it in `writes`,
so `permissions.py` rolls back and kills the phase of any agent that touches it.
Committing matters independently: `permissions.snapshot()` fingerprints an
*untracked* file by name alone, so an uncommitted record's contents could be
rewritten unnoticed. Tracked, a tamper shows in `git diff`.

Three independent copies have to be changed in step to hide one: the file, the git
history, and the trace row carrying its sha256.

```bash
just decisions          # every decision, newest first
python -c "from adw_modules import human; print(human.verify('adws/adw_decisions/<id>/01_foundations_approval.json'))"
```

**4. Descoping a Must is never automatic.** When the clock beats the work,
`timebox.descope_plan` drops Coulds, then Shoulds — and puts any outstanding Must
in `musts_at_risk`, which the ADW splices into the checkpoint question. The date is
fixed; what to do about a Must that will not fit is the sponsor's call.

---

## The lifecycle

```
Foundations (once)                    Evolutionary development (repeat)
─────────────────────                 ─────────────────────────────────
adw_dsdm_foundations.py               adw_dsdm_timebox.py --adw-id <same>

request                               kickoff              ← clock starts
  business_analyst    PRL               business_ambassador
  business_advisor    constraints         ◆ scope_question  ← if it escalated
  technical_coordinator  SAD + DAD      solution_developer ⟲
  workshop_facilitator   pack           code(test)         ⟲ bounded loop
◆ foundations_approval  ← YOU           solution_tester    ⟲
  git(record) + git(commit)            code(consolidate)   ← descope plan
                                        workshop_facilitator  pack
                                      ◆ timebox_review     ← YOU
                                        git(record) + git(commit)
```

**There is no ADW that loops timeboxes for you, on purpose.** Deciding whether the
work deserves another box is exactly the decision the ceremony exists to put in
front of a person. Run `adw_dsdm_timebox.py` again with the same `--adw-id` when
you want another one.

`adw_dsdm_coach.py <adw_id>` audits a finished run against all eight principles and
exits non-zero on a breach, so it is worth putting in CI.

---

## Tuning it

- **`--minutes` is a deadline, not a budget.** It does not extend. The clock is read
  between iterations, never mid-phase — an expired box means "no more refinement
  loops", not an agent killed halfway through an edit.
- **The MoSCoW thresholds** are `MAX_MUST_SHARE` / `MIN_COULD_SHARE` in `gates.py`.
  Before loosening them, check whether the analyst has marked as Must something the
  increment would survive without. That is almost always what a failure means.
- **Adding an agent** follows [update_config.md](update_config.md), plus: give it
  `writes: []` unless it genuinely builds, and never grant it `adws/adw_decisions/`.
- **Adding a checkpoint** is `human.decide(run, ph, request, checkpoints)` inside an
  `engineer` phase, followed by a git phase committing `decision.records`. Branch on
  `decision.proceed`; pass it to `run.finish(accepted=...)`. Do not raise on a
  `no_go` — a human declining is the checkpoint working.
