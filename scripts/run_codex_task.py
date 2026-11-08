#!/usr/bin/env python3
"""Run one bounded task through the Codex CLI with an explicit model and effort.

Claude Code calls this for router profiles whose id starts with codex_. The
effort is always passed explicitly so the user's config.toml default is not used.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

MODELS = ("gpt-6-luna", "gpt-6.1-terra", "gpt-6.1-sol", "gpt-6-astra")
EFFORTS = ("low", "medium", "high", "xhigh", "max")  # ultra spawns its own subagents.
SANDBOXES = ("read-only", "workspace-write")
GUARDRAILS = """Rules for this run:
- Work only on the task below and only inside the working directory.
- Do not commit, push, merge, rebase or tag.
- Do not delete files unless the task explicitly lists them.
- Do not read, print or edit secrets: .env files, keys, tokens, credential files.
- Do not install packages or use the network.
- If the task needs any of the above, stop and say so in your final message.
- Finish with: what changed, files touched, commands run, test results, open questions.

Task:
"""


def build_command(codex, model, effort, sandbox, cwd, report):
    return [codex, "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"',
            "-s", sandbox, "--skip-git-repo-check", "-C", str(cwd), "-o", str(report), "-"]


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=MODELS)
    parser.add_argument("--effort", required=True, choices=EFFORTS)
    parser.add_argument("--sandbox", required=True, choices=SANDBOXES)
    parser.add_argument("--task-file", required=True, type=Path)
    parser.add_argument("--cwd", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=1800, help="seconds")
    return parser.parse_args(argv)


def emit(**result):
    print(json.dumps(result, ensure_ascii=False))
    return result["exit_code"]


def main(argv=None):
    args = parse_args(argv)
    common = {"model": args.model, "effort": args.effort, "report": str(args.report)}
    codex = shutil.which("codex")
    if not codex:
        return emit(status="error", error="codex_not_found", exit_code=1, **common)
    if not args.cwd.is_dir():
        return emit(status="error", error="cwd_not_found", exit_code=1, **common)
    try:
        task = args.task_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return emit(status="error", error="task_file_unreadable", exit_code=1, **common)
    if not task.strip():
        return emit(status="error", error="task_file_empty", exit_code=1, **common)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.unlink(missing_ok=True)  # A stale report must not look like this run's result.
    log = args.report.with_name(args.report.name + ".log")
    command = build_command(codex, args.model, args.effort, args.sandbox, args.cwd, args.report)
    started = time.monotonic()
    common["log"] = str(log)
    with log.open("w", encoding="utf-8") as output:
        try:
            done = subprocess.run(command, input=GUARDRAILS + task, text=True, stdout=output,
                                  stderr=subprocess.STDOUT, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            return emit(status="timeout", exit_code=124, elapsed_s=args.timeout, **common)
    elapsed = round(time.monotonic() - started, 1)
    has_report = args.report.is_file() and args.report.stat().st_size > 0
    if done.returncode == 0 and has_report:
        return emit(status="completed", exit_code=0, elapsed_s=elapsed, **common)
    error = "codex_failed" if done.returncode else "empty_report"
    return emit(status="failed", error=error, exit_code=done.returncode or 1, elapsed_s=elapsed, **common)


if __name__ == "__main__":
    sys.exit(main())
