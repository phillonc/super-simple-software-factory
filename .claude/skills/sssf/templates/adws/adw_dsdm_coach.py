#!/usr/bin/env -S uv run
# /// script
# dependencies = ["pydantic", "python-dotenv", "pyyaml", "rich"]
# ///
"""ADW DSDM Coach — audit a completed run against the eight principles. Read-only.

Usage:
    uv run adws/adw_dsdm_coach.py <adw_id_to_audit> \\
        --config adws/adw_sssf_config/sssf.config.dsdm.yaml [--adw-id a1b2c3d4]

Phases: engineer(request) -> dsdm_coach

The positional argument is the adw_id being AUDITED; `--adw-id` is this audit's
own session, as in every other ADW. They are different runs on purpose — an
audit that wrote into the session it was judging would be part of its own
evidence.

The coach reads the trace db, the decision records, and the session's handoff
products, then rules on all eight principles with evidence. A gate rejects a
partial audit, because silence on a principle reads exactly like a pass.

Finding breaches is the audit working, so the PHASE succeeds either way. The
RUN is accepted only when all eight principles are upheld — that split is what
lets `just coach <id>` be worth putting in CI: the exit code says whether the
process held, not whether the coach managed to produce a document.
"""

import argparse
import sys

from adw_modules import agents, gates, session
from adw_modules.data_types import AgentCall, CoachOutput, PhaseParams

REQUIRED_AGENTS = ["dsdm_coach"]

TASK = ("Audit run {target} against the eight DSDM principles. Its trace is in the "
        "sssf.db configured for this factory, its decision records are under "
        "adws/adw_decisions/{target}/, and its handoff products are under the "
        "sessions directory for {target}. Rule on all eight, with evidence, and "
        "name a corrective action for every principle you do not uphold.")


def main(target: str, config: str = "adws/adw_sssf_config/sssf.config.dsdm.yaml",
         adw_id: str | None = None) -> int:
    cfg = agents.load_config(config)
    agents.validate(cfg, REQUIRED_AGENTS)
    run = session.ensure(cfg, adw_id)
    prompt = TASK.format(target=target)

    with run.phase(PhaseParams(name="request", kind="engineer", owner=run.engineer,
                               description="Name the run being audited")) as ph:
        ph.log(input=prompt, auditing=target)

    with run.phase(PhaseParams(name="audit", kind="agent", owner="dsdm_coach", retries=1,
                               description="Rule on all eight principles from the trace and "
                                           "the artifacts, with evidence")) as ph:
        audit = ph.call(AgentCall(output_type=CoachOutput, prompt=prompt,
                                  gates=[gates.artifacts_exist, gates.files_non_empty,
                                         gates.all_principles_ruled]))

    upheld = [f.principle for f in audit.findings if f.upheld]
    breached = [f.principle for f in audit.findings if not f.upheld]
    return run.finish(
        accepted=not breached,
        reason=f"{len(upheld)}/8 principles upheld — breached: {', '.join(breached)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="the adw_id to audit")
    parser.add_argument("--config", default="adws/adw_sssf_config/sssf.config.dsdm.yaml")
    parser.add_argument("--adw-id", default=None, help="this audit's own session id")
    args = parser.parse_args()
    sys.exit(main(args.target, args.config, args.adw_id))
