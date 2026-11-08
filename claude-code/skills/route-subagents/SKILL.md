---
name: route-subagents
description: "Choose the model and effort for each subagent or Codex run through the Decision Router (Drex Max, Jev 1.14 backup). Use before delegating any part of a user's task to a Claude subagent or to Codex, whenever the work is split into separate subtasks."
---

# Route subagents across Claude and Codex

OpenRouter pays only for the routing decision. The work runs on native Claude
subagents and on Codex under the user's own subscription. You (the session's
main model) break the task down, launch the workers and accept the results.

## When to route

Route when the task has two or more separate parts, or one large part worth
delegating. Do it without being asked: the user's global CLAUDE.md is a standing
request for this. Handle small work yourself (a question, a few reads, one edit)
without routing. Keep talking to the user, architecture, task breakdown and
final integration with yourself.

Project instructions win. If a project assigns a kind of work to Codex, list
only `codex_*` profiles for that work. Hard limits in the project (commits,
deletes, secrets, installs) still apply to every worker.

## Prepare the request

1. Read `profiles.json` next to this file and pass it unchanged as `profiles`.
2. Split the work into a small dependency graph. For each task write `id`,
   `role`, `description`, `acceptance` and `depends_on`.
3. Set `allowed_profiles` and `fallback_profile` from this table:

| Kind of task | allowed_profiles | fallback_profile |
|---|---|---|
| Code search, reading, fact collection | claude_haiku, claude_sonnet | claude_sonnet |
| Mechanical work with an automatic check | codex_luna, codex_terra, claude_haiku | codex_terra |
| Implementation or tests from a clear spec | codex_terra, codex_sol, claude_sonnet | codex_sol |
| Long multi-file work, migrations | codex_sol, codex_sol_high, claude_sonnet_high | codex_sol_high |
| Independent code review | codex_sol_high, claude_opus | codex_sol_high |
| Terminal, environment, session tools or connectors | claude_sonnet, claude_sonnet_high | claude_sonnet_high |
| Debugging, partly known cause | claude_sonnet_high, codex_sol_high, claude_opus | claude_opus |
| Debugging, unknown cause; risky decisions | claude_opus, codex_astra | claude_opus |

   A task with an automatic check means a test, build or grep can prove the
   result. Without one, do not offer `codex_luna`. A single allowed profile pins
   the task and costs no API call; use it when only one choice is adequate.

4. Omit `decision_model` and `fallback_decision_model`: the server applies Drex
   Max with Jev 1.14 as backup. Use `policy: "balanced"` unless the user asks
   otherwise, and `max_parallel: 3` at most.

Task text is sent to OpenRouter. Keep it short and describe the work, not the
data. Never include secrets, credentials, personal data or file contents. Use
`context` only when the choice depends on it.

## Call the router

Call `mcp__decision-router__route_tasks` once for the whole graph. If the tool is
missing, run the same JSON on stdin through
`{{PYTHON}} {{ROUTER_DIR}}/server/main.py route`.

Check `status`, `api_error`, `backup_used` and each `decision.source`. A
`fallback` decision is your preset, not a router choice. If routing fails, go on
with the fallback profiles and tell the user routing did not happen.
If the error is 401, 402 or 403, tell the user the key or balance needs attention.

## Launch the workers

Follow `execution_waves`. Start a dependent task only after its dependencies
succeeded, and put their actual results in its brief. Never let two workers edit
the same files at the same time.

**Profiles starting with `claude_`:** call the Agent tool with the assignment's
`model` as `model` and its `reasoning_effort` as `effort`. This skill explicitly
asks you to set `effort`. Give a self-contained brief: goal, files, output
format, acceptance criteria and the project's limits.

**Profiles starting with `codex_`:** write a self-contained task file in the
scratchpad, in English, and run:

```bash
{{PYTHON}} {{ROUTER_DIR}}/scripts/run_codex_task.py \
  --model <assignment.model> --effort <assignment.reasoning_effort> \
  --sandbox <read-only|workspace-write> \
  --task-file <task.md> --cwd <project root> --report <report.md>
```

Use `read-only` for review and research, `workspace-write` for implementation.
Run long tasks with `run_in_background`. The script prints one JSON line; read
`--report` only when `status` is `completed`. Codex starts cold, so the task file
must carry everything it needs. Codex cannot use this session's tools.

## Accept the work

Check every result against its `acceptance`: read the diff and run the tests
yourself. A worker's report and a router probability are not proof. If a worker
fails, diagnose first, then re-route only that task once with the failure
evidence. Do not retry in a loop.

Tell the user briefly which model did each task, what was verified, and what the
routing cost if `api_cost_usd_this_call` is known. Do not claim savings: they are
not measured.
