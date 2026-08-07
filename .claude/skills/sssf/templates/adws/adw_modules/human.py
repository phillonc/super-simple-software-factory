"""Human control points: the decisions no agent is allowed to take.

DSDM keeps two roles human — the Business Sponsor, who owns the business case,
and the Business Visionary, who owns the vision. Neither is in the roster,
because neither is an agent. This module is how a chain hands them the
decisions that are theirs, and how it proves afterwards that they took them.

Three properties, in order of how easy they are to get wrong:

1. **No default verdict.** A checkpoint with nobody to answer it stops the run.
   There is no timeout that means yes, no `--yes` flag, no "assume go in CI".
   Silence is the one answer this module will not invent, because a framework
   that assumes consent when the human is absent has no human in it.

2. **The verdict is not an agent-writable field.** `HumanDecision` is
   constructed here and nowhere else. The facilitator produces a
   `DecisionPackOutput` — options, consequences, a recommendation — and
   `gates.decision_is_the_humans` fails it if it arrives pre-decided. An agent
   can advise the decision. It cannot make it, and it cannot forge one.

3. **The record is evidence, not a log line.** Every decision lands in the repo
   under `adws/adw_decisions/<adw_id>/`, which is in `protected_files`, so
   `permissions.py` rolls back and fails any agent that touches it. The ADW
   commits it immediately: once tracked, a later edit shows up in `git diff`,
   which is what makes tampering visible rather than merely forbidden. The
   sha256 goes into the trace as a second copy of the same fact.

Three ways a human can answer, all recorded with which one it was:

    prompt       an interactive terminal — the default
    file         `--decision-file`: the run blocks until a person writes the
                 verdict as JSON. This is how a remote or CI run waits for a
                 human instead of proceeding without one.
    preapproved  `--decide foundations_approval=go:"rationale"`, typed by a
                 human before the run started. Still a human, still recorded,
                 and marked as given in advance so nobody later mistakes it for
                 a considered response to what the agents actually produced.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

from .data_types import (DecisionOption, DecisionOutput, EventRecord, HumanDecision,
                         HumanDecisionRequest)
from .utils import ensure_dir, now_iso

# Where decision records live. In the REPO, not under data_dir: the session
# runtime is writable by every agent by design (see permissions.always_writable),
# and the one artifact that must not be is this one. Named in protected_files.
DECISIONS_DIR = "adws/adw_decisions"

VERDICTS = {
    "go": "go",
    "g": "go",
    "yes": "go",
    "changes": "go_with_changes",
    "c": "go_with_changes",
    "go_with_changes": "go_with_changes",
    "no-go": "no_go",
    "no_go": "no_go",
    "n": "no_go",
    "no": "no_go",
    "stop": "no_go",
}

FILE_POLL_SECONDS = 2


class NoHumanAvailable(RuntimeError):
    """A checkpoint was reached with no way to ask anyone.

    Deliberately fatal. The alternatives are to guess a verdict or to skip the
    checkpoint, and both of them are the failure this module exists to prevent.
    """


class Checkpoints:
    """How this run resolves its checkpoints. Built once from the CLI, in main().

    One object rather than four loose params, per the four-param rule, and it
    keeps every ADW's `--decide` / `--decision-file` handling identical.
    """

    def __init__(self, decide: list[str] | None = None, decision_file: str = "",
                 timeout_seconds: int = 3600, decided_by: str = ""):
        self.preapproved = _parse_decisions(decide or [])
        self.decision_file = decision_file
        self.timeout_seconds = timeout_seconds
        self.decided_by = decided_by

    @staticmethod
    def add_arguments(parser) -> None:
        """The checkpoint flags every DSDM ADW exposes, defined in one place."""
        parser.add_argument(
            "--decide", action="append", default=[], metavar="CHECKPOINT=VERDICT[:WHY]",
            help="answer a checkpoint in advance: foundations_approval=go:'budget agreed'. "
                 "Verdicts: go | changes | no-go. Recorded as given in advance.")
        parser.add_argument(
            "--decision-file", default="",
            help="block at each checkpoint until a human writes the verdict as JSON "
                 "to this path — how an unattended run waits for a person.")
        parser.add_argument(
            "--decision-timeout", type=int, default=3600,
            help="seconds to wait on --decision-file before giving up (default 3600). "
                 "Timing out fails the run; it never means yes.")
        parser.add_argument(
            "--decided-by", default="",
            help="who is answering (defaults to the engineer running the ADW)")

    @classmethod
    def from_args(cls, args) -> "Checkpoints":
        return cls(decide=args.decide, decision_file=args.decision_file,
                   timeout_seconds=args.decision_timeout, decided_by=args.decided_by)


def _parse_decisions(entries: list[str]) -> dict[str, tuple[str, str]]:
    """`name=verdict[:rationale]` -> {name: (verdict, rationale)}."""
    parsed: dict[str, tuple[str, str]] = {}
    for entry in entries:
        name, _, rest = entry.partition("=")
        verdict_word, _, rationale = rest.partition(":")
        verdict = VERDICTS.get(verdict_word.strip().lower())
        if not name.strip() or verdict is None:
            raise SystemExit(
                f"--decide {entry!r} is not understood. Use "
                f"CHECKPOINT=VERDICT[:WHY] where VERDICT is go, changes, or no-go.")
        parsed[name.strip()] = (verdict, rationale.strip().strip("'\""))
    return parsed


# ── the checkpoint ───────────────────────────────────────────────────────────

def decide(run, ph, request: HumanDecisionRequest,
           checkpoints: Checkpoints | None = None) -> HumanDecision:
    """Put one decision in front of a human and return what they said.

    Called inside an `engineer` phase, so the checkpoint is a visible block in
    the trace with the human as its owner — the chain shows where control
    changed hands, not just that it did.

    The phase SUCCEEDS on any verdict, including `no_go`. A human declining is
    the checkpoint working, not failing. What a `no_go` decides is the RUN's
    outcome, which the ADW settles with `run.finish(accepted=decision.proceed)`.
    """
    checkpoints = checkpoints or Checkpoints()
    _present(run, request)

    if request.checkpoint in checkpoints.preapproved:
        verdict, rationale = checkpoints.preapproved[request.checkpoint]
        decision = HumanDecision(
            checkpoint=request.checkpoint, verdict=verdict,
            decided_by=checkpoints.decided_by or run.engineer,
            rationale=rationale, chosen_option=request.recommendation,
            source="preapproved")
    elif checkpoints.decision_file:
        decision = _await_file(run, request, checkpoints)
    elif sys.stdin.isatty():
        decision = _ask(run, request, checkpoints)
    else:
        raise NoHumanAvailable(
            f"checkpoint {request.checkpoint!r} needs a human and this run has no "
            f"way to reach one: stdin is not a terminal, no --decision-file was "
            f"given, and no --decide {request.checkpoint}=... was passed. "
            f"Answer it one of those three ways and re-run — there is no verdict "
            f"this can assume on your behalf.")

    decision.decided_at = now_iso()
    _record(run, ph, request, decision)
    return decision


def require(decision: HumanDecision) -> HumanDecision:
    """Assert a checkpoint said go. For the rare step that cannot run otherwise.

    Most ADWs should branch on `decision.proceed` instead — a declined
    checkpoint usually means "stop here cleanly and report why", not "crash".
    """
    if not decision.proceed:
        raise RuntimeError(
            f"checkpoint {decision.checkpoint!r}: {decision.decided_by} said no-go"
            + (f" — {decision.rationale}" if decision.rationale else ""))
    return decision


def as_envelope(decision: HumanDecision, notes: str = "") -> DecisionOutput:
    """Wrap a decision so the next agent can be handed it like any other input."""
    return DecisionOutput(
        status="success",
        summary=(f"{decision.decided_by} decided {decision.verdict} at checkpoint "
                 f"{decision.checkpoint}"
                 + (f" ({decision.chosen_option})" if decision.chosen_option else "")),
        artifacts=[decision.record_path] if decision.record_path else [],
        notes_for_next_agent=notes or decision.rationale,
        checkpoint=decision.checkpoint,
        verdict=decision.verdict,
        chosen_option=decision.chosen_option,
        decided_by=decision.decided_by,
        rationale=decision.rationale,
        record_path=decision.record_path,
    )


# ── presenting, asking, waiting ──────────────────────────────────────────────

def _present(run, request: HumanDecisionRequest) -> None:
    """Print the decision the way a person needs to read it, before being asked."""
    run.console.note(f"CHECKPOINT {request.checkpoint} — the decision below is yours")
    run.console.note(f"question: {request.question}")
    if request.pack_path:
        run.console.note(f"read first: {request.pack_path}")
    for option in request.options:
        risk = f" · {option.reversibility}" if option.reversibility else ""
        musts = f" · musts: {option.impact_on_musts}" if option.impact_on_musts else ""
        run.console.note(f"  {option.id}: {option.option} -> {option.consequence}{risk}{musts}")
    if request.recommendation:
        run.console.note(f"the team recommends: {request.recommendation} (advice, not a verdict)")
    if request.if_no_decision:
        run.console.note(f"if you decide nothing: {request.if_no_decision}")


def _ask(run, request: HumanDecisionRequest, checkpoints: Checkpoints) -> HumanDecision:
    """Interactive terminal. Loops until the answer is one this can record."""
    ids = [o.id for o in request.options]
    while True:
        try:
            raw = input(f"\n[{request.checkpoint}] go | changes | no-go > ").strip().lower()
        except EOFError as error:
            raise NoHumanAvailable(
                f"checkpoint {request.checkpoint!r}: stdin closed before an answer "
                f"was given. Nothing was assumed; re-run and answer it.") from error
        verdict = VERDICTS.get(raw)
        if verdict:
            break
        print(f"  not understood: {raw!r}. Answer go, changes, or no-go.")

    chosen = ""
    if ids and verdict != "no_go":
        default = request.recommendation if request.recommendation in ids else ids[0]
        chosen = input(f"  option {'|'.join(ids)} [{default}] > ").strip() or default

    # A rationale is what makes the record worth keeping. Required exactly where
    # it matters — anything other than plain agreement changes the plan, and the
    # next person to read this needs to know why.
    prompt = "  why (required) > " if verdict != "go" else "  why (optional) > "
    rationale = input(prompt).strip()
    while verdict != "go" and not rationale:
        rationale = input("  a rationale is required for this verdict > ").strip()

    return HumanDecision(checkpoint=request.checkpoint, verdict=verdict,
                         decided_by=checkpoints.decided_by or run.engineer,
                         rationale=rationale, chosen_option=chosen, source="prompt")


def _await_file(run, request: HumanDecisionRequest,
                checkpoints: Checkpoints) -> HumanDecision:
    """Block until a person writes the verdict to disk. Timing out is a failure.

    The run writes the question out as `<file>.request.json` first, so whoever
    answers is looking at the same options the console showed, then polls for
    the answer. A timeout raises: waiting longer than we were told to is not
    permission to continue.
    """
    answer_path = Path(checkpoints.decision_file)
    question_path = answer_path.with_suffix(answer_path.suffix + ".request.json")
    ensure_dir(answer_path.parent)
    question_path.write_text(json.dumps(
        {**request.model_dump(), "answer_with": {
            "checkpoint": request.checkpoint, "verdict": "go | go_with_changes | no_go",
            "decided_by": "<your name>", "rationale": "<why>",
            "chosen_option": "<option id>"}}, indent=2))
    run.console.note(f"waiting for a human: write your verdict to {answer_path} "
                     f"(the question is in {question_path})")

    deadline = time.monotonic() + checkpoints.timeout_seconds
    while time.monotonic() < deadline:
        if answer_path.exists():
            try:
                payload = json.loads(answer_path.read_text())
            except json.JSONDecodeError as error:
                run.console.note(f"decision file is not valid JSON yet ({error}) — still waiting")
                time.sleep(FILE_POLL_SECONDS)
                continue
            verdict = VERDICTS.get(str(payload.get("verdict", "")).strip().lower())
            if verdict is None:
                raise RuntimeError(
                    f"{answer_path}: verdict {payload.get('verdict')!r} is not one of "
                    f"go, go_with_changes, no_go. Fix the file and re-run — a "
                    f"malformed verdict is not a yes.")
            named = str(payload.get("decided_by", "")).strip()
            if not named:
                raise RuntimeError(
                    f"{answer_path}: decided_by is required. A decision record with "
                    f"nobody's name on it is not evidence that a human made it.")
            return HumanDecision(
                checkpoint=request.checkpoint, verdict=verdict, decided_by=named,
                rationale=str(payload.get("rationale", "")).strip(),
                chosen_option=str(payload.get("chosen_option", "")).strip(),
                source="file")
        time.sleep(FILE_POLL_SECONDS)

    raise NoHumanAvailable(
        f"checkpoint {request.checkpoint!r}: nobody answered within "
        f"{checkpoints.timeout_seconds}s. The run stops here — a timeout is not "
        f"consent. Re-run once someone is available, or pass --decide "
        f"{request.checkpoint}=<verdict>.")


# ── the record ───────────────────────────────────────────────────────────────

def _record(run, ph, request: HumanDecisionRequest, decision: HumanDecision) -> None:
    """Write the decision to the repo, digest it, and put both in the trace."""
    directory = ensure_dir(Path(run.repo_root) / DECISIONS_DIR / run.adw_id)
    seq = len([p for p in directory.glob("*.json")]) + 1
    stem = f"{seq:02d}_{request.checkpoint}"

    # `digest` and `record_path` describe the FILE, not the decision, so they are
    # left out of what the file contains. That is what makes the digest usable:
    # it is the sha256 of these exact bytes, so `verify(path) == trace digest` is
    # a check anyone can run later, rather than a hash of something that no
    # longer exists anywhere. See verify() below.
    payload = {"adw_id": run.adw_id, "request": request.model_dump(),
               "decision": decision.model_dump(
                   exclude={"digest", "record_path", "readable_path"})}
    body = json.dumps(payload, indent=2, sort_keys=True)
    decision.digest = hashlib.sha256(body.encode()).hexdigest()

    json_path = directory / f"{stem}.json"
    json_path.write_text(body)
    readable_path = directory / f"{stem}.md"
    readable_path.write_text(_readable(run, request, decision))
    # Relative: these are repo artifacts, and the trace should read the same on
    # every machine that clones this repository.
    root = Path(run.repo_root)
    decision.record_path = str(json_path.relative_to(root))
    decision.readable_path = str(readable_path.relative_to(root))

    run.tracer.event(EventRecord(
        adw_id=run.adw_id, phase_id=ph.phase.phase_id, type="log",
        name="human_decision",
        payload={"checkpoint": decision.checkpoint, "verdict": decision.verdict,
                 "decided_by": decision.decided_by, "source": decision.source,
                 "chosen_option": decision.chosen_option,
                 "rationale": decision.rationale,
                 "record": decision.record_path, "sha256": decision.digest}))
    ph.log(checkpoint=decision.checkpoint, verdict=decision.verdict,
           decided_by=decision.decided_by, source=decision.source,
           record=decision.record_path)


def record_message(decision: HumanDecision) -> str:
    """The commit subject for a decision record. Every verdict gets one.

    A decision record is committed whatever the answer was — a `no_go` is the
    verdict most worth keeping and the one a chain is most tempted to drop,
    since nothing after it runs. It is also the only one that would otherwise
    stay untracked, and `permissions.snapshot()` fingerprints an untracked file
    by name alone: its CONTENT could be rewritten by a later agent without the
    change ever being noticed. Committing it closes that hole for real.
    """
    subject = (f"Record {decision.verdict} at {decision.checkpoint} "
               f"by {decision.decided_by}")
    body = f"\n\nSource: {decision.source}. sha256: {decision.digest}"
    if decision.chosen_option:
        body += f"\nOption: {decision.chosen_option}"
    if decision.rationale:
        body += f"\nRationale: {decision.rationale}"
    return subject + body


def verify(record_path: str) -> str:
    """The sha256 of a decision record as it stands on disk now.

    Compare it with the digest the trace recorded when the decision was taken:

        select json_extract(payload_json,'$.sha256') from events
         where type='log' and name='human_decision' and adw_id='<id>';

    They match unless the file has been edited since. Three independent copies
    of the same fact have to be changed in step to hide a tampered decision —
    this file, the git history that committed it, and the trace row — which is
    the point of keeping the record in all three.
    """
    return hashlib.sha256(Path(record_path).read_bytes()).hexdigest()


def _readable(run, request: HumanDecisionRequest, decision: HumanDecision) -> str:
    """The same record as prose. The JSON is for tools; this is for people."""
    lines = [f"# Decision — {request.checkpoint}", "",
             f"- **adw_id**: {run.adw_id}",
             f"- **verdict**: {decision.verdict}",
             f"- **decided by**: {decision.decided_by} ({decision.source})",
             f"- **at**: {decision.decided_at}"]
    if decision.chosen_option:
        lines.append(f"- **option**: {decision.chosen_option}")
    lines += ["", "## Question", "", request.question, ""]
    if request.options:
        lines += ["## Options", ""]
        lines += [f"- **{o.id}** ({o.reversibility}) — {o.option}: {o.consequence}"
                  + (f" _Musts: {o.impact_on_musts}_" if o.impact_on_musts else "")
                  for o in request.options]
        lines.append("")
    if request.recommendation:
        lines += [f"Recommended by the team: **{request.recommendation}** "
                  f"(advice — the verdict above is the human's).", ""]
    if request.if_no_decision:
        lines += ["## If no decision were taken", "", request.if_no_decision, ""]
    lines += ["## Rationale", "", decision.rationale or "_(none given)_", ""]
    if request.pack_path:
        lines += [f"Full pack: `{request.pack_path}`", ""]
    return "\n".join(lines)


def option(id: str, text: str, consequence: str, reversibility: str = "reversible",
           impact_on_musts: str = "") -> DecisionOption:
    """Build an option for a checkpoint the ADW raises itself, without a pack."""
    return DecisionOption(id=id, option=text, consequence=consequence,
                          reversibility=reversibility, impact_on_musts=impact_on_musts)


def pack_to_request(pack, checkpoint: str, pack_path: str = "") -> HumanDecisionRequest:
    """Turn the facilitator's decision pack into the request a checkpoint asks.

    The pack has already been through `gates.decision_is_the_humans`, so by the
    time it reaches here it is known to hold a question, two or more options,
    and the cost of deciding nothing.
    """
    return HumanDecisionRequest(
        checkpoint=checkpoint or pack.checkpoint,
        question=pack.question,
        options=list(pack.options),
        recommendation=pack.recommendation,
        if_no_decision=pack.if_no_decision,
        pack_path=pack_path or (pack.artifacts[0] if pack.artifacts else ""),
    )
