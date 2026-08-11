"""Validation gates: verify the envelope's CLAIMS, never guesses.

A gate is `gate(envelope, run) -> GateReport` — one check per item it looked at.
Violations are derived from the failed checks and sent back to the SAME agent
session as a correction. Every check is recorded either way, so a green gate
says WHAT it verified instead of only that it passed.

Gates check what is mechanically checkable; plan quality is a reviewer's job.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import git_helper
from .data_types import (CDF_BAND_THRESHOLDS, CDF_BANDS, CDF_DIMENSIONS, DSDM_PRINCIPLES,
                         UCAF_ALIGNMENT_DIMENSIONS, UCAF_ALIGNMENT_WEIGHTS,
                         UCAF_CONSTITUTIONAL_PILLARS, UCAF_REASONING_STRATEGIES,
                         EnvelopeBase, GateReport)

TAIL_CHARS = 1000        # command output kept as evidence on a failure


def _size(path: Path) -> str:
    n = path.stat().st_size
    return f"{n}B" if n < 1024 else f"{n / 1024:.1f}KB"


def artifacts_exist(envelope: EnvelopeBase, run) -> GateReport:
    report = GateReport()
    for a in envelope.artifacts:
        p = Path(a)
        report.check(a, p.exists(),
                     f"exists, {_size(p)}" if p.exists() else "declared artifact does not exist")
    return report


def files_non_empty(envelope: EnvelopeBase, run) -> GateReport:
    report = GateReport()
    for a in envelope.artifacts:
        p = Path(a)
        if not (p.exists() and p.is_file()):
            continue                       # existence is artifacts_exist's job
        empty = p.stat().st_size == 0
        report.check(a, not empty, "declared artifact is empty" if empty else _size(p))
    return report


def json_parses(envelope: EnvelopeBase, run) -> GateReport:
    report = GateReport()
    for a in envelope.artifacts:
        p = Path(a)
        if p.suffix != ".json" or not p.exists():
            continue
        try:
            parsed = json.loads(p.read_text())
            report.check(a, True, f"parses, {type(parsed).__name__}")
        except json.JSONDecodeError as e:
            report.check(a, False, f"declared JSON artifact does not parse: {e}")
    return report


def diff_matches_claims(envelope: EnvelopeBase, run) -> GateReport:
    """Every file claimed changed must exist on disk — or be a recorded deletion.

    Deleting a file IS changing it, and an agent that reports the deletion is
    being accurate. Checking existence alone punished exactly that: a developer
    that replaced a placeholder test with real ones, and said so, failed the
    gate for telling the truth. So a path that is gone is accepted when git
    records it as deleted, and rejected when git has never heard of it — which
    is the case this gate exists to catch.
    """
    report = GateReport()
    claims = list(getattr(envelope, "changed_files", []))
    deleted = set(git_helper.deleted_files()) if claims else set()
    for f in claims:
        p = Path(f)
        if p.exists():
            report.check(f, True, f"exists, {_size(p)}")
        elif f in deleted:
            report.check(f, True, "deleted, and git agrees")
        else:
            report.check(f, False, "claimed changed file does not exist, and git "
                                   "records no deletion of it")
    return report


def verdict_consistent(envelope: EnvelopeBase, run) -> GateReport:
    """A review's verdict must agree with the findings it just wrote down.

    Nothing here judges the code — that is the reviewer's job. This checks the
    envelope against itself: an approval that ships blocking items, or a
    rejection that names no problem, is a claim the harness can refute without
    reading a line of the diff.
    """
    report = GateReport()
    approved = bool(getattr(envelope, "approved", False))
    blocking = list(getattr(envelope, "blocking", []))
    unmet = [f.requirement for f in getattr(envelope, "findings", []) if not f.met]

    report.check("approved vs blocking", not (approved and blocking),
                 "no blocking items" if not blocking
                 else f"{len(blocking)} blocking item(s) while approved=true"
                 if approved else f"{len(blocking)} blocking item(s), not approved")
    report.check("approved vs findings", not (approved and unmet),
                 "every requirement met" if not unmet
                 else f"{len(unmet)} unmet requirement(s) while approved=true"
                 if approved else f"{len(unmet)} unmet requirement(s), not approved")
    report.check("rejection names a problem", approved or bool(blocking or unmet),
                 "verdict is supported" if approved or blocking or unmet
                 else "approved=false but no blocking item or unmet requirement was given")
    return report


# ── DSDM gates ───────────────────────────────────────────────────────────────
#
# A principle nobody checks is a slogan. Each gate below is one DSDM rule made
# mechanical, so the rule survives a model that drifts, a prompt someone edits,
# and a run at 3am with nobody reading the console.

# DSDM's own rule of thumb for a balanced timebox: no more than 60% of effort on
# Musts, and at least 20% held as Coulds — the contingency that lets a fixed
# deadline be met by descoping instead of slipping. A list that is all Musts has
# no contingency, so "deliver on time" becomes a wish.
MAX_MUST_SHARE = 0.60
MIN_COULD_SHARE = 0.20


def _requirements(envelope: EnvelopeBase) -> list:
    return list(getattr(envelope, "requirements", []))


def requirements_traceable(envelope: EnvelopeBase, run) -> GateReport:
    """Every requirement carries a unique id, a WHY, and something testable.

    Principle 1 — focus on the business need. A requirement with no business
    justification is a preference; a requirement with no acceptance criterion
    cannot be shown to be met, so nobody can ever say the increment is done.
    """
    report = GateReport()
    requirements = _requirements(envelope)
    if not requirements:
        return report.check("requirements", False, "no requirements were produced")

    seen: set[str] = set()
    for r in requirements:
        label = r.id or "(no id)"
        report.check(f"{label} id", bool(r.id) and r.id not in seen,
                     "duplicate id" if r.id in seen else
                     "missing id" if not r.id else "unique")
        seen.add(r.id)
        report.check(f"{label} justification", bool(r.business_justification.strip()),
                     "no business justification — principle 1 requires the WHY"
                     if not r.business_justification.strip() else "stated")
        report.check(f"{label} criteria", bool(r.acceptance_criteria),
                     "no acceptance criteria — nothing could ever show this is met"
                     if not r.acceptance_criteria else
                     f"{len(r.acceptance_criteria)} criterion(s)")
        # A Must is what the increment is not viable without, so it is the one
        # priority whose criteria have to name who settles them.
        if r.moscow == "must":
            unowned = [c.id for c in r.acceptance_criteria if not c.verified_by.strip()]
            report.check(f"{label} verifiers", not unowned,
                         f"Must criteria with no verified_by: {', '.join(unowned)}"
                         if unowned else "every criterion names its verifier")
    return report


def moscow_balanced(envelope: EnvelopeBase, run) -> GateReport:
    """The Must/Should/Could split, measured on effort rather than asserted.

    Principle 2 — deliver on time. The deadline is fixed, so the only give in a
    timebox is priority. Contingency that does not exist cannot be spent.
    """
    report = GateReport()
    requirements = [r for r in _requirements(envelope) if r.moscow != "wont"]
    total = sum(max(0, r.effort) for r in requirements)
    if total <= 0:
        return report.check("effort", False,
                            "no requirement carries effort — the MoSCoW split "
                            "cannot be measured, only claimed")

    share = {level: sum(r.effort for r in requirements if r.moscow == level) / total
             for level in ("must", "should", "could")}
    report.check("must share", share["must"] <= MAX_MUST_SHARE,
                 f"{share['must']:.0%} of effort is Must "
                 f"(DSDM ceiling {MAX_MUST_SHARE:.0%}) — "
                 f"re-rank what the increment is genuinely not viable without"
                 if share["must"] > MAX_MUST_SHARE
                 else f"{share['must']:.0%} of effort, within {MAX_MUST_SHARE:.0%}")
    report.check("could share", share["could"] >= MIN_COULD_SHARE,
                 f"only {share['could']:.0%} of effort is Could "
                 f"(DSDM floor {MIN_COULD_SHARE:.0%}) — there is no contingency "
                 f"to descope, so the date can only be met by luck"
                 if share["could"] < MIN_COULD_SHARE
                 else f"{share['could']:.0%} of effort held as contingency")
    return report


def constraints_sourced(envelope: EnvelopeBase, run) -> GateReport:
    """A specialist constraint names where it came from, or it is an opinion."""
    report = GateReport()
    for c in getattr(envelope, "constraints", []):
        report.check(f"{c.area}: {c.constraint[:60]}", bool(c.source.strip()),
                     "no source — cite the file:line, standard, or document"
                     if not c.source.strip() else c.source)
    return report


def decision_is_the_humans(envelope: EnvelopeBase, run) -> GateReport:
    """A decision pack must leave the decision open, and make it answerable.

    Principle 8 — demonstrate control. This is the gate that keeps the human in
    the loop rather than merely mentioning them in a prompt: a pack that arrives
    pre-decided, or with one option, or with no stated cost of doing nothing, is
    not a choice being offered. It is a choice already taken.
    """
    report = GateReport()
    options = list(getattr(envelope, "options", []))
    recommendation = str(getattr(envelope, "recommendation", "") or "")
    decided = bool(getattr(envelope, "decided", False))
    ids = {o.id for o in options}

    report.check("verdict withheld", not decided,
                 "the pack reports a decision — the verdict is the human's, and "
                 "an agent that fills it in has removed them from the loop"
                 if decided else "no verdict recorded, as required")
    report.check("real choice", len(options) >= 2,
                 f"only {len(options)} option — a single option is a decision "
                 f"already made" if len(options) < 2 else f"{len(options)} options")
    report.check("question stated", bool(str(getattr(envelope, "question", "")).strip()),
                 "no question — the human is not told what they are deciding"
                 if not str(getattr(envelope, "question", "")).strip() else "stated")
    report.check("recommendation names an option", not recommendation or recommendation in ids,
                 f"recommendation {recommendation!r} is not one of {sorted(ids)}"
                 if recommendation and recommendation not in ids
                 else recommendation or "none offered")
    report.check("cost of doing nothing",
                 bool(str(getattr(envelope, "if_no_decision", "")).strip()),
                 "if_no_decision is empty — a human cannot weigh a choice without "
                 "knowing what happens if they decline"
                 if not str(getattr(envelope, "if_no_decision", "")).strip() else "stated")
    for o in options:
        report.check(f"{o.id} consequence", bool(o.consequence.strip()),
                     "no consequence stated" if not o.consequence.strip() else "stated")
    return report


def musts_not_descoped(envelope: EnvelopeBase, run) -> GateReport:
    """No agent drops a Must. Descoping a Must is the human's call, not code's.

    Principle 2 again, from the other side: the deadline moves for nobody, but
    what a fixed deadline may cost is Coulds and Shoulds. A Must that will not
    fit is an escalation, and it has to surface as one.
    """
    report = GateReport()
    for d in getattr(envelope, "deferred", []):
        report.check(f"{d.requirement_id} deferred", d.moscow != "must",
                     "a Must was deferred — raise it at the checkpoint instead; "
                     "dropping it is the sponsor's decision"
                     if d.moscow == "must" else f"{d.moscow}, deferrable")
        report.check(f"{d.requirement_id} reason", bool(d.reason.strip()),
                     "deferred with no reason" if not d.reason.strip() else d.reason[:60])
    return report


def acceptance_consistent(envelope: EnvelopeBase, run) -> GateReport:
    """An acceptance verdict must agree with the criteria it just ruled on.

    Principle 4 — never compromise quality. Quality is the agreed level, not a
    sliding one, so `accepted` is arithmetic over the results, not a mood.
    """
    report = GateReport()
    accepted = bool(getattr(envelope, "accepted", False))
    results = list(getattr(envelope, "results", []))
    unmet = list(getattr(envelope, "unmet_musts", []))
    failed_musts = sorted({r.requirement_id for r in results
                           if r.moscow == "must" and not r.passed})

    report.check("ruled on something", bool(results),
                 "no criterion was ruled on" if not results else f"{len(results)} ruling(s)")
    report.check("accepted vs Must results", not (accepted and failed_musts),
                 f"accepted=true with failing Musts: {', '.join(failed_musts)}"
                 if accepted and failed_musts else
                 f"{len(failed_musts)} failing Must(s)" if failed_musts else "no failing Must")
    report.check("accepted vs unmet_musts", not (accepted and unmet),
                 f"accepted=true while unmet_musts lists {', '.join(unmet)}"
                 if accepted and unmet else "consistent")
    report.check("unmet_musts matches results", set(unmet) == set(failed_musts),
                 f"unmet_musts {sorted(set(unmet))} does not match the failing "
                 f"Musts in results {failed_musts}"
                 if set(unmet) != set(failed_musts) else "agrees with the rulings")
    report.check("rejection names a gap", accepted or bool(failed_musts or unmet
                                                          or [r for r in results if not r.passed]),
                 "accepted=false but every criterion passed and nothing was named"
                 if not accepted and not [r for r in results if not r.passed] else "supported")
    return report


def all_principles_ruled(envelope: EnvelopeBase, run) -> GateReport:
    """The coach rules on all eight principles, and names a fix for each breach.

    A partial audit reads like a clean one. Requiring the full set means silence
    on a principle is impossible — the coach either upholds it with evidence or
    says what to do about it.
    """
    report = GateReport()
    findings = list(getattr(envelope, "findings", []))
    ruled = {f.principle for f in findings}
    for principle in DSDM_PRINCIPLES:
        report.check(principle, principle in ruled,
                     "not ruled on" if principle not in ruled else "ruled")
    unknown = sorted(ruled - set(DSDM_PRINCIPLES))
    report.check("principle names", not unknown,
                 f"not DSDM principles: {', '.join(unknown)}" if unknown
                 else "all names are from the canonical list")
    for f in findings:
        if not f.upheld:
            report.check(f"{f.principle} corrective action", bool(f.corrective_action.strip()),
                         "breach reported with no corrective action"
                         if not f.corrective_action.strip() else "stated")
    return report


# ── UCAF gates ───────────────────────────────────────────────────────────────
#
# UCAF's claims are the kind that sound strongest exactly when they are least
# checked: a named reasoning strategy, a confidence figure, an ethical review, a
# prior-art sweep. Each gate below turns one of those into something the harness
# can refute without believing the agent.

# Above this, a claim is asserting near-certainty and has to cite something.
CONFIDENCE_NEEDS_EVIDENCE = 0.70

# A weighted alignment score below this is not compliant, whatever the envelope
# says. UCAF's own threshold, restated here so the gate does not have to trust
# the agent's arithmetic OR its judgement.
MIN_ALIGNMENT_SCORE = 60.0


def strategy_is_known(envelope: EnvelopeBase, run) -> GateReport:
    """Every inference names one of UCAF's eight strategies, verbatim.

    The list is closed. An agent that invents a ninth is not reasoning in a way
    anyone can audit — it is giving an ordinary guess a principled-sounding
    name, which is the failure this gate exists to make impossible.
    """
    report = GateReport()
    inferences = list(getattr(envelope, "inferences", []))
    if not inferences:
        return report.check("inferences", False, "no inference was drawn")
    for inf in inferences:
        known = inf.strategy in UCAF_REASONING_STRATEGIES
        report.check(f"{inf.id} strategy", known,
                     f"{inf.strategy!r} is not a UCAF strategy — one of "
                     f"{', '.join(UCAF_REASONING_STRATEGIES)}" if not known
                     else inf.strategy)
    return report


def inferences_are_evidenced(envelope: EnvelopeBase, run) -> GateReport:
    """A confident claim cites something; a derived one names what it came from.

    Confidence is cheap to type. This gate makes it expensive above
    CONFIDENCE_NEEDS_EVIDENCE, and checks that hypothesis ids an inference
    claims to rest on are hypotheses this envelope actually raised.
    """
    report = GateReport()
    hypotheses = list(getattr(envelope, "hypotheses", []))
    known_ids = {h.id for h in hypotheses}

    for h in hypotheses:
        in_range = 0.0 <= h.confidence <= 1.0
        report.check(f"{h.id} confidence", in_range,
                     f"{h.confidence} is outside 0-1" if not in_range else f"{h.confidence}")
        if h.confidence >= CONFIDENCE_NEEDS_EVIDENCE:
            report.check(f"{h.id} evidence", bool(h.evidence),
                         f"confidence {h.confidence} with no evidence — cite a "
                         f"file:line, a command, or lower the confidence"
                         if not h.evidence else f"{len(h.evidence)} citation(s)")

    for inf in getattr(envelope, "inferences", []):
        unknown = [h for h in inf.from_hypotheses if h not in known_ids]
        report.check(f"{inf.id} provenance", not unknown,
                     f"rests on hypotheses this envelope never raised: "
                     f"{', '.join(unknown)}" if unknown else "traceable")
        if inf.confidence >= CONFIDENCE_NEEDS_EVIDENCE:
            report.check(f"{inf.id} evidence", bool(inf.evidence or inf.from_hypotheses),
                         f"confidence {inf.confidence} resting on nothing"
                         if not (inf.evidence or inf.from_hypotheses) else "supported")
    return report


def corrections_applied(envelope: EnvelopeBase, run) -> GateReport:
    """A self-correction pass that found something must have done something.

    Detecting an issue and leaving it standing is worse than not looking: the
    run now carries a written record saying the reasoning was checked. `clean`
    is arithmetic over `issues`, so an agent cannot declare itself clean and
    list a contradiction in the same breath.
    """
    report = GateReport()
    issues = list(getattr(envelope, "issues", []))
    clean = bool(getattr(envelope, "clean", False))
    uncorrected = [i for i in issues if not i.correction.strip()]

    report.check("clean vs issues", not (clean and issues),
                 f"clean=true while reporting {len(issues)} issue(s)"
                 if clean and issues else
                 "no issues found" if clean else f"{len(issues)} issue(s) reported")
    report.check("issues corrected", not uncorrected,
                 f"detected and left standing: {', '.join(i.kind for i in uncorrected)}"
                 if uncorrected else "every issue carries a correction")
    return report


def all_dimensions_scored(envelope: EnvelopeBase, run) -> GateReport:
    """DAVS rules on all five dimensions, and the weighted score is the weights.

    A partial ethical review reads exactly like a clean one, which is why the
    full set is required rather than encouraged. The weighted score is
    recomputed here from UCAF's published weights: an agent that scores five
    dimensions honestly and then reports a total it likes better is caught by
    arithmetic rather than by a reviewer noticing.
    """
    report = GateReport()
    scores = list(getattr(envelope, "scores", []))
    by_dimension = {s.dimension: s for s in scores}

    for dimension in UCAF_ALIGNMENT_DIMENSIONS:
        report.check(dimension, dimension in by_dimension,
                     "not scored" if dimension not in by_dimension
                     else f"{by_dimension[dimension].score}")
    unknown = sorted(set(by_dimension) - set(UCAF_ALIGNMENT_DIMENSIONS))
    report.check("dimension names", not unknown,
                 f"not UCAF dimensions: {', '.join(unknown)}" if unknown else "all five, named")

    if len(by_dimension) == len(UCAF_ALIGNMENT_DIMENSIONS):
        expected = sum(by_dimension[d].score * UCAF_ALIGNMENT_WEIGHTS[d]
                       for d in UCAF_ALIGNMENT_DIMENSIONS)
        claimed = float(getattr(envelope, "weighted_score", 0.0))
        report.check("weighted score", abs(expected - claimed) <= 0.5,
                     f"reported {claimed:.1f}, the published weights give "
                     f"{expected:.1f}" if abs(expected - claimed) > 0.5
                     else f"{claimed:.1f}, matches the weights")
    return report


def alignment_verdict_consistent(envelope: EnvelopeBase, run) -> GateReport:
    """`compliant` must agree with the breaches and the score beside it.

    This is the gate the cognitive chain hangs on: DAVS is the only agent whose
    verdict stops a run, so its verdict is the one most worth being unable to
    fudge. Nothing here judges ethics — it checks the envelope against itself.
    """
    report = GateReport()
    compliant = bool(getattr(envelope, "compliant", False))
    breaches = list(getattr(envelope, "breaches", []))
    critical = [b for b in breaches if b.severity in ("high", "critical")]
    score = float(getattr(envelope, "weighted_score", 0.0))

    report.check("compliant vs breaches", not (compliant and critical),
                 f"compliant=true with {len(critical)} high/critical breach(es): "
                 f"{', '.join(b.pillar for b in critical)}" if compliant and critical
                 else f"{len(critical)} high/critical breach(es)" if critical
                 else "no serious breach")
    report.check("compliant vs score", not (compliant and score < MIN_ALIGNMENT_SCORE),
                 f"compliant=true at {score:.1f}, below the {MIN_ALIGNMENT_SCORE:.0f} "
                 f"floor" if compliant and score < MIN_ALIGNMENT_SCORE
                 else f"{score:.1f}")
    report.check("newspaper test",
                 bool(str(getattr(envelope, "newspaper_test", "")).strip()),
                 "the Dual Newspaper Test was not applied — say how this reads "
                 "reported as a scandal AND reported as excessive caution"
                 if not str(getattr(envelope, "newspaper_test", "")).strip() else "applied")

    unknown = sorted({b.pillar for b in breaches} - set(UCAF_CONSTITUTIONAL_PILLARS))
    report.check("pillar names", not unknown,
                 f"not constitutional pillars: {', '.join(unknown)}" if unknown
                 else "named from the canonical seven")
    for b in critical:
        report.check(f"{b.pillar} remedy", bool(b.remedy.strip()),
                     f"{b.severity} breach with no remedy" if not b.remedy.strip() else "stated")
    return report


def risks_are_contained(envelope: EnvelopeBase, run) -> GateReport:
    """A pattern ERA classified as a risk names its containment.

    ERA is observational — it does not fix what it finds. But a risk reported
    with no containment is a note, and the point of detecting emergent behaviour
    is that somebody can act on it before it compounds.
    """
    report = GateReport()
    patterns = list(getattr(envelope, "patterns", []))
    if not patterns:
        return report.check("patterns", True,
                            "no emergent pattern detected — a legitimate finding")
    for p in patterns:
        in_range = 0.0 <= p.novelty <= 1.0
        report.check(f"{p.id} novelty", in_range,
                     f"{p.novelty} is outside 0-1" if not in_range else f"{p.novelty}")
        report.check(f"{p.id} evidence", bool(p.evidence),
                     "classified with no evidence" if not p.evidence
                     else f"{len(p.evidence)} citation(s)")
        if p.classification == "risk":
            report.check(f"{p.id} containment", bool(p.containment.strip()),
                         "classified a risk with no containment"
                         if not p.containment.strip() else "stated")
    return report


def gates_not_bypassed(envelope: EnvelopeBase, run) -> GateReport:
    """A candidate's band respects its own scores and its own disqualifiers.

    CDFA's whole claim is that a well-told story cannot talk its way into the
    top band, and that claim rests on gates being non-bypassable. So the band is
    recomputed here from the composite score and then walked down by the
    disqualifiers the agent itself declared: a BLOCKING one floors the candidate
    at INCREMENTAL, a DEMOTING one drops it a band. An agent that scores
    honestly and bands generously is caught by the same arithmetic UCAF uses.
    """
    report = GateReport()
    candidates = list(getattr(envelope, "candidates", []))
    if not candidates:
        return report.check("candidates", False, "no candidate was assessed")

    for c in candidates:
        scored = {s.dimension for s in c.scores}
        missing = [d for d in CDF_DIMENSIONS if d not in scored]
        report.check(f"{c.name} dimensions", not missing,
                     f"not scored: {', '.join(missing)}" if missing
                     else f"all {len(CDF_DIMENSIONS)} scored")

        raw = max((b for b in CDF_BANDS if c.composite >= CDF_BAND_THRESHOLDS[b]),
                  key=CDF_BANDS.index, default="INCREMENTAL")
        report.check(f"{c.name} raw band", c.band_before_gates == raw,
                     f"composite {c.composite} is {raw}, not "
                     f"{c.band_before_gates}" if c.band_before_gates != raw else raw)

        severities = {d.severity for d in c.disqualifiers}
        if "BLOCKING" in severities:
            ceiling = "INCREMENTAL"
        else:
            demotions = sum(1 for d in c.disqualifiers if d.severity == "DEMOTING")
            ceiling = CDF_BANDS[max(0, CDF_BANDS.index(raw) - demotions)]
        held = CDF_BANDS.index(c.band) <= CDF_BANDS.index(ceiling)
        report.check(f"{c.name} band after gates", held,
                     f"banded {c.band}; its own disqualifiers cap it at {ceiling}"
                     if not held else f"{c.band}, within {ceiling}")

        for d in c.disqualifiers:
            report.check(f"{c.name}/{d.code} resolution", bool(d.resolution.strip()),
                         "no resolution — say what would have to be true to clear it"
                         if not d.resolution.strip() else "stated")
    return report


def prior_art_is_not_a_clearance(envelope: EnvelopeBase, run) -> GateReport:
    """A prior-art sweep reports what it found and what it could not reach.

    The invariant UCAF pins in its adapters, restated where this roster can
    enforce it: an automated search must never read as a freedom-to-operate
    opinion. The databases are partial, publication lags filing by up to
    eighteen months, and only a qualified human adjudication decides whether a
    hit stands in the way. So `blocking` stays false, the human is always
    required, and a sweep that names no coverage gap has not understood what it
    just did — every one of these searches has gaps, and saying so is the
    difference between evidence and a clearance.
    """
    report = GateReport()
    report.check("not blocking", getattr(envelope, "blocking", False) is False,
                 "a prior-art search set blocking=true — only a human "
                 "adjudication may block a candidate")
    report.check("human adjudication required",
                 getattr(envelope, "requires_human_adjudication", False) is True,
                 "the sweep does not require adjudication — an automated search "
                 "is evidence, never a clearance")
    databases = list(getattr(envelope, "databases_searched", []))
    report.check("databases named", bool(databases),
                 "no database named — an unsourced search cannot be reproduced"
                 if not databases else ", ".join(databases))
    report.check("queries recorded", bool(getattr(envelope, "queries", [])),
                 "no query recorded — nobody can rerun or widen this search"
                 if not getattr(envelope, "queries", []) else "recorded")
    report.check("coverage gaps stated", bool(getattr(envelope, "coverage_gaps", [])),
                 "no coverage gap stated — every search of these databases has "
                 "them (unpublished filings, non-participating offices, "
                 "non-patent literature); silence here reads as a clearance"
                 if not getattr(envelope, "coverage_gaps", []) else "stated")
    for hit in getattr(envelope, "hits", []):
        report.check(f"{hit.database} {hit.identifier}", bool(hit.relevance.strip()),
                     "hit reported with no stated relevance"
                     if not hit.relevance.strip() else hit.relevance[:60])
    return report


def tests_pass(command: str):
    """Gate factory: the given shell command must exit 0."""
    def gate(envelope: EnvelopeBase, run) -> GateReport:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        ok = result.returncode == 0
        note = f"exit {result.returncode}"
        if not ok:
            note += "\n" + (result.stdout + result.stderr)[-TAIL_CHARS:]
        return GateReport().check(command, ok, note)
    gate.__name__ = f"tests_pass({command})"
    return gate
