#!/usr/bin/env -S uv run
# /// script
# dependencies = ["pydantic", "python-dotenv", "pyyaml", "rich"]
# ///
"""ADW UCAF Category — is this category-defining? Scored, gated, adjudicated by a human.

Usage:
    uv run adws/adw_ucaf_category.py "<idea or path/to/idea.md>" \\
        --config adws/adw_sssf_config/sssf.config.ucaf.yaml \\
        [--adw-id a1b2c3d4] [--skip-emergence] \\
        [--decide prior_art_adjudication=go:"why"] \\
        [--decision-file path.json] [--decided-by "Name"]

Phases: engineer(request) -> emergence_researcher -> category_feature_architect
        -> prior_art_searcher -> workshop_facilitator
        -> engineer(prior_art_adjudication) -> git(record_decision)
        -> git(commit_assessment)

The episodic half of the UCAF roster. ERA and CDFA are the same instinct pointed
in opposite directions — ERA finds the pattern nobody predicted, CDFA proposes
the mechanism nobody has built — and a friction ERA surfaces is exactly what
CDFA consumes. In UCAF that hand-off is manual. Here it is the chain, which is
the one thing this roster adds to the model it ports.

**The prior-art adjudication is the reason this ADW ends where it does.** The
sweep is evidence: patent applications publish up to eighteen months after
filing, coverage varies by office, and the term nobody thought of is the one
that finds the blocking document. So no adapter, no agent and no gate in this
chain may conclude that the way is clear. `PriorArtOutput.blocking` is typed
`Literal[False]`, `gates.prior_art_is_not_a_clearance` refuses an envelope that
says otherwise, and the verdict is a human's — recorded in `adws/adw_decisions/`,
a protected path no agent may write. An automated sweep that could clear a
candidate would be wrong in exactly the cases that matter, and wrong
reassuringly.

A `no_go` is not a failure of this chain. The chain did its job and the answer
was that the prior art stands in the way, which is the most expensive thing to
learn late and the cheapest to learn here. It is a failure of the RUN, which is
what `run.finish(accepted=...)` exists to separate.

The assessment follows only after adjudication. An adjudicated assessment is a
project artifact; an unadjudicated one is a draft that reads exactly like a
cleared one, and the working tree is where drafts belong.
"""

import argparse
import sys

from adw_modules import agents, gates, git_helper, human, session, utils
from adw_modules.data_types import (AgentCall, CategoryAnalysisOutput, DecisionPackOutput,
                                    EmergenceOutput, PhaseParams, PriorArtOutput)

REQUIRED_AGENTS = ["category_feature_architect", "prior_art_searcher", "workshop_facilitator"]

# Skipped with --skip-emergence, when the engineer already has the idea and does
# not need one synthesised from the system's own unpredicted behaviour.
EMERGENCE_AGENT = "emergence_researcher"

CHECKPOINT = "prior_art_adjudication"

PACK_NOTES = (
    f"Prepare the pack for checkpoint '{CHECKPOINT}'. The human is adjudicating the "
    "prior art: do the hits found stand in the way of this candidate, or not? Read "
    "the assessment and the prior-art report first. The sweep is EVIDENCE, not a "
    "clearance — say so in the options, and put the coverage gaps in front of the "
    "adjudicator rather than in a footnote. What was not searched matters as much "
    "as what came back.")


def main(prompt: str, config: str = "adws/adw_sssf_config/sssf.config.ucaf.yaml",
         adw_id: str | None = None, skip_emergence: bool = False,
         checkpoints: human.Checkpoints | None = None) -> int:
    cfg = agents.load_config(config)
    agents.validate(cfg, REQUIRED_AGENTS + ([] if skip_emergence else [EMERGENCE_AGENT]))
    run = session.ensure(cfg, adw_id)
    checkpoints = checkpoints or human.Checkpoints()

    with run.phase(PhaseParams(name="request", kind="engineer", owner=run.engineer,
                               description="Capture the idea under assessment and pin "
                                           "the baseline")) as ph:
        ph.log(input=prompt, baseline=git_helper.short_sha(git_helper.rev("HEAD")))

    signals = None
    if not skip_emergence:
        with run.phase(PhaseParams(name="emergence", kind="agent", owner=EMERGENCE_AGENT,
                                   description="Find what this system already does that "
                                               "nobody designed — the seed a candidate "
                                               "grows from")) as ph:
            signals = ph.call(AgentCall(
                output_type=EmergenceOutput, prompt=prompt,
                gates=[gates.artifacts_exist, gates.risks_are_contained]))

    with run.phase(PhaseParams(name="assessment", kind="agent",
                               owner="category_feature_architect", retries=1,
                               description="Score the candidates on eight dimensions and "
                                           "band what survives the disqualifier "
                                           "gates")) as ph:
        assessment = ph.call(AgentCall(
            output_type=CategoryAnalysisOutput, prompt=prompt, previous=signals,
            # The gate that carries the model: the band is recomputed from the
            # composite and then walked down by the candidate's own declared
            # disqualifiers. An agent that scores honestly and bands generously
            # is caught by arithmetic rather than by someone noticing.
            gates=[gates.artifacts_exist, gates.files_non_empty, gates.gates_not_bypassed]))

    with run.phase(PhaseParams(name="prior_art", kind="agent", owner="prior_art_searcher",
                               description="Search the IP databases for what already "
                                           "exists, and record what could not be "
                                           "reached")) as ph:
        prior_art = ph.call(AgentCall(
            output_type=PriorArtOutput, prompt=prompt, previous=assessment,
            gates=[gates.artifacts_exist, gates.prior_art_is_not_a_clearance]))

    with run.phase(PhaseParams(name="decision_pack", kind="agent", owner="workshop_facilitator",
                               retries=1,
                               description="Turn the assessment and the sweep into one "
                                           "question a person can answer")) as ph:
        prior_art.notes_for_next_agent = PACK_NOTES
        pack = ph.call(AgentCall(
            output_type=DecisionPackOutput, prompt=prompt, previous=prior_art,
            gates=[gates.artifacts_exist, gates.decision_is_the_humans]))

    with run.phase(PhaseParams(name=CHECKPOINT, kind="engineer", owner=run.engineer,
                               description="Hand the prior art to a person: does it "
                                           "stand in the way, or not")) as ph:
        request = human.pack_to_request(pack, CHECKPOINT)
        # What the sweep could NOT reach travels with the question rather than
        # sitting in a report the adjudicator may not open. A gap they never saw
        # is a gap they cannot weigh, and this decision is only as good as the
        # adjudicator's picture of how partial the evidence is.
        if prior_art.coverage_gaps:
            request.question = (f"{request.question}\n\nCOVERAGE GAPS — the sweep did "
                                f"not reach: {'; '.join(prior_art.coverage_gaps)}")
        blocking = [d for c in assessment.candidates for d in c.disqualifiers
                    if d.severity == "BLOCKING"]
        if blocking:
            request.question = (f"{request.question}\n\nNOTE: the assessment carries "
                                f"{len(blocking)} BLOCKING disqualifier(s) independent of "
                                f"prior art: {'; '.join(d.code for d in blocking)}")
        decision = human.decide(run, ph, request, checkpoints)

    # Committed whichever way it went. A `no_go` on prior art is the verdict
    # most worth keeping and the one this chain is most tempted to drop, since
    # nothing after it runs — and while it stays untracked, its content can be
    # rewritten without `permissions.snapshot()` ever noticing.
    with run.phase(PhaseParams(name=f"record_{CHECKPOINT}", kind="code", owner="git",
                               description="Put the adjudication under version control, "
                                           "whichever way it went")) as ph:
        ph.log(sha=git_helper.commit_paths(human.record_message(decision),
                                           decision.records) or "(already recorded)",
               verdict=decision.verdict, record=decision.record_path)

    # An unadjudicated assessment reads exactly like a cleared one, which is the
    # single most dangerous document this chain can produce. It stays a draft.
    if decision.proceed:
        with run.phase(PhaseParams(name="commit_assessment", kind="code", owner="git",
                                   description="Land the adjudicated assessment, naming "
                                               "the decision that let it through")) as ph:
            message = (assessment.commit_message
                       or f"sssf({run.adw_id}): {assessment.summary}")
            message += f"\n\nAdjudicated at checkpoint {decision.checkpoint} by {decision.decided_by}"
            if decision.rationale:
                message += f": {decision.rationale}"
            ph.log(sha=git_helper.commit_all(message) if git_helper.is_dirty()
                       else "(nothing to land — the assessment was already committed)",
                   decision=decision.record_path)

    return run.finish(
        accepted=decision.proceed,
        reason=f"{decision.decided_by} ruled the prior art blocking at {CHECKPOINT}"
               + (f": {decision.rationale}" if decision.rationale else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="inline text or a path to an idea file")
    parser.add_argument("--config", default="adws/adw_sssf_config/sssf.config.ucaf.yaml")
    parser.add_argument("--adw-id", default=None, help="join or pin an existing session")
    parser.add_argument("--skip-emergence", action="store_true",
                        help="assess the idea as given, without synthesising candidates "
                             "from the system's own unpredicted behaviour")
    human.Checkpoints.add_arguments(parser)
    args = parser.parse_args()
    sys.exit(main(utils.resolve_prompt(args.prompt), args.config, args.adw_id,
                  args.skip_emergence, human.Checkpoints.from_args(args)))
