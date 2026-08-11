#!/usr/bin/env -S uv run
# /// script
# dependencies = ["pydantic", "python-dotenv", "pyyaml", "rich"]
# ///
"""ADW UCAF Cognitive — the standing cognitive loop, gated by the constitution.

Usage:
    uv run adws/adw_ucaf_cognitive.py "<goal or path/to/goal.md>" \\
        --config adws/adw_sssf_config/sssf.config.ucaf.yaml \\
        [--adw-id a1b2c3d4] [--journey]

Phases: engineer(goal) -> memory_architect -> capability_specialist
        -> [interaction_specialist] -> reasoning_architect -> self_corrector
        -> alignment_gatekeeper -> memory_consolidator -> git(commit_memory)

UCAF's `UCAFRalphOrchestrator` sweeps eleven phases across five standing agents:
memory initialisation and context loading (DMA), capability discovery and
composition (CIS), reasoning planning and execution then self-correction (ARA),
memory consolidation (DMA), and interaction analysis, journey mapping and
experience optimisation (IES). This chain is that loop, collapsed to the phases
that do distinct work when the subject is a codebase rather than a live
platform, and with SELF_CORRECTION given to a different agent on a different
model — an agent re-reading its own reasoning in its own session agrees with
itself, which is the one thing a correction pass must not do.

Nothing is built here. The chain reasons, checks itself, and asks whether the
conclusion should be acted on at all. What it leaves behind is one document in
`app_docs/`: what this run learned, and what it retires.

DAVS is the gate, and it is a real one. `alignment_gatekeeper` is the only agent
in this roster whose verdict stops the run — a non-compliant verdict skips
consolidation and finishes unaccepted. That ordering is deliberate and it is the
argument for the whole roster: a system that consolidated first and reviewed
afterwards would have already written the conclusion into memory by the time it
decided the conclusion was wrong.

The interaction pass is opt-in (`--journey`) rather than always-on. IES maps how
people move through a system; on a goal with no human journey in it there is
nothing to map, and an agent asked to map one anyway will produce something
rather than nothing.
"""

import argparse
import sys

from adw_modules import agents, gates, git_helper, session, utils
from adw_modules.data_types import (AgentCall, AlignmentOutput, CapabilityOutput,
                                    ConsolidationOutput, ContextOutput, CorrectionOutput,
                                    InteractionOutput, PhaseParams, ReasoningOutput)

REQUIRED_AGENTS = ["memory_architect", "capability_specialist", "reasoning_architect",
                   "self_corrector", "alignment_gatekeeper", "memory_consolidator"]

# Only validated when --journey is passed: a roster that never runs the
# interaction pass should not be forced to carry the agent for it.
JOURNEY_AGENT = "interaction_specialist"

CONSOLIDATION_NOTES = (
    "The constitutional review has passed. Consolidate what this run learned — "
    "including what the self-correction pass changed, which is the memory most "
    "likely to stop the next run repeating this one.")


def main(prompt: str, config: str = "adws/adw_sssf_config/sssf.config.ucaf.yaml",
         adw_id: str | None = None, journey: bool = False) -> int:
    cfg = agents.load_config(config)
    agents.validate(cfg, REQUIRED_AGENTS + ([JOURNEY_AGENT] if journey else []))
    run = session.ensure(cfg, adw_id)

    with run.phase(PhaseParams(name="goal", kind="engineer", owner=run.engineer,
                               description="Capture the goal and pin the baseline "
                                           "the run is measured from")) as ph:
        ph.log(input=prompt, baseline=git_helper.short_sha(git_helper.rev("HEAD")))

    with run.phase(PhaseParams(name="recall", kind="agent", owner="memory_architect",
                               description="Establish what is already known about this "
                                           "goal, and what nothing answers")) as ph:
        recall = ph.call(AgentCall(
            output_type=ContextOutput, prompt=prompt,
            gates=[gates.artifacts_exist, gates.files_non_empty]))

    with run.phase(PhaseParams(name="capabilities", kind="agent",
                               owner="capability_specialist",
                               description="Ground the plan in what this codebase can "
                                           "actually do, health checked")) as ph:
        capabilities = ph.call(AgentCall(
            output_type=CapabilityOutput, prompt=prompt, previous=recall,
            gates=[gates.artifacts_exist, gates.files_non_empty]))

    # IES only runs when the goal has a human journey in it. Handed the
    # capabilities either way, so the reasoning pass sees one continuous chain.
    context = capabilities
    if journey:
        with run.phase(PhaseParams(name="journey", kind="agent", owner=JOURNEY_AGENT,
                                   description="Map how people actually move through "
                                               "this, and where it costs them")) as ph:
            context = ph.call(AgentCall(
                output_type=InteractionOutput, prompt=prompt, previous=capabilities,
                gates=[gates.artifacts_exist, gates.files_non_empty]))

    with run.phase(PhaseParams(name="reasoning", kind="agent", owner="reasoning_architect",
                               retries=1,
                               description="Draw what follows from the goal and the "
                                           "evidence, by a named strategy")) as ph:
        reasoning = ph.call(AgentCall(
            output_type=ReasoningOutput, prompt=prompt, previous=context,
            # The two gates that make the reasoning auditable rather than merely
            # fluent: a strategy from UCAF's closed list of eight, and evidence
            # behind anything asserted above 0.7.
            gates=[gates.artifacts_exist, gates.strategy_is_known,
                   gates.inferences_are_evidenced]))

    with run.phase(PhaseParams(name="self_correction", kind="agent", owner="self_corrector",
                               description="Audit the reasoning for contradiction, drift "
                                           "and unearned confidence, and fix what is "
                                           "there")) as ph:
        correction = ph.call(AgentCall(
            output_type=CorrectionOutput, prompt=prompt, previous=reasoning,
            gates=[gates.artifacts_exist, gates.corrections_applied]))

    with run.phase(PhaseParams(name="alignment", kind="agent", owner="alignment_gatekeeper",
                               retries=1,
                               description="Rule on whether the conclusion should be "
                                           "acted on at all, across five dimensions "
                                           "and seven pillars")) as ph:
        alignment = ph.call(AgentCall(
            output_type=AlignmentOutput, prompt=prompt, previous=correction,
            gates=[gates.artifacts_exist, gates.all_dimensions_scored,
                   gates.alignment_verdict_consistent]))

    # Nothing is written to memory that the gate did not clear. A chain that
    # consolidated first would have already recorded the conclusion by the time
    # it decided the conclusion was wrong — and the next run's recall pass would
    # read it back as established fact, which is how one bad run becomes the
    # premise of every run after it.
    if not alignment.compliant:
        return run.finish(
            accepted=False,
            reason=f"the constitutional gate refused the conclusion at "
                   f"{alignment.weighted_score:.1f}/100: {alignment.summary}")

    with run.phase(PhaseParams(name="consolidation", kind="agent", owner="memory_consolidator",
                               description="Commit what this run learned, and retire what "
                                           "it supersedes")) as ph:
        alignment.notes_for_next_agent = CONSOLIDATION_NOTES
        consolidation = ph.call(AgentCall(
            output_type=ConsolidationOutput, prompt=prompt, previous=alignment,
            gates=[gates.artifacts_exist, gates.files_non_empty]))

    with run.phase(PhaseParams(name="commit_memory", kind="code", owner="git",
                               description="Put this run's memory under version control "
                                           "so the next recall pass can find it")) as ph:
        message = (consolidation.commit_message
                   or f"sssf({run.adw_id}): {consolidation.summary}")
        # An unchanged tree here means the consolidation reproduced what was
        # already on record — a re-run against the same session, usually. That
        # is memory working, not memory failing.
        ph.log(sha=git_helper.commit_all(message) if git_helper.is_dirty()
                   else "(nothing to land — this run learned nothing new)",
               stored=len(consolidation.stored), superseded=len(consolidation.superseded))

    return run.finish(accepted=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="inline text or a path to a goal file")
    parser.add_argument("--config", default="adws/adw_sssf_config/sssf.config.ucaf.yaml")
    parser.add_argument("--adw-id", default=None, help="join or pin an existing session")
    parser.add_argument("--journey", action="store_true",
                        help="run the IES interaction pass — only for goals with a "
                             "human journey in them")
    args = parser.parse_args()
    sys.exit(main(utils.resolve_prompt(args.prompt), args.config, args.adw_id, args.journey))
