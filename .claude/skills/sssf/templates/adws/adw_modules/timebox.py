"""Timeboxing: a fixed end, a variable scope, and arithmetic instead of hope.

DSDM's second principle is *deliver on time*, and its mechanism is the timebox:
the end date is fixed, so when the work will not fit, what gives is priority.
That only works if two things are true, and both of them are code's job here
rather than an agent's:

  * **The clock is real.** `Timebox` measures wall time from kick-off. An agent
    asked to "keep an eye on the time" has no clock; a subprocess does. The
    remaining time rides into each agent as an envelope, so the team knows the
    deadline the way a DSDM team does.

  * **Descoping is ordered, and stops at Musts.** `descope_plan` drops Coulds
    first, then Shoulds — never a Must. A Must that will not fit lands in
    `musts_at_risk`, which the ADW turns into a checkpoint. That is the line
    this module refuses to cross on its own: dropping something the increment
    is not viable without is the sponsor's decision, and code taking it
    silently is exactly how a "timeboxed" project quietly ships nothing.

The clock never stops a phase mid-flight. It is read BETWEEN iterations, so an
expired timebox means "no more refinement loops", not "kill the developer
halfway through an edit" — which would leave a half-written tree and cost more
time than it saved.
"""

from __future__ import annotations

import time

from .data_types import (DescopePlan, MoSCoW, Requirement, TimeboxOutput, TimeboxSpec,
                         TimeboxStatus)
from .utils import now_iso

# The order scope comes off in. Musts are absent on purpose — that omission is
# the rule, not an oversight.
DESCOPE_ORDER: list[MoSCoW] = ["could", "should"]


class Timebox:
    """A running timebox. Started once, read as often as you like."""

    def __init__(self, spec: TimeboxSpec):
        self.spec = spec
        self.started_at = now_iso()
        self._clock = time.monotonic()

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._clock

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.spec.minutes * 60 - self.elapsed_seconds)

    @property
    def expired(self) -> bool:
        return self.remaining_seconds <= 0

    def status(self) -> TimeboxStatus:
        return TimeboxStatus(
            name=self.spec.name, minutes=self.spec.minutes, started_at=self.started_at,
            elapsed_seconds=round(self.elapsed_seconds, 1),
            remaining_seconds=round(self.remaining_seconds, 1), expired=self.expired)

    def log(self, ph, **extra) -> TimeboxStatus:
        """Put the clock in the trace. Every loop calls this, so the record shows
        the deadline being watched rather than the ADW claiming it was."""
        status = self.status()
        ph.log(timebox=status.name,
               remaining=f"{status.remaining_seconds / 60:.1f}m of {status.minutes}m",
               spent=f"{status.spent_share:.0%}", **extra)
        return status


def descope_plan(requirements: list[Requirement], done: list[str],
                 status: TimeboxStatus) -> DescopePlan:
    """What comes out of the box, in DSDM's order, when the clock beats the work.

    `done` is what the increment actually delivered. Anything else is
    outstanding: Coulds and Shoulds are proposed for descoping, Musts are
    escalated. Nothing here decides — the plan is an input to a checkpoint.
    """
    delivered = set(done)
    outstanding = [r for r in requirements
                   if r.id not in delivered and r.moscow != "wont"]
    drop = [r.id for level in DESCOPE_ORDER for r in outstanding if r.moscow == level]
    musts_at_risk = [r.id for r in outstanding if r.moscow == "must"]

    if not outstanding:
        reason = "every prioritised requirement was delivered inside the timebox"
    elif musts_at_risk:
        reason = (f"the timebox is {status.spent_share:.0%} spent with "
                  f"{len(musts_at_risk)} Must(s) outstanding — the date is fixed, so "
                  f"this is a decision about scope, and it is not code's to take")
    else:
        reason = (f"{len(drop)} lower-priority requirement(s) did not fit; the date "
                  f"holds and they move to the next timebox")
    return DescopePlan(outstanding=[r.id for r in outstanding], drop=drop,
                       musts_at_risk=musts_at_risk, reason=reason)


def as_envelope(status: TimeboxStatus, plan: DescopePlan | None = None,
                notes: str = "") -> TimeboxOutput:
    """The clock (and any descope plan) as an envelope an agent can be handed.

    Same adapter shape as quality.as_envelope and changes.as_envelope: code
    computes it, the agent receives it through the one door every handoff uses.
    """
    plan = plan or DescopePlan()
    remaining = f"{status.remaining_seconds / 60:.1f} minute(s) left"
    return TimeboxOutput(
        status="success",
        summary=(f"timebox {status.name}: "
                 + ("expired" if status.expired else remaining)
                 + (f"; {len(plan.outstanding)} requirement(s) outstanding"
                    if plan.outstanding else "")),
        notes_for_next_agent=notes or plan.reason,
        timebox=status.name,
        minutes=status.minutes,
        remaining_seconds=status.remaining_seconds,
        expired=status.expired,
        outstanding=plan.outstanding,
        drop=plan.drop,
        musts_at_risk=plan.musts_at_risk,
    )
