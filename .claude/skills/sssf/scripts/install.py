#!/usr/bin/env -S uv run
# /// script
# dependencies = []
# ///
"""/install — stamp the SSSF factory from the skill into the cwd. Idempotent.

Usage:
    uv run <skill>/scripts/install.py [--force]

Stamps: adws/ (modules + starter ADWs), adws/adw_data/prompt_engineering/
(4 starter agents + the 8 DSDM agents + the 9 UCAF agents),
adws/adw_sssf_config/sssf.config.yaml, sssf.config.dsdm.yaml,
sssf.config.dsdm.cc.yaml and sssf.config.ucaf.yaml, .env.sample,
.gitignore entries. Existing files are skipped unless --force.
"""

import argparse
import shutil
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

GITIGNORE_ENTRIES = [
    "adws/adw_data/sessions/",
    "adws/adw_data/sssf.db*",
    ".env",
    # The ADWs are Python, so importing adw_modules writes bytecode next to it.
    # Chains that end in a commit phase call `git add -A`, so without this a
    # stamped repo commits its own .pyc files — 15 of them showed up in the
    # first repo that was ever installed into from scratch.
    "__pycache__/",
    "*.pyc",
]


def stamp(src: Path, dest: Path, force: bool, stamped: list, skipped: list) -> None:
    if src.is_dir():
        for child in sorted(src.iterdir()):
            if child.name == "__pycache__":
                continue
            stamp(child, dest / child.name, force, stamped, skipped)
        return
    if dest.exists() and not force:
        skipped.append(str(dest))
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    stamped.append(str(dest))


def ensure_gitignore(root: Path, stamped: list) -> None:
    gitignore = root / ".gitignore"
    existing = gitignore.read_text().splitlines() if gitignore.exists() else []
    missing = [e for e in GITIGNORE_ENTRIES if e not in existing]
    if missing:
        with gitignore.open("a") as f:
            f.write("\n# sssf runtime\n" + "\n".join(missing) + "\n")
        stamped.append(f"{gitignore} (+{len(missing)} entries)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args()

    root = Path.cwd()
    stamped, skipped = [], []

    stamp(TEMPLATES / "adws", root / "adws", args.force, stamped, skipped)
    stamp(TEMPLATES / "prompt_engineering",
          root / "adws" / "adw_data" / "prompt_engineering", args.force, stamped, skipped)
    stamp(TEMPLATES / "harness_engineering",
          root / "adws" / "adw_data" / "harness_engineering", args.force, stamped, skipped)
    stamp(TEMPLATES / "sssf.config.yaml",
          root / "adws" / "adw_sssf_config" / "sssf.config.yaml",
          args.force, stamped, skipped)
    # The DSDM roster ships alongside the starter one rather than replacing it.
    # Both are valid rosters over the same modules; `--config` (or SSSF_CONFIG)
    # picks which one a run uses, so a repo can hold the plain chain and the
    # governed one without either being the "other" install.
    stamp(TEMPLATES / "sssf.config.dsdm.yaml",
          root / "adws" / "adw_sssf_config" / "sssf.config.dsdm.yaml",
          args.force, stamped, skipped)
    # The same DSDM roster on the other coding agent. Identical agents, prompts
    # and boundaries; only `coding_agent` and the model ids differ. Which one you
    # run depends on whether `pi` or `claude` is installed, not on the workflow.
    stamp(TEMPLATES / "sssf.config.dsdm.cc.yaml",
          root / "adws" / "adw_sssf_config" / "sssf.config.dsdm.cc.yaml",
          args.force, stamped, skipped)
    # The UCAF roster — the same modules again, staffed as a cognitive chain
    # rather than a delivery one. Ships alongside the others for the same reason
    # they ship alongside each other: `--config` picks the roster, so a repo can
    # hold all three without any of them being the "other" install.
    stamp(TEMPLATES / "sssf.config.ucaf.yaml",
          root / "adws" / "adw_sssf_config" / "sssf.config.ucaf.yaml",
          args.force, stamped, skipped)
    stamp(TEMPLATES / "env.sample", root / ".env.sample", args.force, stamped, skipped)
    # The recipes are part of the operating experience, and several cookbooks
    # plus the run banner tell you to use them, so a stamped repo has to have
    # them. Skipped like any other file if the repo already has a justfile.
    stamp(TEMPLATES / "justfile", root / "justfile", args.force, stamped, skipped)
    ensure_gitignore(root, stamped)

    print(f"sssf installed into {root}")
    print(f"  stamped: {len(stamped)} file(s)")
    for s in stamped:
        print(f"    + {s}")
    if skipped:
        print(f"  skipped (already exist, use --force to overwrite): {len(skipped)}")
    print("\nnext steps:")
    print("  1. cp .env.sample .env   # then set the key(s) your roster needs")
    print("  2. just demo             # two cheap read-only runs, end to end")
    print("  3. just sessions         # what just happened")
    print("  4. just obs              # the trace UI, needs bun")
    print("\n  no just? the raw form of step 2 is:")
    print("     uv run adws/adw_prompt.py \"say hello\" --agent scout")
    return 0


if __name__ == "__main__":
    sys.exit(main())
