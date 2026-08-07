"""Claude Code interface — the second coding agent the factory can run.

Runs `claude -p --output-format stream-json --verbose` and tails its JSONL
stdout line by line, forwarding each event to a callback WHILE the agent works.
Same contract as `agent_pi.run`: one non-interactive turn in, one `PiResult`
out, tool calls forwarded through a `ToolCallTracker`.

Three things differ from Pi, and each is handled here so no ADW, gate, prompt or
config has to know which coding agent it is running on:

**Sessions.** Pi's `--session-id` is create-or-continue. Claude Code splits it:
`--session-id <uuid>` creates, `--resume <uuid>` continues, and passing
`--session-id` twice fails. So the first send in a session creates and every
send after resumes — tracked by a marker file in `session_dir`, which is where
that state already belongs. The id must also be a real UUID, and the factory's
ids are not (`sssf-a1b2-planner-9f3c`), so it derives one with uuid5: the same
factory id always maps to the same UUID, which is what makes a rejoined session
land in the context window it left.

**Tool names.** The roster speaks the factory's vocabulary (`read`, `bash`,
`grep`) and each interface translates. Unknown names pass through untouched, so
an MCP tool can be named in `tools:` exactly as an extension tool is for Pi.

**Permissions.** A non-interactive run cannot answer a permission prompt, so
every tool the roster granted is also pre-approved via `--allowedTools`. This is
NOT a widening: the allowlist is exactly `request.tools`, so an agent configured
read-only is granted read-only. `--dangerously-skip-permissions` is never used —
it is refused under root anyway, and the roster is the allowlist.

`writes:` enforcement is unaffected and unchanged. It runs in
`permissions.py` against the repo after the call, which is the only place a
claim about what an agent changed can actually be checked.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

from .data_types import PiRequest, PiResult
from .utils import now_iso, operator_env

CLAUDE_PATH = os.environ.get("CLAUDE_PATH", "claude")

# Stable namespace for deriving a UUID from a factory session id. Fixed forever:
# changing it would orphan every session on disk, because the same factory id
# would start resolving to a different UUID.
SESSION_NAMESPACE = uuid.UUID("6f9b1e2a-0c74-4b6d-9a1f-3c5d8e7b2a41")

RESULT_SNIPPET_CHARS = 20_000
ARG_VALUE_CHARS = 20_000
LABEL_CHARS = 80

PRIMARY_ARGS = ("command", "path", "file_path", "pattern", "query", "url")

# The factory's tool vocabulary -> Claude Code's built-in tool names. `find` and
# `ls` both land on Glob: Claude has no LS tool, and shelling out to `ls`
# through Bash is what the model does anyway.
TOOL_NAMES = {
    "read": "Read",
    "bash": "Bash",
    "edit": "Edit",
    "write": "Write",
    "grep": "Grep",
    "find": "Glob",
    "ls": "Glob",
}

# `thinking` in the roster -> `--effort`. Pi's ladder has two rungs Claude Code
# does not, and both mean "as little as possible".
EFFORT = {"off": "low", "minimal": "low", "low": "low", "medium": "medium",
          "high": "high", "xhigh": "xhigh", "max": "max"}

# Claude Code resolves aliases and full ids itself, so the factory does not keep
# a catalog for it the way it does for Pi. These are the aliases that are always
# valid; anything else is passed through and validated by the CLI at spawn.
KNOWN_ALIASES = {"fable", "opus", "sonnet", "haiku", "default", "sonnet[1m]"}


def resolve_model(pattern: str) -> tuple[str, str]:
    """Resolve a model pattern to ``(provider, model_id)``.

    Claude Code owns model resolution — it accepts aliases (`sonnet`, `haiku`)
    and full ids (`claude-opus-5`), and it errors clearly on an unknown one. So
    this validates only what it can validate cheaply and honestly: the shape.

    A `provider/id` pattern is accepted with the provider stripped, so one
    roster can name `anthropic/claude-opus-5` and run on either interface.
    """
    model = pattern.split("/", 1)[1] if "/" in pattern else pattern
    if not model.strip():
        raise ValueError(f"model pattern {pattern!r} is empty")
    if model not in KNOWN_ALIASES and not model.startswith("claude-"):
        raise ValueError(
            f"model {model!r} is not a Claude Code model — use an alias "
            f"({', '.join(sorted(KNOWN_ALIASES))}) or a full id like "
            f"'claude-opus-5'. Pattern came from the roster as {pattern!r}.")
    return "anthropic", model


def map_tools(tools: Optional[list[str]]) -> Optional[list[str]]:
    """Factory tool names -> Claude Code tool names, order-preserving, deduped.

    `None` means "all tools" and stays `None`. An unrecognised name passes
    through unchanged so MCP and plugin tools can be granted by their real name.
    """
    if tools is None:
        return None
    mapped: list[str] = []
    for tool in tools:
        name = TOOL_NAMES.get(tool, tool)
        if name not in mapped:
            mapped.append(name)
    return mapped


def session_uuid(session_id: str) -> str:
    """The UUID Claude Code will see for a factory session id.

    Deterministic, so rejoining a session by its factory id lands in the same
    context window. A caller that already has a UUID keeps it verbatim.
    """
    try:
        return str(uuid.UUID(session_id))
    except ValueError:
        return str(uuid.uuid5(SESSION_NAMESPACE, session_id))


def _feed(process, prompt: str) -> None:
    """Write the prompt to the child's stdin and close it.

    Errors are swallowed on purpose: if the child died before reading, the
    write fails with EPIPE, and the real diagnosis is the exit code and stderr
    that `run` is about to report. Raising here would replace that with a
    traceback from a daemon thread nobody is watching.
    """
    try:
        process.stdin.write(prompt)
        process.stdin.close()
    except (BrokenPipeError, ValueError, OSError):
        pass


def _marker(request: PiRequest, resolved: str) -> Path:
    return Path(request.session_dir) / f"{resolved}.started"


def _text_of(message: dict) -> str:
    return "".join(block.get("text", "") for block in message.get("content", []) or []
                   if isinstance(block, dict) and block.get("type") == "text")


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _label(tool: str, args: dict) -> str:
    value = next((args[key] for key in PRIMARY_ARGS
                  if isinstance(args.get(key), str) and args[key].strip()), "")
    if not value:
        value = next((v for v in args.values() if isinstance(v, str) and v.strip()), "")
    value = " ".join(str(value).split())
    return f"{tool}: {_clip(value, LABEL_CHARS)}" if value else tool


def _result_text(content) -> str:
    """Claude sends a tool result as a string or as a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(block.get("text", "") for block in content
                       if isinstance(block, dict) and block.get("type") == "text")
    return ""


class ToolCallTracker:
    """Folds Claude Code's tool stream into ONE record per completed call.

    Claude announces a call as a `tool_use` block on an `assistant` message and
    returns it as a `tool_result` block on the following `user` message. Only
    the result closes the call, so that is where a record is emitted — one trace
    event per real tool call, the moment it returns.

    Deliberately the same class name and `observe(event) -> record | None`
    contract as `agent_pi.ToolCallTracker`, so `agents._event_forwarder` works
    against either interface without knowing which one it has.
    """

    def __init__(self) -> None:
        self._open: dict[str, dict] = {}

    def observe(self, event: dict) -> Optional[dict]:
        etype = event.get("type")
        if etype == "assistant":
            for block in event.get("message", {}).get("content", []) or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    self._announce(block.get("id"), block.get("name"),
                                   block.get("input"))
            return None
        if etype != "user":
            return None

        for block in event.get("message", {}).get("content", []) or []:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            call_id = str(block.get("tool_use_id") or "")
            opened = self._open.pop(call_id, {})
            tool = str(opened.get("tool") or "tool")
            args = opened.get("args") or {}
            record = {
                "tool": tool,
                "tool_call_id": call_id,
                "args": {k: _clip(v, ARG_VALUE_CHARS) if isinstance(v, str) else v
                         for k, v in args.items()},
                "ok": not block.get("is_error", False),
                "label": _label(tool, args),
                "ended_at": now_iso(),
            }
            text = _result_text(block.get("content"))
            if text:
                record["result_snippet"] = _clip(text, RESULT_SNIPPET_CHARS)
            if opened.get("clock"):
                record["duration_ms"] = int((time.monotonic() - opened["clock"]) * 1000)
            if opened.get("started_at"):
                record["started_at"] = opened["started_at"]
            return record          # one record per event, as the Pi tracker does
        return None

    def _announce(self, call_id, tool, args) -> None:
        if not call_id:
            return
        known = self._open.get(str(call_id), {})
        self._open[str(call_id)] = {
            "tool": tool or known.get("tool", ""),
            "args": args or known.get("args", {}),
            "started_at": known.get("started_at") or now_iso(),
            "clock": known.get("clock") or time.monotonic(),
        }


def _usage_of(message: dict) -> dict:
    """Claude's usage shape -> the four components UsageBreakdown.add_turn wants.

    `input_tokens` already EXCLUDES cache reads, which is the same convention
    UsageBreakdown documents, so the two line up without adjustment. Cost is not
    reported per message — it arrives once on the `result` event — so it is
    added there rather than guessed here.
    """
    usage = message.get("usage", {}) or {}
    return {
        "input": usage.get("input_tokens") or 0,
        "output": usage.get("output_tokens") or 0,
        "cacheRead": usage.get("cache_read_input_tokens") or 0,
        "cacheWrite": usage.get("cache_creation_input_tokens") or 0,
    }


def _context_tokens(usage: dict) -> int:
    """How full the window is after a turn — every component, cache included."""
    return int(sum(usage.get(part) or 0
                   for part in ("input", "output", "cacheRead", "cacheWrite")))


def run(request: PiRequest, on_event: Optional[Callable[[dict], None]] = None,
        on_spawn: Optional[Callable[[int], None]] = None,
        on_exit: Optional[Callable[[int], None]] = None) -> PiResult:
    """Run one non-interactive Claude Code turn.

    `on_spawn(pid)` / `on_exit(pid)` bracket the child so the caller can record
    it as killable, exactly as the Pi interface does.
    """
    _, model = resolve_model(request.model)
    resolved = session_uuid(request.session_id)
    Path(request.session_dir).mkdir(parents=True, exist_ok=True)
    marker = _marker(request, resolved)

    cmd = [CLAUDE_PATH, "-p", "--output-format", "stream-json", "--verbose",
           "--model", model,
           "--effort", EFFORT.get(request.thinking, "medium"),
           "--system-prompt", request.system_prompt]
    # Create on the first send, resume on every one after. Passing --session-id
    # to an existing session is an error, and passing --resume to one that does
    # not exist is too, so the marker is what keeps the two straight.
    cmd += ["--resume", resolved] if marker.exists() else ["--session-id", resolved]

    tools = map_tools(request.tools)
    if tools is not None:
        # --tools decides what EXISTS, --allowedTools what runs without asking.
        # Both, or a non-interactive run stalls on the first permission prompt.
        cmd += ["--tools", ",".join(tools), "--allowedTools", ",".join(tools)]
    for extension in request.extensions:
        # Pi's -e is an extension file; Claude Code's nearest equivalent is an
        # MCP server config. Same field in the roster, each interface's own flag.
        cmd += ["--mcp-config", extension]

    raw_path = Path(request.raw_output_path)
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    result = PiResult(session_id=request.session_id)
    # The prompt goes in on STDIN, not argv — the opposite of the Pi interface,
    # for a reason that cost a run to find. `--tools` and `--allowedTools` are
    # variadic (`<tools...>`), so commander keeps consuming arguments until the
    # next flag: a trailing prompt is swallowed as one more tool name and claude
    # exits 1 with "Input must be provided either through stdin or as a prompt
    # argument". Comma-joining the values does not help — the option is still
    # variadic. Ordering the flags so a non-variadic one comes last would work
    # today and break the next time a flag is added.
    #
    # stdin is the documented input channel for --print, it is immune to flag
    # ordering, and it sidesteps ARG_MAX — which matters here, because prompts
    # carry whole envelopes and a diff-bearing one is not small.
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, bufsize=1, cwd=request.cwd,
                               env=operator_env())
    if on_spawn:
        on_spawn(process.pid)
    # Written from a thread, so a prompt larger than the pipe buffer cannot
    # deadlock against a child that is already writing to stdout. Closing the
    # pipe is what tells the CLI the prompt is complete.
    threading.Thread(target=_feed, args=(process, request.prompt),
                     daemon=True).start()

    with raw_path.open("a") as raw:
        assert process.stdout is not None
        for line in process.stdout:
            raw.write(line)
            raw.flush()
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type")
            if etype == "assistant":
                message = event.get("message", {}) or {}
                usage = _usage_of(message)
                turn = _context_tokens(usage)
                if turn:
                    result.tokens += turn
                    result.usage.add_turn(usage, turn)
                    result.context_tokens = turn
                if not result.context_window:
                    result.context_window = _window_of(event)
            elif etype == "result":
                # The final text and the authoritative cost both arrive here.
                # Cost is a whole-turn number from the CLI, so it is taken once
                # rather than accumulated per message and rounded differently.
                if event.get("result"):
                    result.text = str(event["result"])
                cost = event.get("total_cost_usd") or 0.0
                result.cost += cost
                result.usage.total_cost += cost
                if event.get("is_error") or event.get("subtype") != "success":
                    result.returncode = result.returncode or 1
            if on_event:
                on_event(event)

    stderr = process.stderr.read() if process.stderr else ""
    exit_code = process.wait()
    result.returncode = exit_code or result.returncode
    if on_exit:
        on_exit(process.pid)

    # The session now exists, so the next send must resume it. Written only
    # after a turn that actually produced something: a spawn that died before
    # the model was reached leaves no session to resume, and a marker would
    # make every retry fail with "no conversation found".
    if result.text or exit_code == 0:
        marker.write_text(now_iso())

    if result.returncode != 0 and not result.text:
        raise RuntimeError(
            f"claude exited {result.returncode}: {stderr.strip()[-800:] or '(no stderr)'}")
    return result


def _window_of(event: dict) -> int:
    """Context ceiling, when the stream mentions one. 0 means 'not declared'."""
    for source in (event.get("message", {}) or {}, event):
        for key in ("contextWindow", "context_window"):
            if source.get(key):
                return int(source[key])
    return 0
