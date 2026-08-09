# What was added, and how to run it

Two enhancements to the Super Simple Software Factory, on branch
`claude/dsdm-agents-agentic-framework-dwenei`:

1. **A DSDM agent roster with human-owned control points** — eight agents mapped
   onto the DSDM Agile Project Framework, three new workflows, and the machinery
   that keeps the decisions DSDM reserves for people out of the agents' reach.
2. **A second coding agent** — `claude_code` was a stub that raised; it now runs.
   The same roster, prompts, gates and boundaries work on either Pi or Claude Code.

Everything ships as skill templates under `.claude/skills/sssf/templates/`. After
`install.py` stamps a repo, the paths below are relative to that repo's root.

---

## Install

```bash
cd /path/to/your/project
uv run /path/to/skill/.claude/skills/sssf/scripts/install.py
```

Stamps 89 files: `adws/` (modules + 17 ADWs), the 23 agent prompt directories,
four rosters, `.env.sample`, a `justfile`, and `.gitignore` entries.

Before the first real run, wire the test command — `adws/adw_modules/quality.py`
ships every check as a placeholder `echo` that admits it is fake:

```python
# adws/adw_modules/quality.py, in test()
argv=["uv", "run", "--with", "pytest", "pytest", "-q"],   # or ["bun", "test"], etc.
```

Then pick a roster:

| Roster | Coding agent | Needs |
|---|---|---|
| `adws/adw_sssf_config/sssf.config.yaml` | pi | `pi` on PATH |
| `adws/adw_sssf_config/sssf.config.dsdm.yaml` | pi | `pi` on PATH |
| `adws/adw_sssf_config/sssf.config.dsdm.cc.yaml` | claude_code | `claude` on PATH |
| `adws/adw_sssf_config/sssf.config.ucaf.yaml` | pi | `pi` on PATH |

The UCAF roster is a later addition and is documented on its own, in
`.claude/skills/sssf/cookbooks/ucaf.md`. Everything below this line describes the
DSDM work.

The two DSDM rosters are the same eight agents, prompts and `writes:` boundaries.
Only `coding_agent:` and the model ids differ. Examples below use the Claude Code
one; swap the `--config` to run on Pi.

---

# Enhancement 1 — the DSDM roster

## 1.1 Eight agents

| Agent | DSDM role | Produces | May write in the repo |
|---|---|---|---|
| `business_analyst` | Business Analyst | Prioritised Requirements List (MoSCoW + effort + acceptance criteria) | `specs/` |
| `business_advisor` | Business Advisor | specialist constraints, each one sourced | nothing |
| `technical_coordinator` | Technical Coordinator | Solution Architecture + Development Approach Definition | `specs/` |
| `workshop_facilitator` | Workshop Facilitator | the decision pack for a human checkpoint | nothing |
| `business_ambassador` | Business Ambassador | timebox requirements, sharpened; escalations | nothing |
| `solution_developer` | Solution Developer | the increment | anything but `protected_files` |
| `solution_tester` | Solution Tester | acceptance rulings against agreed criteria | nothing |
| `dsdm_coach` | DSDM Coach | an audit of a run against the eight principles | nothing |

**Deliberately not agents:** the Business Sponsor and Business Visionary are
humans and appear as checkpoint phases; Project Manager and Team Leader are the
ADW script; the test *runner* is a `kind="code"` phase; the timebox clock is
`adw_modules/timebox.py`.

### Run one agent on its own

```bash
uv run adws/adw_prompt.py \
  --config adws/adw_sssf_config/sssf.config.dsdm.cc.yaml \
  --agent business_advisor \
  "List the constraints in this repo that would limit adding SSO. Change nothing."
```

---

## 1.2 Three workflows

### `adw_dsdm_foundations.py` — agree the work before building it

Nothing is built. Requirements → constraints → architecture → decision pack →
**you decide**. Run it once per project.

```bash
uv run adws/adw_dsdm_foundations.py request.md \
  --config adws/adw_sssf_config/sssf.config.dsdm.cc.yaml \
  --adw-id proj0001
```

The run **stops at the checkpoint** and waits for you. See §1.3 for the three
ways to answer.

Phases: `request → requirements → constraints → foundations → decision_pack →
foundations_approval (YOU) → record_decision → commit_foundations`

### `adw_dsdm_timebox.py` — one fixed-length box of evolutionary development

Run it against the `--adw-id` of a completed foundations run, once per timebox.

```bash
uv run adws/adw_dsdm_timebox.py request.md \
  --config adws/adw_sssf_config/sssf.config.dsdm.cc.yaml \
  --adw-id proj0001 \
  --minutes 25 --loops 3 --name "tb1-musts" \
  --objective "Deliver REQ-01, REQ-02 and REQ-03."
```

| Flag | Meaning |
|---|---|
| `--minutes` | wall-clock deadline from kick-off. **It does not extend.** |
| `--loops` | max build→test→accept iterations inside the box (default 3) |
| `--name`, `--objective` | what this box is and what it is for |

There is deliberately **no ADW that loops timeboxes for you**. Deciding whether
the work deserves another box is the decision the ceremony exists to surface.
Run the command again with the same `--adw-id`.

Phases: `kickoff → investigate → [scope_question (YOU)] → build/test/accept ⟲ →
consolidate → review_pack → timebox_review (YOU) → record_decision →
commit_increment`

### `adw_dsdm_coach.py` — audit a finished run against the eight principles

```bash
uv run adws/adw_dsdm_coach.py proj0001 \
  --config adws/adw_sssf_config/sssf.config.dsdm.cc.yaml
```

Read-only. **Exits 1 on any breach**, so it works in CI. The positional argument
is the run being audited; `--adw-id` is the audit's own session.

### Via the justfile

```bash
just foundations request.md          # needs `just`; sets --config for you
just timebox --adw-id proj0001 request.md
just coach proj0001
just decisions                       # every human decision, newest first
```

---

## 1.3 Human control points

**The core rule: an agent may prepare a decision; it may not take one that
belongs to a person, and it cannot forge the record of one being taken.**

Four mechanisms, none of which is a prompt asking an agent to behave:

1. `HumanDecision` is constructed only in `adw_modules/human.py`. No agent's
   output type contains one.
2. `gates.decision_is_the_humans` fails any decision pack that arrives
   pre-decided, with one option, with no question, or with no stated cost of
   declining.
3. Every answer is committed to `adws/adw_decisions/<adw_id>/` — a
   `protected_files` path — in its own commit, **before** the work it authorises,
   including a `no_go`.
4. Descoping a Must is never automatic; it becomes a question for the human.

### Answering a checkpoint — three ways

**A. Interactively** (default when stdin is a terminal). The pack prints, you answer:

```
[foundations_approval] go | changes | no-go > go
  option OPT-A|OPT-B|OPT-C|OPT-D [OPT-A] > OPT-A
  why (optional) > budget agreed, ship it
```

**B. From a file** — how an unattended or remote run waits for a real person:

```bash
uv run adws/adw_dsdm_foundations.py request.md \
  --config adws/adw_sssf_config/sssf.config.dsdm.cc.yaml \
  --decision-file /tmp/answer.json --decision-timeout 3600
```

The run writes the question to `/tmp/answer.json.request.json` and blocks. A
person then writes:

```json
{ "verdict": "go_with_changes",
  "decided_by": "Sam Visionary",
  "rationale": "approve, but drop REQ-04",
  "chosen_option": "OPT-A" }
```

`decided_by` is required — a record with nobody's name on it is not evidence.
**Timing out is a failure, never a yes.**

**C. In advance**, typed by a human before the run:

```bash
--decide 'foundations_approval=go:Budget agreed; build it.' \
--decided-by "Alex Sponsor"
```

Verdicts are `go`, `changes`, `no-go`. Recorded as `source: preapproved` so
nobody later mistakes it for a considered response to what the agents produced.

### With no human reachable, the run stops

```
checkpoint 'foundations_approval' needs a human and this run has no way to reach
one: stdin is not a terminal, no --decision-file was given, and no --decide
foundations_approval=... was passed. Answer it one of those three ways and
re-run — there is no verdict this can assume on your behalf.
```

### Reading and verifying the decision record

```bash
cat adws/adw_decisions/proj0001/01_foundations_approval.md    # prose, for people
cat adws/adw_decisions/proj0001/01_foundations_approval.json  # structured, for tools
```

Every decision is digested and the sha256 mirrored into the trace. To check a
record has not been edited since:

```bash
uv run --with pydantic --with python-dotenv --with pyyaml --with rich python -c "
import sys; sys.path.insert(0,'adws')
from adw_modules import human
print(human.verify('adws/adw_decisions/proj0001/01_foundations_approval.json'))"
```

Compare with the trace:

```sql
select json_extract(payload_json,'$.sha256') from events
 where type='log' and name='human_decision' and adw_id='proj0001';
```

Three independent copies must change in step to hide a tamper: the file, the git
history, and the trace row.

---

## 1.4 DSDM principles as gates

Each is one DSDM rule made mechanical, in `adw_modules/gates.py`. A failing gate
returns to the same agent session as a correction; unfixed, the phase dies.

| Gate | Enforces |
|---|---|
| `requirements_traceable` | every requirement has a unique id, a business justification, ≥1 acceptance criterion, and `verified_by` on every Must criterion |
| `moscow_balanced` | Musts ≤ 60% of effort, Coulds ≥ 20% — measured on `effort`, not asserted |
| `musts_not_descoped` | no agent may defer a Must; that is the sponsor's call |
| `acceptance_consistent` | `accepted` is arithmetic over the rulings, and `unmet_musts` must match them |
| `constraints_sourced` | every specialist constraint cites a `file:line` or document |
| `decision_is_the_humans` | ≥2 options, a real question, a stated cost of declining, and no verdict |
| `all_principles_ruled` | the coach rules on all eight principles, with a corrective action per breach |

Tune the MoSCoW thresholds at the top of the DSDM gates section:

```python
MAX_MUST_SHARE = 0.60
MIN_COULD_SHARE = 0.20
```

Before loosening them, check whether something is marked Must that the increment
would survive without. That is almost always what a failure means.

---

## 1.5 Timeboxing

`adw_modules/timebox.py` holds a real wall clock and computes what comes out of
the box when the clock beats the work.

- The clock is read **between iterations**, so an expired box means "no more
  refinement loops", not an agent killed mid-edit.
- `descope_plan` drops **Coulds first, then Shoulds** — never a Must. An
  outstanding Must lands in `musts_at_risk`, which the ADW splices into the
  checkpoint question so it is the first thing the human sees.

---

# Enhancement 2 — the Claude Code coding agent

`adw_modules/agent_cc.py` was a stub that raised `NotImplementedError`. It now
implements the same contract as `agent_pi.py` (`run`, `resolve_model`,
`ToolCallTracker`), and `agents.INTERFACES` dispatches on `coding_agent:`.

| | `pi` | `claude_code` |
|---|---|---|
| binary | `pi` | `claude` |
| model syntax | `provider/model-id` | alias (`opus`, `sonnet`, `haiku`) or full id |
| `thinking:` maps to | `--thinking` | `--effort` |
| default model | `google/gemini-3.6-flash` | `sonnet` |

Three differences the interface absorbs, so no ADW, gate, prompt or roster has to
know which agent it is running on:

- **Sessions.** Pi's `--session-id` is create-or-continue; Claude Code splits
  create (`--session-id`) from continue (`--resume`) and requires a UUID. The
  factory's id is mapped through `uuid5` and a marker file tracks which call is
  which, so a rejoined session lands in the context window it left.
- **Tool names.** The roster speaks `read`/`bash`/`grep`; each interface
  translates (`Read`/`Bash`/`Grep`). Unknown names pass through, so an MCP tool
  can be granted by its real name.
- **Permissions.** Every tool the roster grants is also pre-approved via
  `--allowedTools`, so a headless run never stalls on a prompt. The allowlist is
  exactly `tools:`, so this widens nothing, and
  `--dangerously-skip-permissions` is never used.

### Run the roster on Claude Code

```bash
uv run adws/adw_dsdm_foundations.py request.md \
  --config adws/adw_sssf_config/sssf.config.dsdm.cc.yaml
```

Point at a different binary with `CLAUDE_PATH=/path/to/claude` (as `PI_PATH` does
for Pi).

### One gotcha worth knowing

The prompt goes in on **stdin**, not argv. `--tools` and `--allowedTools` are
variadic, so a trailing argv prompt is swallowed as another tool name and
`claude` exits 1 with *"Input must be provided either through stdin or as a
prompt argument"*. This is handled inside `agent_cc.run`; it only matters if you
write another interface.

---

# Two bug fixes

Both surfaced only under a real coding agent, not a stub.

**`gates.diff_matches_claims` called a deletion a lie.** The developer replaced a
placeholder test with real ones, reported the deletion accurately, and failed the
gate for it. The gate now accepts a claimed file that is gone when git records
the deletion, and still rejects one git never heard of — `git_helper.deleted_files()`
tells them apart.

**The build phase had no gate-correction retry**, so a single mis-declared file
killed the whole timebox. It now has `retries=1`, like every other phase whose
failure is a re-promptable mistake.

---

# Verification

## Deterministic checks (free, no model calls)

Gate behaviour, timebox arithmetic and the permission boundary, against a stubbed
coding agent:

| Case | Expected |
|---|---|
| balanced PRL | `moscow_balanced` passes |
| all-Musts PRL | fails: *"100% of effort is Must (DSDM ceiling 60%)"* |
| pre-decided pack | fails: *"the verdict is the human's"* |
| agent defers a Must | `musts_not_descoped` kills the phase |
| `accepted: true` with a failing Must | `acceptance_consistent` fails |
| developer (unrestricted) writes a decision record | **denied** |
| facilitator writes its own handoff file | allowed |
| human declines | all phases pass, run not accepted, exit 1, decision still committed |
| no human reachable | run stops with an actionable message |
| decision record edited by one byte | digest mismatch **and** `git diff` |

## The live run

The whole roster was run against a real coding agent, from a written request, to
build a small Python package (`logdigest` — summarise structured log files):

| | |
|---|---|
| `adw_dsdm_foundations` | 8/8 phases |
| `adw_dsdm_timebox` | 10/10 phases |
| Requirements produced | 11, at 41% Must / 29% Could — passed `moscow_balanced` first try |
| Acceptance | 11 of 11 criteria met, each citing a `file:line` |
| Test suite (real pytest) | 13 passed |
| Permission breaches | 0 |
| Decision records | 2, git-tracked, digests verify |

Agents touched only what their `writes:` allowed: `business_analyst` and
`technical_coordinator` wrote only `specs/`; `business_advisor`,
`business_ambassador`, `solution_tester` and `workshop_facilitator` touched
nothing in the repo at all.

The result works on a log file written by hand afterwards, not its own fixtures:

```
$ logdigest incident.jsonl
lines: 6 (skipped: 0)
period: 2026-08-07T09:14:02Z .. 2026-08-07T09:19:02Z
levels:
  ERROR: 4
  INFO: 1
  WARN: 1
top messages:
     3  payment declined
     1  cart loaded
```

**Caveat, stated plainly:** both checkpoints in that run were answered with
`--decide`, recorded as `source: preapproved` — a human answering in advance, not
one reviewing what the agents produced. The interactive and `--decision-file`
modes are both tested and working; a genuinely interactive approval is not
something a headless run can perform.

---

# File map

New:

```
adws/adw_dsdm_foundations.py          agree the work before building it
adws/adw_dsdm_timebox.py              one fixed-length box of development
adws/adw_dsdm_coach.py                audit a run against the 8 principles
adws/adw_modules/human.py             checkpoints, decision records, digests
adws/adw_modules/timebox.py           the clock, and descoping that stops at Musts
adws/adw_sssf_config/sssf.config.dsdm.yaml      the roster, on Pi
adws/adw_sssf_config/sssf.config.dsdm.cc.yaml   the roster, on Claude Code
adws/adw_data/prompt_engineering/{business_analyst,business_advisor,
  technical_coordinator,workshop_facilitator,business_ambassador,
  solution_developer,solution_tester,dsdm_coach}/{system,user}.md
```

Changed:

```
adws/adw_modules/agent_cc.py    stub -> a working Claude Code interface
adws/adw_modules/agents.py      INTERFACES dispatch on coding_agent:
adws/adw_modules/data_types.py  DSDM envelopes, decisions, timeboxes
adws/adw_modules/gates.py       7 DSDM gates + the deletion fix
adws/adw_modules/git_helper.py  commit_paths(), deleted_files()
justfile                        foundations / timebox / coach / decisions
```

Documentation lives in the skill: `.claude/skills/sssf/cookbooks/dsdm.md` is the
full guide; `SKILL.md` carries the coding-agent table and hard rule 11.
