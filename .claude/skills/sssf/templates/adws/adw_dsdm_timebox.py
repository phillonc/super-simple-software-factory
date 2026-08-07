#!/usr/bin/env -S uv run
# /// script
# dependencies = ["pydantic", "python-dotenv", "pyyaml", "rich"]
# ///
"""ADW DSDM Timebox — one evolutionary-development timebox, ending at a human review.

Usage:
    uv run adws/adw_dsdm_timebox.py "<prompt or path/to/prompt.md>" \\
        --config adws/adw_sssf_config/sssf.config.dsdm.yaml \\
        --adw-id <the foundations session> [--minutes 30] [--loops 3] \\
        [--decide timebox_review=go:"why"] [--decision-file path.json]

Phases: engineer(kickoff) -> business_ambassador [-> engineer(scope_question)]
        -> solution_developer -> code(test) -> solution_tester
           [-> solution_developer -> code(test) -> solution_tester ... bounded]
        -> code(consolidate) -> workshop_facilitator
        -> engineer(timebox_review) -> git(record_decision)
        -> git(commit_increment)

Every checkpoint is followed by a git phase that commits the answer, whichever
way it went. The increment itself is committed only on acceptance.

Run it against the --adw-id of a completed foundations run, as many times as
the work needs. Launching the next timebox is a human act, deliberately: an
ADW that looped by itself would have taken the one decision — "is this worth
another box?" — that the whole ceremony exists to put in front of a person.

THE DATE DOES NOT MOVE. `--minutes` is wall clock from kick-off, held in
adw_modules/timebox.py, and read BETWEEN iterations so an expired box means
"no more refinement loops", not an agent killed mid-edit. When the clock beats
the work, scope gives: Coulds first, then Shoulds. A Must that will not fit is
never dropped by code — it lands in `musts_at_risk`, and the checkpoint makes
it the first thing the human sees.

Three different questions get asked, in order, and none can answer another. The
suite asks "does it run" — a known command, so code runs it (hard rule 8). The
tester asks "does it meet what the business agreed to", against the acceptance
criteria. The human asks "given all that, and the clock, do we ship this". The
first two are inputs to the third; only the third decides.

The increment is committed after the human accepts it, not after it goes green.
A declined timebox leaves the code in the working tree where the engineer can
see it — the run produced something, and the honest record is that nobody
accepted it yet.
"""

import argparse
import sys

from adw_modules import (agents, gates, git_helper, human, quality, session, timebox,
                         utils)
from adw_modules.data_types import (AcceptanceOutput, AgentCall, AmbassadorOutput,
                                    DecisionPackOutput, IncrementOutput, PhaseParams,
                                    TimeboxSpec)

REQUIRED_AGENTS = ["business_ambassador", "solution_developer", "solution_tester",
                   "workshop_facilitator"]

CHECKPOINT = "timebox_review"
SCOPE_CHECKPOINT = "scope_question"

PACK_NOTES = (f"Prepare the pack for checkpoint '{CHECKPOINT}'. The human is deciding "
              "whether to accept this increment. Read the acceptance report, the "
              "timebox status, and the descope plan. If any Must is at risk, that is "
              "the question — the date is fixed, so their real options are to descope, "
              "to carry the Must into another timebox, or to stop.")


def main(prompt: str, config: str = "adws/adw_sssf_config/sssf.config.dsdm.yaml",
         adw_id: str | None = None, spec: TimeboxSpec | None = None,
         checkpoints: human.Checkpoints | None = None) -> int:
    cfg = agents.load_config(config)
    agents.validate(cfg, REQUIRED_AGENTS)
    run = session.ensure(cfg, adw_id)
    spec = spec or TimeboxSpec(name="timebox")
    checkpoints = checkpoints or human.Checkpoints()
    box = timebox.Timebox(spec)

    def record(decision) -> None:
        """Commit the human's answer, whichever way it went.

        Every checkpoint gets one of these, including the ones that stop the
        run — a `no_go` is the verdict most worth keeping and the one a chain is
        most tempted to drop, since nothing after it runs. Untracked, its
        content could also be rewritten without `permissions.snapshot()` seeing
        it, because that fingerprints an untracked file by name alone.
        """
        with run.phase(PhaseParams(name=f"record_{decision.checkpoint}", kind="code",
                                   owner="git",
                                   description="Put the human's answer under version "
                                               "control, whichever way it went")) as ph:
            ph.log(sha=git_helper.commit_paths(human.record_message(decision),
                                               decision.records) or "(already recorded)",
                   verdict=decision.verdict, record=decision.record_path)

    with run.phase(PhaseParams(name="kickoff", kind="engineer", owner=run.engineer,
                               description="Start the clock and state what this box is "
                                           "trying to achieve")) as ph:
        box.log(ph, input=prompt, objective=spec.objective or prompt[:120],
                baseline=git_helper.short_sha(git_helper.rev("HEAD")))

    with run.phase(PhaseParams(name="investigate", kind="agent", owner="business_ambassador",
                               description="Take the requirements this box can hold and "
                                           "sharpen them until nobody needs to ask again")) as ph:
        agreed = ph.call(AgentCall(
            output_type=AmbassadorOutput, prompt=prompt,
            previous=timebox.as_envelope(box.status(), notes=(
                "Select only what fits in the remaining time, Musts first.")),
            gates=[gates.artifacts_exist, gates.requirements_traceable]))

    # The ambassador refuses to settle anything that changes what was agreed.
    # That refusal is worth nothing unless it actually reaches someone, so it
    # becomes a checkpoint before a line is written — the cheapest moment to
    # answer it, and the only one where the answer still changes the build.
    if agreed.escalations:
        with run.phase(PhaseParams(name=SCOPE_CHECKPOINT, kind="engineer", owner=run.engineer,
                                   description="Settle what the ambassador would not decide "
                                               "on the business's behalf")) as ph:
            first = agreed.escalations[0]
            answer = human.decide(run, ph, human.HumanDecisionRequest(
                checkpoint=SCOPE_CHECKPOINT,
                question=(f"{first.question}\n\nWhy this needs you: {first.why_human}"
                          + (f"\nBlocks: {', '.join(first.blocks)}" if first.blocks else "")
                          + (f"\n\n({len(agreed.escalations) - 1} further escalation(s) are "
                             f"in the report — see notes)"
                             if len(agreed.escalations) > 1 else "")),
                options=[human.option(f"OPT-{chr(65 + i)}", text,
                                      "chosen by you; the developer builds to it")
                         for i, text in enumerate(first.options)]
                        or [human.option("OPT-A", "proceed as the ambassador described",
                                         "the developer builds the requirements as written"),
                            human.option("OPT-B", "stop and re-plan",
                                         "this timebox ends now; nothing is built",
                                         reversibility="reversible")],
                if_no_decision=("the timebox cannot proceed — the developer would have to "
                                "guess at the answer, which is what the escalation exists "
                                "to prevent"),
                pack_path=agreed.artifacts[0] if agreed.artifacts else ""),
                checkpoints)
        record(answer)
        if not answer.proceed:
            return run.finish(accepted=False,
                              reason=f"{answer.decided_by} stopped the timebox at "
                                     f"{SCOPE_CHECKPOINT}: {answer.rationale}")
        agreed.notes_for_next_agent = (
            f"Human decision at {SCOPE_CHECKPOINT}: {answer.verdict} "
            f"{answer.chosen_option} — {answer.rationale}. Build to this.\n"
            + agreed.notes_for_next_agent)

    increment = None
    acceptance = None
    test = None
    previous = agreed
    for i in range(1, spec.max_refine_loops + 1):
        with run.phase(PhaseParams(name=f"build_{i}", kind="agent", owner="solution_developer",
                                   retries=1,
                                   description="Build in MoSCoW order against the clock, "
                                               "Musts before anything else")) as ph:
            box.log(ph, loop=i)
            increment = ph.call(AgentCall(
                output_type=IncrementOutput, prompt=prompt, previous=previous,
                gates=[gates.diff_matches_claims, gates.musts_not_descoped]))

        with run.phase(PhaseParams(name=f"test_{i}", kind="code", owner="quality",
                                   description="Run the suite — a known command, so code "
                                               "runs it and no agent rediscovers it")) as ph:
            test = quality.run_tests(run)
            passed = sum(1 for check in test.checks if check.passed)
            ph.log(passed=test.passed, checks=f"{passed}/{len(test.checks)}",
                   artifacts=", ".join(test.artifacts))

        # A red suite is not an acceptance question. Send it straight back to
        # the developer rather than spending a tester on code that does not run.
        if not test.passed:
            previous = quality.as_envelope(test, "tests")
            if box.expired or i == spec.max_refine_loops:
                break
            continue

        with run.phase(PhaseParams(name=f"accept_{i}", kind="agent", owner="solution_tester",
                                   description="Rule on the increment against the criteria "
                                               "the business agreed to")) as ph:
            acceptance = ph.call(AgentCall(
                output_type=AcceptanceOutput, prompt=prompt, previous=increment,
                gates=[gates.artifacts_exist, gates.acceptance_consistent]))

        if acceptance.accepted:
            break
        if box.expired:
            run.console.note("timebox expired — no further refinement, scope gives instead")
            break
        previous = acceptance

    with run.phase(PhaseParams(name="consolidate", kind="code", owner="quality",
                               description="Measure what the box delivered against what it "
                                           "took on, and work out what comes out")) as ph:
        status = box.status()
        delivered = list(increment.requirements_addressed) if increment else []
        plan = timebox.descope_plan(agreed.requirements, delivered, status)
        box.log(ph, delivered=len(delivered), outstanding=len(plan.outstanding),
                drop=", ".join(plan.drop) or "nothing",
                musts_at_risk=", ".join(plan.musts_at_risk) or "none",
                tests="passed" if test and test.passed else "not passing",
                accepted=bool(acceptance and acceptance.accepted))

    with run.phase(PhaseParams(name="review_pack", kind="agent", owner="workshop_facilitator",
                               retries=1,
                               description="Frame the accept-or-descope question the timebox "
                                           "has arrived at")) as ph:
        pack = ph.call(AgentCall(
            output_type=DecisionPackOutput, prompt=prompt,
            previous=timebox.as_envelope(status, plan, notes=PACK_NOTES),
            gates=[gates.artifacts_exist, gates.decision_is_the_humans]))

    with run.phase(PhaseParams(name=CHECKPOINT, kind="engineer", owner=run.engineer,
                               description="Hand control back: accept this increment, accept "
                                           "it with changes, or reject it")) as ph:
        request = human.pack_to_request(pack, CHECKPOINT)
        # Three facts the human must not have to go looking for. Each is a thing
        # the agents are least reliable about and the human is most accountable
        # for, so each is spliced into the question itself.
        flags = []
        if plan.musts_at_risk:
            flags.append(f"MUSTS AT RISK: {', '.join(plan.musts_at_risk)} — the date is "
                         f"fixed, so dropping or carrying a Must is your call, not the team's")
        if test and not test.passed:
            flags.append("the test suite is RED — this increment does not run clean")
        if acceptance and not acceptance.accepted:
            flags.append(f"the tester did NOT accept: {acceptance.summary}")
        if flags:
            request.question = request.question + "\n\n" + "\n".join(f"- {f}" for f in flags)
        decision = human.decide(run, ph, request, checkpoints)

    record(decision)

    if decision.proceed:
        with run.phase(PhaseParams(name="commit_increment", kind="code", owner="git",
                                   description="Land the increment the human accepted, naming "
                                               "the decision that accepted it")) as ph:
            message = (increment.commit_message if increment
                       else f"sssf({run.adw_id}): timebox {spec.name}")
            message += (f"\n\nAccepted at checkpoint {decision.checkpoint} by "
                        f"{decision.decided_by} ({decision.verdict})")
            if decision.rationale:
                message += f": {decision.rationale}"
            # A timebox can legitimately end with nothing to land — everything
            # deferred, or the work already committed by an earlier box. The
            # decision has been recorded and the human said go, so crashing here
            # would turn an honest empty result into a failed run. Say it plainly
            # in the trace instead — the acceptance report is where "what was
            # actually delivered" already lives.
            ph.log(sha=git_helper.commit_all(message) if git_helper.is_dirty()
                       else "(nothing to land — the increment changed no files)",
                   decision=decision.record_path)

    return run.finish(
        accepted=decision.proceed,
        reason=f"{decision.decided_by} did not accept the increment at {CHECKPOINT}"
               + (f": {decision.rationale}" if decision.rationale else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="inline text or a path to a prompt file")
    parser.add_argument("--config", default="adws/adw_sssf_config/sssf.config.dsdm.yaml")
    parser.add_argument("--adw-id", default=None,
                        help="the foundations session this timebox belongs to")
    parser.add_argument("--minutes", type=int, default=30,
                        help="the timebox length in wall-clock minutes (default 30). "
                             "This is a deadline, not a budget — it does not extend.")
    parser.add_argument("--loops", type=int, default=3,
                        help="maximum refinement iterations inside the box (default 3)")
    parser.add_argument("--name", default="timebox", help="a name for this timebox")
    parser.add_argument("--objective", default="", help="what this box is trying to achieve")
    human.Checkpoints.add_arguments(parser)
    args = parser.parse_args()
    sys.exit(main(utils.resolve_prompt(args.prompt), args.config, args.adw_id,
                  TimeboxSpec(name=args.name, minutes=args.minutes,
                              max_refine_loops=args.loops, objective=args.objective),
                  human.Checkpoints.from_args(args)))
