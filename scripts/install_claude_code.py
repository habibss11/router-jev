#!/usr/bin/env python3
"""Install the router skill for Claude Code and register its MCP server.

Copies claude-code/skills/route-subagents to ~/.claude/skills with this
checkout's paths filled in, then runs `claude mcp add --scope user`. It does not
touch settings.json or CLAUDE.md; the steps for those are printed at the end.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "claude-code" / "skills" / "route-subagents"


def render(text, python, router_dir):
    return text.replace("{{PYTHON}}", str(python)).replace("{{ROUTER_DIR}}", str(router_dir))


def install_skill(target, python):
    target.mkdir(parents=True, exist_ok=True)
    for source in SOURCE.iterdir():
        text = render(source.read_text(encoding="utf-8"), python, ROOT)
        (target / source.name).write_text(text, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude", default=shutil.which("claude"), help="path to the claude binary")
    parser.add_argument("--python", default=sys.executable, help="python used to run the MCP server")
    parser.add_argument("--skills-dir", type=Path, default=Path.home() / ".claude" / "skills")
    args = parser.parse_args(argv)
    if not args.claude:
        print("claude binary not found; pass --claude <path>", file=sys.stderr)
        return 1
    target = args.skills_dir / "route-subagents"
    if target.exists():
        print(f"{target} already exists; remove it first to reinstall", file=sys.stderr)
        return 1
    install_skill(target, args.python)
    command = [args.claude, "mcp", "add", "--scope", "user", "decision-router",
               "-e", "PYTHONDONTWRITEBYTECODE=1", "--", args.python,
               str(ROOT / "server" / "main.py"), "serve"]
    done = subprocess.run(command)
    if done.returncode:
        print("MCP registration failed; the skill files were copied", file=sys.stderr)
        return done.returncode
    print(f"""
Installed. Remaining manual steps:
1. Add your OpenRouter key: {args.python} {ROOT / 'scripts' / 'setup_key.py'}
2. Allow the router tools in ~/.claude/settings.json under permissions.allow:
   mcp__decision-router__router_status, mcp__decision-router__preview_routing,
   mcp__decision-router__route_tasks
3. Paste {ROOT / 'claude-code' / 'CLAUDE-snippet.md'} into ~/.claude/CLAUDE.md
   to make routing automatic.
4. Start a new Claude Code session so the tools load.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
