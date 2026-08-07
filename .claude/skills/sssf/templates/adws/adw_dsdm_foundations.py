#!/usr/bin/env -S uv run
# /// script
# dependencies = ["pydantic", "python-dotenv", "pyyaml", "rich"]
# ///
"""ADW DSDM Foundations — Feasibility and Foundations, ending at a human go/no-go.

Usage:
    uv run adws/adw_dsdm_foundations.py "<prompt or path/to/prompt.md>" \\
        --config adws/adw_sssf_config/sssf.config.dsdm.yaml \\
        [--adw-id a1b2c3d4] [--decide foundations_approval=go:"why"] \\
        [--decision-file path.json] [--decided-by "Name"]

Phases: engineer(request) -> business_analyst -> business_advisor
        -> technical_coordinator -> workshop_facilitator
        -> engineer(foundations_approval) -> git(record_decision)
        -> git(commit_foundations)

Nothing is built here. That is the point of the phase: DSDM's Foundations
answers what the business needs, why, in what order, within what constraints,
and on what architecture — and then STOPS, so a human decides whether any of it
is worth building before a line of code exists to make that decision feel
expensive.

The chain ends at a checkpoint the agents cannot answer. The facilitator frames
the question and recommends; `adw_modules/human.py` puts it to a person and
records what they said in `adws/adw_decisions/<adw_id>/`, which is a protected
path no agent may write. A `no_go` is not a failure of this ADW — the chain did
its job and the answer was no. It is a failure of the RUN, which is what
`run.finish(accepted=...)` exists to separate.

The decision is committed on its own, first, whatever it was — a `no_go` is the
verdict most worth keeping and the one this chain is most tempted to drop, since
nothing after it runs. Being tracked is also what makes it tamper-evident: a
later edit shows up in `git diff`, whereas an untracked file is fingerprinted by
`permissions.snapshot()` by NAME alone, so its content could be rewritten
unnoticed.

The foundations follow only after approval. An approved spec is a project
artifact; a declined one is a draft, and the working tree is where drafts
belong.

Run this once per project. Then run adw_dsdm_timebox.py against the same
--adw-id, as many times as the work needs — the human deciding whether to
launch another timebox IS the control loop, and it stays outside the software.
"""

import argparse
import sys

from adw_modules import agents, gates, git_helper, human, session, utils
from adw_modules.data_types import (AdvisoryOutput, AgentCall, DecisionPackOutput,
                                    FoundationsOutput, HumanDecisionRequest, PhaseParams,
                                    PrioritisedRequirementsOutput)

REQUIRED_AGENTS = ["business_analyst", "business_advisor", "technical_coordinator",
                   "workshop_facilitator"]

CHECKPOINT = "foundations_approval"

PACK_NOTES = (f"Prepare the pack for checkpoint '{CHECKPOINT}'. The human is deciding "
              "whether these foundations are firm enough to start building on, and "
              "whether the prioritised list is the right work. Read the PRL, the "
              "constraints, and both foundations documents before you frame the question.")


def main(prompt: str, config: str = "adws/adw_sssf_config/sssf.config.dsdm.yaml",
         adw_id: str | None = None, checkpoints: human.Checkpoints | None = None) -> int:
    cfg = agents.load_config(config)
    agents.validate(cfg, REQUIRED_AGENTS)
    run = session.ensure(cfg, adw_id)
    checkpoints = checkpoints or human.Checkpoints()

    with run.phase(PhaseParams(name="request", kind="engineer", owner=run.engineer,
                               description="Capture the incoming ask and pin the baseline")) as ph:
        ph.log(input=prompt, baseline=git_helper.short_sha(git_helper.rev("HEAD")))

    with run.phase(PhaseParams(name="requirements", kind="agent", owner="business_analyst",
                               description="Establish what the business needs, why, and in "
                                           "what priority order")) as ph:
        prl = ph.call(AgentCall(
            output_type=PrioritisedRequirementsOutput, prompt=prompt,
            # The MoSCoW gate is the one worth re-prompting on: a list that is
            # all Musts has no contingency, and a timebox with no contingency
            # can only hit its date by luck.
            gates=[gates.artifacts_exist, gates.files_non_empty,
                   gates.requirements_traceable, gates.moscow_balanced]))

    with run.phase(PhaseParams(name="constraints", kind="agent", owner="business_advisor",
                               description="Report the specialist limits the solution has "
                                           "to live within, each one sourced")) as ph:
        advice = ph.call(AgentCall(output_type=AdvisoryOutput, prompt=prompt, previous=prl,
                                   gates=[gates.artifacts_exist, gates.constraints_sourced]))

    with run.phase(PhaseParams(name="foundations", kind="agent", owner="technical_coordinator",
                               description="Design far enough ahead to start safely, and "
                                           "no further")) as ph:
        foundations = ph.call(AgentCall(
            output_type=FoundationsOutput, prompt=prompt, previous=advice,
            gates=[gates.artifacts_exist, gates.files_non_empty]))

    with run.phase(PhaseParams(name="decision_pack", kind="agent", owner="workshop_facilitator",
                               retries=1,
                               description="Turn everything produced so far into one question "
                                           "a person can answer")) as ph:
        foundations.notes_for_next_agent = PACK_NOTES
        pack = ph.call(AgentCall(
            output_type=DecisionPackOutput, prompt=prompt, previous=foundations,
            gates=[gates.artifacts_exist, gates.decision_is_the_humans]))

    with run.phase(PhaseParams(name=CHECKPOINT, kind="engineer", owner=run.engineer,
                               description="Hand control to the sponsor: build on these "
                                           "foundations, change them, or stop")) as ph:
        request = human.pack_to_request(pack, CHECKPOINT)
        # The coordinator's own doubt reaches the human as part of the question,
        # not as a footnote in a document they may not open.
        if not foundations.firm_enough_to_start:
            request.question = (f"{request.question}\n\nNOTE: the technical coordinator "
                                f"reports the foundations are NOT firm enough to start. "
                                f"Open: {'; '.join(foundations.open_questions) or 'unspecified'}")
        decision = human.decide(run, ph, request, checkpoints)

    # The answer is committed whatever it was. A `no_go` is the verdict most
    # worth keeping and the one this chain is most tempted to drop, since
    # nothing after it runs — and while it stays untracked, its content can be
    # rewritten without `permissions.snapshot()` ever noticing.
    with run.phase(PhaseParams(name=f"record_{CHECKPOINT}", kind="code", owner="git",
                               description="Put the sponsor's answer under version control, "
                                           "whichever way it went")) as ph:
        ph.log(sha=git_helper.commit_paths(human.record_message(decision),
                                           decision.records) or "(already recorded)",
               verdict=decision.verdict, record=decision.record_path)

    # Declined work stays in the working tree. A spec nobody approved is a
    # draft, and committing drafts is how a repo fills with plans that were
    # never agreed to but read exactly like plans that were.
    if decision.proceed:
        with run.phase(PhaseParams(name="commit_foundations", kind="code", owner="git",
                                   description="Land the approved foundations, naming the "
                                               "decision that let them through")) as ph:
            message = (foundations.commit_message
                       or f"sssf({run.adw_id}): {foundations.summary}")
            message += f"\n\nApproved at checkpoint {decision.checkpoint} by {decision.decided_by}"
            if decision.rationale:
                message += f": {decision.rationale}"
            # The decision was committed by the phase above, so an unchanged tree
            # here means the foundations documents were already on record — a
            # re-run against the same session, usually. Approved-and-unchanged is
            # not a failure, and crashing after the human said go would make it one.
            ph.log(sha=git_helper.commit_all(message) if git_helper.is_dirty()
                       else "(nothing to land — the foundations were already committed)",
                   decision=decision.record_path)

    return run.finish(
        accepted=decision.proceed,
        reason=f"{decision.decided_by} declined at {CHECKPOINT}"
               + (f": {decision.rationale}" if decision.rationale else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="inline text or a path to a prompt file")
    parser.add_argument("--config", default="adws/adw_sssf_config/sssf.config.dsdm.yaml")
    parser.add_argument("--adw-id", default=None, help="join or pin an existing session")
    human.Checkpoints.add_arguments(parser)
    args = parser.parse_args()
    sys.exit(main(utils.resolve_prompt(args.prompt), args.config, args.adw_id,
                  human.Checkpoints.from_args(args)))
