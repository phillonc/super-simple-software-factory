"""Concrete data types for the SSSF ADW system.

RULE (four-param rule): any function that takes more than 4 parameters takes
ONE of these objects instead. AgentCall and PhaseParams are the pattern.

Every agent call declares a concrete output type — an EnvelopeBase subclass —
that its final JSON response is parsed against. No untyped handoffs.
"""

from __future__ import annotations

from typing import Any, Callable, Literal, Optional, Type

from pydantic import BaseModel, Field, ValidationInfo, field_validator

PhaseKind = Literal["engineer", "agent", "code"]
PhaseStatus = Literal["queued", "running", "success", "fail"]


# ── Phases ────────────────────────────────────────────────────────────────────

class PhaseParams(BaseModel):
    """Everything run.phase() needs. Passed as one object, never loose params."""

    name: str                       # short id, unique within the run: "plan", "build"
    kind: PhaseKind                 # which lane the block renders in
    owner: str                      # engineer's name, "git", or an agent name from config
    description: str                # REQUIRED: what this phase does and why — see below
    retries: int = 0                # agent phases: gate-failure retries via continue

    @field_validator("description")
    @classmethod
    def _description_must_be_earned(cls, value: str, info: ValidationInfo) -> str:
        """A phase name identifies; a description explains. Both are required.

        The description is the only sentence the trace, the console, and the
        phase block in the UI ever show about intent — everything else is ids,
        statuses, and timings. `commit_plan: "Commit the plan"` tells a reader
        nothing they could not already see, so an echo is rejected the same way
        a blank one is. This is a construction-time error on purpose: it fires
        before the phase opens, not after a run is already in the trace.
        """
        text = " ".join(value.split())
        name = str(info.data.get("name", "?"))
        if not text:
            raise ValueError(
                f"phase {name!r}: description is required — one sentence on what this "
                f"phase does and why. It is what the trace and the UI show.")
        if text.rstrip(".").casefold() == name.replace("_", " ").casefold():
            raise ValueError(
                f"phase {name!r}: description {text!r} only restates the phase name — "
                f"say what it does and why instead.")
        return text


class Phase(BaseModel):
    """The persisted phase record — PhaseParams plus lifecycle."""

    phase_id: str
    adw_id: str
    seq: int
    params: PhaseParams
    status: PhaseStatus = "fail"    # success must be earned
    attempt: int = 0
    error: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


# ── Envelopes (agent output types) ───────────────────────────────────────────

class EnvelopeBase(BaseModel):
    """Base of every agent's final JSON response. Output types extend this."""

    status: Literal["success", "fail"]
    summary: str = ""
    artifacts: list[str] = Field(default_factory=list)
    notes_for_next_agent: str = ""


class GenericOutput(EnvelopeBase):
    pass


class PlanOutput(EnvelopeBase):
    # Subject for committing the PLAN — the spec file the planner wrote, not the
    # implementation it describes. Each agent's commit_message covers its own
    # work product, so a chain that commits per step never reuses one agent's
    # words for another agent's diff.
    commit_message: str = ""


class BuildOutput(EnvelopeBase):
    changed_files: list[str] = Field(default_factory=list)
    commit_message: str = ""        # consumed by the git commit phase


class ScoutFinding(BaseModel):
    file: str
    note: str = ""


class ScoutOutput(EnvelopeBase):
    findings: list[ScoutFinding] = Field(default_factory=list)


class ReviewFinding(BaseModel):
    """One thing the request (or plan) asked for, and whether it is there."""

    requirement: str                # the ask, in the requester's words
    met: bool
    evidence: str = ""              # where it lives, or what is missing


class ReviewOutput(EnvelopeBase):
    """Confirmation that what was built is what was asked for — not a test run."""

    approved: bool = False
    findings: list[ReviewFinding] = Field(default_factory=list)
    blocking: list[str] = Field(default_factory=list)   # what must change before approval


class DocumentOutput(EnvelopeBase):
    """Where the write-up of a completed change landed."""

    document_path: str = ""         # the doc in the repo, e.g. app_docs/<adw_id>_<slug>.md
    documented_files: list[str] = Field(default_factory=list)
    commit_message: str = ""


# ── DSDM: requirements, timeboxes, and the human's decisions ─────────────────
#
# The DSDM roster's envelopes. Three ideas carry every one of them:
#
#   1. A requirement without a business justification is not a requirement
#      (principle 1). The field is on the type, so a gate can refuse it.
#   2. Priority is MoSCoW and priority is measured — `effort` exists so
#      `gates.moscow_balanced` can check the Must share against the DSDM
#      threshold instead of taking an agent's word that the list is balanced.
#   3. A decision the human owns is never a field an agent fills in. The
#      facilitator produces OPTIONS (`DecisionPackOutput`); the verdict lives in
#      `HumanDecision`, which only `adw_modules/human.py` ever constructs.

MoSCoW = Literal["must", "should", "could", "wont"]

# Every principle the coach rules on. Named here rather than in a prompt so the
# gate and the agent are reading the same list.
DSDM_PRINCIPLES = [
    "focus_on_the_business_need",
    "deliver_on_time",
    "collaborate",
    "never_compromise_quality",
    "build_incrementally_from_firm_foundations",
    "develop_iteratively",
    "communicate_continuously_and_clearly",
    "demonstrate_control",
]


class AcceptanceCriterion(BaseModel):
    """One observable statement that decides whether a requirement is met."""

    id: str                         # AC-01, unique within its requirement
    statement: str                  # observable, in the business's own words
    # Who or what settles it: "code: uv run pytest -q", "agent: solution_tester",
    # or "human". Naming a runner is how a criterion stops being an opinion —
    # and a criterion only a human can settle is a criterion that must reach one.
    verified_by: str = ""


class Requirement(BaseModel):
    """One entry in the Prioritised Requirements List."""

    id: str                         # REQ-01, stable for the life of the project
    need: str                       # what the business needs, in its words
    business_justification: str     # WHY it is needed — principle 1, gated
    moscow: MoSCoW
    # Relative effort, any consistent unit. Not an estimate of truth — it exists
    # so the Must/Should/Could split can be MEASURED rather than asserted.
    effort: int = 1
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)


class PrioritisedRequirementsOutput(EnvelopeBase):
    """The PRL: what the business needs, why, and in what order it matters."""

    business_need: str = ""         # one paragraph: the problem being solved
    requirements: list[Requirement] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    commit_message: str = ""


class Escalation(BaseModel):
    """Something the ambassador refused to settle on the business's behalf."""

    question: str
    why_human: str                  # why an agent must not answer this one
    options: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)      # requirement ids held up


class AmbassadorOutput(EnvelopeBase):
    """The PRL sharpened for one timebox, plus what the agent would not decide."""

    timebox: str = ""
    requirements: list[Requirement] = Field(default_factory=list)
    escalations: list[Escalation] = Field(default_factory=list)


class Constraint(BaseModel):
    """A specialist limit the solution has to live within."""

    area: str                       # security | compliance | ops | data | cost | ...
    constraint: str
    applies_to: list[str] = Field(default_factory=list)  # requirement ids
    source: str = ""                # file:line, or the document it came from


class AdvisoryOutput(EnvelopeBase):
    """Specialist input. Every constraint cites where it came from."""

    constraints: list[Constraint] = Field(default_factory=list)


class FoundationsOutput(EnvelopeBase):
    """Firm foundations — enough architecture to start, not a finished design."""

    architecture_path: str = ""     # Solution Architecture Definition
    development_approach_path: str = ""   # how quality is assured, and to what level
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    firm_enough_to_start: bool = False
    commit_message: str = ""


class DecisionOption(BaseModel):
    """One thing the human could choose, and what follows from choosing it."""

    id: str                         # OPT-A
    option: str
    consequence: str
    impact_on_musts: str = ""       # which Musts this option puts at risk, if any
    reversibility: Literal["reversible", "costly", "irreversible"] = "reversible"


class DecisionPackOutput(EnvelopeBase):
    """What the facilitator prepares FOR a human checkpoint. Never a verdict.

    `decided` exists so the absence of a verdict is checkable rather than
    assumed: `gates.decision_is_the_humans` fails any pack that arrives with it
    set. An agent that answers the question it was asked to frame has taken the
    human out of the loop, and that is the one failure this roster exists to
    make impossible.
    """

    checkpoint: str = ""            # the control point this pack is for
    question: str = ""              # the ONE thing the human must settle
    options: list[DecisionOption] = Field(default_factory=list)
    recommendation: str = ""        # an option id — advice, never an answer
    if_no_decision: str = ""        # what happens if the human says nothing
    decided: bool = False           # ALWAYS false. Gated.


HumanVerdict = Literal["go", "go_with_changes", "no_go"]
DecisionSource = Literal["prompt", "file", "preapproved"]


class HumanDecisionRequest(BaseModel):
    """Everything a checkpoint needs to put a decision in front of a human."""

    checkpoint: str                 # short id: foundations_approval, timebox_review
    question: str
    options: list[DecisionOption] = Field(default_factory=list)
    recommendation: str = ""        # option id the facilitator advises
    if_no_decision: str = ""
    pack_path: str = ""             # the write-up the human should read first
    # Deliberately absent: any notion of a default verdict. A checkpoint with
    # nobody to answer it stops the run — it does not assume consent.


class HumanDecision(BaseModel):
    """A verdict, and the trail proving a human gave it.

    Only `adw_modules/human.py` constructs this. No agent can emit one, because
    no agent's output type contains it.
    """

    checkpoint: str
    verdict: HumanVerdict
    decided_by: str
    rationale: str = ""
    chosen_option: str = ""
    decided_at: str = ""
    source: DecisionSource = "prompt"
    record_path: str = ""           # the decision record — JSON, for tools
    readable_path: str = ""         # the same record as prose, for people
    digest: str = ""                # sha256 of record_path, mirrored into the trace

    @property
    def proceed(self) -> bool:
        return self.verdict != "no_go"

    @property
    def records(self) -> list[str]:
        """Both files, for the commit phase. Neither is the backup of the other:
        the JSON is what `verify()` digests, the prose is what anyone reviewing
        this decision a year from now will actually open."""
        return [p for p in (self.record_path, self.readable_path) if p]


class DecisionOutput(EnvelopeBase):
    """A human decision shaped as an envelope, so agents can be handed one.

    Same adapter idea as VerifyOutput and ChangesOutput: the decision came from
    a person, not an agent, and it reaches the next agent through the one door
    every handoff uses.
    """

    checkpoint: str = ""
    verdict: str = ""
    chosen_option: str = ""
    decided_by: str = ""
    rationale: str = ""
    record_path: str = ""


class TimeboxSpec(BaseModel):
    """A fixed-length box of work. The end date is the one thing that cannot move."""

    name: str
    minutes: int = 30               # wall clock, from kick-off
    max_refine_loops: int = 3
    objective: str = ""


class TimeboxStatus(BaseModel):
    """Where a timebox is against its own clock. Pure arithmetic, no judgement."""

    name: str
    minutes: int
    started_at: str = ""
    elapsed_seconds: float = 0.0
    remaining_seconds: float = 0.0
    expired: bool = False

    @property
    def spent_share(self) -> float:
        total = self.minutes * 60
        return 1.0 if total <= 0 else min(1.0, self.elapsed_seconds / total)


class DescopePlan(BaseModel):
    """What comes out of the timebox when the clock beats the work.

    DSDM descopes, it does not slip: Coulds go first, then Shoulds. A Must that
    will not fit is NOT in `drop` — it is in `musts_at_risk`, which is a
    question for the human, not an outcome code may choose.
    """

    outstanding: list[str] = Field(default_factory=list)   # requirement ids not done
    drop: list[str] = Field(default_factory=list)          # Coulds then Shoulds
    musts_at_risk: list[str] = Field(default_factory=list)
    reason: str = ""

    @property
    def needs_human(self) -> bool:
        return bool(self.musts_at_risk)


class TimeboxOutput(EnvelopeBase):
    """The clock and the descope plan, as an envelope an agent can read."""

    timebox: str = ""
    minutes: int = 0
    remaining_seconds: float = 0.0
    expired: bool = False
    outstanding: list[str] = Field(default_factory=list)
    drop: list[str] = Field(default_factory=list)
    musts_at_risk: list[str] = Field(default_factory=list)


class DeferredItem(BaseModel):
    """Work the developer did not do, and why. Carries its own priority.

    `moscow` rides along so `gates.musts_not_descoped` can rule without going
    back to the PRL — an agent that quietly drops a Must has to write down that
    it was a Must in order to do it.
    """

    requirement_id: str
    moscow: MoSCoW
    reason: str = ""


class IncrementOutput(EnvelopeBase):
    """What the solution developer built in this timebox, and what it left."""

    changed_files: list[str] = Field(default_factory=list)
    requirements_addressed: list[str] = Field(default_factory=list)
    deferred: list[DeferredItem] = Field(default_factory=list)
    commit_message: str = ""


class CriterionResult(BaseModel):
    """One acceptance criterion, ruled on with evidence."""

    requirement_id: str
    moscow: MoSCoW
    criterion_id: str
    passed: bool
    evidence: str = ""              # file:line, command output, or what is missing


class AcceptanceOutput(EnvelopeBase):
    """Whether the increment meets the criteria the business agreed to."""

    accepted: bool = False
    results: list[CriterionResult] = Field(default_factory=list)
    unmet_musts: list[str] = Field(default_factory=list)


class PrincipleFinding(BaseModel):
    """The coach's ruling on one of the eight principles."""

    principle: str                  # one of DSDM_PRINCIPLES, verbatim
    upheld: bool
    evidence: str = ""              # what in the trace or the repo shows it
    corrective_action: str = ""     # required when upheld is false


class CoachOutput(EnvelopeBase):
    """An audit of a run against the eight principles. Advisory, never blocking."""

    findings: list[PrincipleFinding] = Field(default_factory=list)
    breaches: list[str] = Field(default_factory=list)


# ── UCAF: cognition, alignment, and category-defining features ───────────────
#
# The UCAF roster's envelopes, ported from the Universal Cognitive Agent
# Framework in lhs-agents (`agents/ucaf-agent-system/`). The vocabulary is
# copied deliberately rather than paraphrased: a hand-run analysis here and a
# programmatic one there have to reach the same verdict, and they cannot if the
# two disagree about what a strategy, a pillar, or a band is called.
#
# Four ideas carry every type below:
#
#   1. An inference names the strategy that produced it. UCAF has eight and
#      exactly eight; `gates.strategy_is_known` refuses anything else, so an
#      agent cannot invent a ninth to make a weak conclusion sound principled.
#   2. Confidence without evidence is a mood. Every hypothesis and inference
#      carries `evidence`, and the gate fails a high-confidence claim that
#      cites nothing.
#   3. Alignment is scored on all five dimensions or not at all. A partial
#      ethical review reads exactly like a clean one.
#   4. A prior-art search never clears anything. Only a human adjudication may
#      block a candidate — the invariant the UCAF system pins in its adapters,
#      pinned here by the type (`PriorArtOutput.blocking` is `Literal[False]`)
#      and again by `gates.prior_art_is_not_a_clearance`.

# The eight reasoning strategies, verbatim from UCAF's `ReasoningStrategy` enum.
UCAF_REASONING_STRATEGIES = [
    "deductive",            # general to specific
    "inductive",            # specific to general
    "abductive",            # inference to the best explanation
    "analogical",           # pattern transfer between domains
    "causal",               # cause and effect
    "probabilistic",        # Bayesian updating
    "constraint_based",     # satisfaction under stated limits
    "monte_carlo",          # sampled tree search
]

# DMA's six memory types. A recall that names none of these is not a recall.
UCAF_MEMORY_TYPES = [
    "episodic", "semantic", "procedural", "working", "long_term", "associative",
]

# DAVS's five weighted ethical dimensions, with UCAF's own weights. Named here
# rather than in a prompt so the gate and the agent read the same list.
UCAF_ALIGNMENT_DIMENSIONS = ["privacy", "transparency", "autonomy", "fairness", "beneficence"]
UCAF_ALIGNMENT_WEIGHTS = {
    "privacy": 0.25, "transparency": 0.20, "autonomy": 0.20,
    "fairness": 0.20, "beneficence": 0.15,
}

# The seven constitutional pillars DAVS checks an action against.
UCAF_CONSTITUTIONAL_PILLARS = [
    "community_first", "economic_fairness", "radical_accessibility",
    "uncompromising_trust", "responsible_innovation", "sustainable_growth",
    "cultural_preservation",
]

# CDFA's eight weighted dimensions of category-defining-ness.
CDF_DIMENSIONS = [
    "latentSupplyUnlock", "demandAggregation", "frictionCollapse", "trustInfrastructure",
    "compoundingFlywheel", "behaviourDefault", "moatDurability", "timingAlignment",
]

CategoryBand = Literal["INCREMENTAL", "DIFFERENTIATING", "CATEGORY_EXTENDING",
                       "CATEGORY_DEFINING"]

# Ordered weakest → strongest, so a demotion is an index shift.
CDF_BANDS = ["INCREMENTAL", "DIFFERENTIATING", "CATEGORY_EXTENDING", "CATEGORY_DEFINING"]

# Lower bound of the composite score for each band, from UCAF's published table.
CDF_BAND_THRESHOLDS = {
    "INCREMENTAL": 0, "DIFFERENTIATING": 45, "CATEGORY_EXTENDING": 62,
    "CATEGORY_DEFINING": 78,
}


class MemoryRecall(BaseModel):
    """One thing already known that bears on the goal."""

    memory_type: Literal["episodic", "semantic", "procedural", "working",
                         "long_term", "associative"]
    content: str
    source: str = ""                # file:line, a prior adw_id, or the document
    relevance: float = 0.0          # 0-1, why this made the working set


class ContextOutput(EnvelopeBase):
    """DMA's answer to 'what do we already know?' — plus what we plainly do not."""

    goal: str = ""
    recalled: list[MemoryRecall] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)   # what nothing in the repo answers


class CapabilityRecord(BaseModel):
    """One thing the system can actually do, and whether it works right now."""

    capability_id: str
    provider: str = ""              # the module, service or binary behind it
    invocation: str = ""            # how it is called: a command, a route, a symbol
    healthy: bool = False
    evidence: str = ""              # what was checked to decide `healthy`


class CapabilityOutput(EnvelopeBase):
    """CIS's registry for this run: what is available, composed in what order."""

    capabilities: list[CapabilityRecord] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)   # capability ids
    unavailable: list[str] = Field(default_factory=list)       # named, wanted, missing


class Hypothesis(BaseModel):
    """A candidate explanation, held with a stated confidence."""

    id: str                         # H-01
    statement: str
    confidence: float = 0.0         # 0-1
    evidence: list[str] = Field(default_factory=list)   # file:line or command output
    contradicted_by: list[str] = Field(default_factory=list)


class Inference(BaseModel):
    """One conclusion, and the named strategy that produced it."""

    id: str                         # INF-01
    conclusion: str
    strategy: str                   # one of UCAF_REASONING_STRATEGIES, verbatim
    from_hypotheses: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)


class ReasoningOutput(EnvelopeBase):
    """ARA's working: hypotheses raised, inferences drawn, what it would not claim."""

    goal: str = ""
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    inferences: list[Inference] = Field(default_factory=list)
    uncertainty: float = 0.0        # 0-1, the agent's own read on how shaky this is
    unresolved: list[str] = Field(default_factory=list)


class ReasoningIssue(BaseModel):
    """Something wrong with the reasoning, and what was done about it."""

    kind: Literal["contradiction", "unevidenced_claim", "overconfidence",
                  "goal_drift", "circular"]
    detail: str
    affects: list[str] = Field(default_factory=list)    # hypothesis/inference ids
    correction: str = ""            # what changed; empty means it still stands


class CorrectionOutput(EnvelopeBase):
    """The Ralph loop's self-correction pass. Finding nothing is a valid answer.

    `clean` is arithmetic over `issues`, not a mood — `gates.corrections_applied`
    refuses a pass that declares itself clean while leaving an issue uncorrected.
    """

    issues: list[ReasoningIssue] = Field(default_factory=list)
    clean: bool = False
    revised_confidence: float = 0.0


class AlignmentScore(BaseModel):
    """One of DAVS's five dimensions, scored with a reason."""

    dimension: Literal["privacy", "transparency", "autonomy", "fairness", "beneficence"]
    score: float = 0.0              # 0-100
    rationale: str = ""
    concerns: list[str] = Field(default_factory=list)


class PillarBreach(BaseModel):
    """A constitutional pillar the proposed action does not honour."""

    pillar: str                     # one of UCAF_CONSTITUTIONAL_PILLARS, verbatim
    breach: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    remedy: str = ""                # required whenever severity is high or critical


class AlignmentOutput(EnvelopeBase):
    """DAVS's answer to 'should we be doing this at all?'

    The gatekeeper of the cognitive chain, and the only agent in the roster
    whose verdict can stop a run. `compliant` has to agree with what it just
    wrote down: `gates.alignment_verdict_consistent` refuses a pass that clears
    an action while listing a critical breach against it.
    """

    action_reviewed: str = ""
    scores: list[AlignmentScore] = Field(default_factory=list)
    weighted_score: float = 0.0     # 0-100, the published weights applied
    breaches: list[PillarBreach] = Field(default_factory=list)
    # UCAF's Dual Newspaper Test: would this read badly reported as a scandal,
    # AND would it read badly reported as excessive caution? Both, in one line.
    newspaper_test: str = ""
    compliant: bool = False


class ConsolidationOutput(EnvelopeBase):
    """What DMA committed to memory at the end of a run, and what it retired."""

    stored: list[MemoryRecall] = Field(default_factory=list)
    superseded: list[str] = Field(default_factory=list)   # what this run replaces
    commit_message: str = ""


class JourneyStep(BaseModel):
    """One observed step a person takes, and what it costs them."""

    step: str
    channel: str = ""               # web | mobile | in-store | email | ...
    friction: str = ""              # what makes this step harder than it should be
    evidence: str = ""              # file:line, analytics, or the code path


class InteractionOutput(EnvelopeBase):
    """IES's read on how people actually move through this, not how it was designed."""

    journey: list[JourneyStep] = Field(default_factory=list)
    frictions: list[str] = Field(default_factory=list)  # the ones worth removing
    opportunities: list[str] = Field(default_factory=list)


class EmergentPattern(BaseModel):
    """Something happening that nobody designed for."""

    id: str                         # PAT-01
    pattern: str
    novelty: float = 0.0            # 0-1, how far outside the designed behaviour
    classification: Literal["benign", "opportunity", "risk", "unknown"] = "unknown"
    evidence: list[str] = Field(default_factory=list)
    containment: str = ""           # required when classification is "risk"


class EmergenceOutput(EnvelopeBase):
    """ERA's sweep for the behaviour the design did not predict."""

    patterns: list[EmergentPattern] = Field(default_factory=list)
    baseline: str = ""              # what "designed for" was measured against


class DimensionScore(BaseModel):
    """One of CDFA's eight dimensions, scored 0-1 with its reason."""

    dimension: str                  # one of CDF_DIMENSIONS, verbatim
    score: float = 0.0              # 0-1
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)


class Disqualifier(BaseModel):
    """A gate the candidate failed. Non-bypassable by design.

    A BLOCKING disqualifier is not waiting on evidence — no experiment result
    lifts the verdict while it stands. DEMOTING drops the band by one; ADVISORY
    is recorded and changes nothing.
    """

    code: str                       # NO_STRUCTURAL_UNLOCK, PRIOR_ART_CONFLICT, ...
    severity: Literal["ADVISORY", "DEMOTING", "BLOCKING"]
    detail: str
    resolution: str = ""            # what would have to be true to clear it


class CandidateAssessment(BaseModel):
    """One proposed feature, scored, gated, and banded."""

    name: str
    mechanism: str = ""             # what it structurally makes possible that was not
    scores: list[DimensionScore] = Field(default_factory=list)
    composite: float = 0.0          # 0-100, the published weights applied
    band_before_gates: CategoryBand = "INCREMENTAL"
    band: CategoryBand = "INCREMENTAL"      # after gates; never above the raw band
    disqualifiers: list[Disqualifier] = Field(default_factory=list)
    riskiest_assumption: str = ""


class CategoryAnalysisOutput(EnvelopeBase):
    """CDFA's answer to 'what should we build that would change what is possible?'"""

    candidates: list[CandidateAssessment] = Field(default_factory=list)
    ranked: list[str] = Field(default_factory=list)     # candidate names, best first
    commit_message: str = ""


class PriorArtHit(BaseModel):
    """One document a prior-art search surfaced. Evidence, never a verdict."""

    database: str                   # EPO OPS | Lens.org | TMview
    identifier: str                 # publication or application number, mark id
    title: str = ""
    relevance: str = ""             # why it might bear on the candidate
    url: str = ""


class PriorArtOutput(EnvelopeBase):
    """A prior-art sweep: what was searched, what came back. Never a clearance.

    `blocking` is `Literal[False]` on purpose, mirroring the UCAF invariant that
    no prior-art adapter may ever set it. A sweep that could block would read as
    a freedom-to-operate opinion, and this one is not: databases are partial,
    coverage lags publication, and only a qualified human adjudication decides
    whether a hit stands in the way. `gates.prior_art_is_not_a_clearance` says
    the same thing a second time, in case someone widens the type.
    """

    candidate: str = ""
    databases_searched: list[str] = Field(default_factory=list)
    queries: list[str] = Field(default_factory=list)
    hits: list[PriorArtHit] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)  # what was NOT searched
    blocking: Literal[False] = False
    requires_human_adjudication: Literal[True] = True


# ── Deterministic quality blocks ─────────────────────────────────────────────

QualityArea = Literal["frontend", "backend"]
QualityOperation = Literal["lint", "typecheck", "build"]


class QualityCheckSpec(BaseModel):
    """One deterministic quality command."""

    name: str
    area: QualityArea
    operation: QualityOperation
    argv: list[str]
    timeout_seconds: int = 120


class QualityCheckResult(BaseModel):
    """Captured evidence from one quality command."""

    name: str
    area: QualityArea
    operation: QualityOperation
    command: str
    returncode: int
    passed: bool
    duration_seconds: float
    output_artifact: str
    # The tail of stdout+stderr, verbatim and unparsed. A failure has to travel
    # back to the builder as an envelope, and the builder cannot open a log file
    # it was never handed — so the evidence rides along. Deliberately raw: every
    # runner formats failures differently and a generic parser would be
    # confidently wrong. The full log is always at output_artifact.
    output_tail: str = ""


class QualityResult(BaseModel):
    """Aggregate result from a quality block: every check it ran, and the verdict."""

    passed: bool
    checks: list[QualityCheckResult] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)


# ── Change capture (git diff, deterministic) ─────────────────────────────────

class ChangeCapture(BaseModel):
    """Everything documentation.capture() needs. One object, never loose params."""

    base: str = "main"              # the ref the work is measured against
    max_diff_lines: int = 2000      # the diff artifact is truncated past this
    include_untracked: bool = True  # a brand-new file is part of the change


class BaseRef(BaseModel):
    """The commit a change is measured from, and why that one.

    `reason` is the line the trace shows. A diff is only as trustworthy as the
    thing it was taken against, so the ADW records that choice instead of
    leaving the reader to infer it.
    """

    ref: str                        # what was asked for: "main", or a pinned sha
    commit: str                     # the commit actually diffed against
    reason: str = ""

    @property
    def label(self) -> str:
        """Display form — a named ref as itself, a pinned raw sha shortened."""
        if len(self.ref) == 40 and all(c in "0123456789abcdef" for c in self.ref):
            return self.ref[:7]
        return self.ref


class ChangeSet(BaseModel):
    """What changed since the base commit — pure git facts, no judgement."""

    base: BaseRef
    files: list[str] = Field(default_factory=list)
    untracked: list[str] = Field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    stat: str = ""                  # `git diff --stat` output, verbatim
    diff_path: str = ""             # the full diff, written into context_handoff/
    truncated: bool = False

    @property
    def empty(self) -> bool:
        return not (self.files or self.untracked)


class ChangesOutput(EnvelopeBase):
    """A ChangeSet shaped as an envelope so an agent can be handed it directly.

    Same adapter idea as VerifyOutput: code computes the diff, the documenter
    consumes it through the one door every agent handoff uses.
    """

    base: str = ""                  # "<ref> @ <commit> — <reason>"
    changed_files: list[str] = Field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    stat: str = ""
    diff_path: str = ""             # read this for the full diff


class VerifyOutput(EnvelopeBase):
    """A deterministic result, shaped as an envelope so an agent can consume it.

    Agents hand each other typed envelopes; code blocks return QualityResult.
    This is the adapter, so a failing lint or test run flows back into the
    builder through exactly the same door a tester agent's report used to —
    the ADW script is the only thing that knows the difference.
    """

    passed: bool = False
    failures: list[str] = Field(default_factory=list)


# ── Agent calls ──────────────────────────────────────────────────────────────

class GateCheck(BaseModel):
    """One thing a gate looked at, and what it found.

    `note` is the evidence — "exists, 2.1KB", "exit 0", "not in the diff". On a
    failed check it doubles as the reason, so it is what the agent is told.
    """

    item: str                       # what was checked: a path, a command, a test
    ok: bool
    note: str = ""


class GateReport(BaseModel):
    """What every gate returns: the checks it ran. Violations are derived.

    Authoring stays a one-liner per item — `report.check(...)` appends and
    returns self, so a gate is a loop and a return.
    """

    checks: list[GateCheck] = Field(default_factory=list)

    def check(self, item: str, ok: bool, note: str = "") -> "GateReport":
        self.checks.append(GateCheck(item=item, ok=ok, note=note))
        return self

    @property
    def violations(self) -> list[str]:
        return [f"{c.item}: {c.note or 'failed'}" for c in self.checks if not c.ok]

    @property
    def passed(self) -> bool:
        return not self.violations


class AgentCall(BaseModel):
    """One agent invocation: prompt in, typed envelope out, gates verified."""

    model_config = {"arbitrary_types_allowed": True}

    output_type: Type[EnvelopeBase]
    prompt: str
    previous: Optional[EnvelopeBase] = None
    gates: list[Callable] = Field(default_factory=list)   # gate(envelope, run) -> list[str]


# ── Config ───────────────────────────────────────────────────────────────────

class PromptEngineering(BaseModel):
    system: str                     # path to system.md
    user: str                       # path to user.md


class AgentConfig(BaseModel):
    name: str
    coding_agent: Literal["pi", "claude_code"] = "pi"
    model: str = "google/gemini-3.6-flash"
    thinking: str = "medium"        # off | minimal | low | medium | high | xhigh | max
    color: str = ""                 # hex swatch for this agent's lane in the UI
    purpose: str = ""
    prompt_engineering: PromptEngineering
    harness_engineering: list[str] = Field(default_factory=list)
    tools: Optional[list[str]] = None    # allowlist; None = all tools usable
    # What this agent may MODIFY in the repo, enforced in code after every call
    # (see adw_modules/permissions.py). `tools` cannot express this: `bash` runs
    # anything and `write` reaches any path, so an agent's capability list is a
    # statement of intent that nothing checks.
    #   None  -> unrestricted, except the roster-wide `protected_files` paths
    #   []    -> read-only: may modify nothing tracked
    #   [...] -> only these. A trailing "/" means a directory prefix; a "*"
    #            makes it a glob; anything else is an exact path.
    writes: Optional[list[str]] = None


class ConfigDefaults(BaseModel):
    coding_agent: Literal["pi", "claude_code"] = "pi"
    model: str = "google/gemini-3.6-flash"
    thinking: str = "medium"
    color: str = ""
    harness_engineering: list[str] = Field(default_factory=list)
    tools: Optional[list[str]] = None    # roster-wide allowlist; None = all tools usable
    # Off-limits to every agent that has not named them in its own `writes`.
    # The factory's own code is the default: an agent must not be able to edit
    # the machinery that decides whether its work passed.
    protected_files: list[str] = Field(default_factory=lambda: [
        "adws/adw_modules/", "adws/adw_sssf_config/", "adws/adw_*.py",
    ])
    data_dir: str = "adws/adw_data"


class ObservabilityConfig(BaseModel):
    db: str = "adws/adw_data/sssf.db"
    poll_ms: int = 500


class SSSFConfig(BaseModel):
    defaults: ConfigDefaults = Field(default_factory=ConfigDefaults)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    agents: list[AgentConfig] = Field(default_factory=list)


# ── Tracing ──────────────────────────────────────────────────────────────────

class EventRecord(BaseModel):
    """One traced event, always logged against adw_id + phase."""

    adw_id: str
    phase_id: str = ""
    type: str                       # phase_start | agent_start | tool_call | handoff | gate_pass | gate_fail | log | agent_end | phase_end | error
    name: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    parent_id: str = ""
    tokens: Optional[int] = None
    # Spans: set both when an event covers real elapsed time (a tool call), so
    # the UI lays it out on a time axis without parsing payload JSON. Left unset,
    # the tracer stamps started_at with the moment the event was recorded.
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


# ── Pi coding agent interface ────────────────────────────────────────────────

class PiRequest(BaseModel):
    """Everything one non-interactive pi run needs."""

    prompt: str
    system_prompt: str
    model: str                      # registry pattern, resolved to provider + id
    thinking: str = "medium"
    session_id: str                 # pi --session-id: creates or continues
    session_dir: str
    raw_output_path: str            # JSONL stream lands here
    tools: Optional[list[str]] = None
    extensions: list[str] = Field(default_factory=list)
    cwd: str = "."                  # set from run.repo_root — the codebase root agents work in


class UsageBreakdown(BaseModel):
    """Tokens and the dollars they cost, per component, summed over a call.

    Mirrors pi's `usage` shape one-for-one so the numbers reconcile with what
    pi itself reports: `input` EXCLUDES cache reads, which bill at their own
    (cheaper) rate — add them to learn the size of the prompt that was sent.
    """
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    # Thinking tokens. NOT a fifth component: measured across every session on
    # disk, reasoning is always <= output and the four components above always
    # sum to totalTokens, so reasoning is the thinking SHARE of output, billed
    # at the output rate. Report it nested under output, never added to it.
    reasoning_tokens: int = 0
    total_tokens: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_read_cost: float = 0.0
    cache_write_cost: float = 0.0
    total_cost: float = 0.0

    def add_turn(self, usage: dict, total_tokens: int) -> None:
        """Fold in one pi `message_end` usage object.

        `total_tokens` is passed in rather than re-derived: the caller already
        computes it pi's way (totalTokens, else the sum of the parts).
        """
        cost = usage.get("cost") or {}
        self.input_tokens += usage.get("input") or 0
        self.output_tokens += usage.get("output") or 0
        self.cache_read_tokens += usage.get("cacheRead") or 0
        self.cache_write_tokens += usage.get("cacheWrite") or 0
        self.reasoning_tokens += usage.get("reasoning") or 0
        self.total_tokens += total_tokens
        self.input_cost += cost.get("input") or 0.0
        self.output_cost += cost.get("output") or 0.0
        self.cache_read_cost += cost.get("cacheRead") or 0.0
        self.cache_write_cost += cost.get("cacheWrite") or 0.0
        self.total_cost += cost.get("total") or 0.0

    def merge(self, other: "UsageBreakdown") -> None:
        """Add another call's usage — a phase that retries spends more than once."""
        for field in self.model_fields:
            setattr(self, field, getattr(self, field) + getattr(other, field))


class PiResult(BaseModel):
    text: str = ""
    returncode: int = 0
    session_id: str = ""
    tokens: int = 0
    cost: float = 0.0
    usage: UsageBreakdown = Field(default_factory=UsageBreakdown)
    # Context occupancy after the LAST turn — not a sum. `tokens` bills every
    # turn; this is how full the window is right now, which is what the
    # visualizer's context bar measures against `context_window`.
    context_tokens: int = 0
    context_window: int = 0         # 0 when the registry declares no ceiling
