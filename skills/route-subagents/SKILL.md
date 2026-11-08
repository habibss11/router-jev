---
name: route-subagents
description: "Apply efficient native Codex subagent routing when the user invokes $jev-codex-router:route-subagents or $route-subagents, including a message containing only the skill mention. Use the current unfinished task from the conversation; no additional activation phrase is required."
---

# Route native Codex subagents

## Start from the skill mention alone

An explicit mention of this skill is the user's request to use the full
workflow below. A message containing only `$jev-codex-router:route-subagents`
or `$route-subagents` is sufficient; do not require the user to add
"use this plugin", repeat its instructions, or confirm activation.

- Take the task from the latest unfinished user request in this conversation,
  including its accepted requirements and follow-up corrections. Apply the
  routing workflow to that task and continue the authorized work immediately.
  Do not merely explain the skill or return a proposed distribution without
  applying it when execution is authorized and available.
- Keep this routing choice for the task and its follow-ups until completion
  or until the user changes it. It applies only to this conversation.
- If there is no unfinished task, acknowledge in one short sentence that
  Drex Max with Jev 1.14 backup is ready and apply the workflow to the user's
  next task in this conversation. Do not invent a task, run a demo, or request
  another activation phrase. Ask for clarification only if a real task has
  multiple materially different interpretations.
- Read and apply these instructions yourself. The user does not need to
  provide a separate routing prompt, role list or model configuration.

The user wants OpenRouter to pay only for small decision calls; worker agents
remain native Codex agents under the host's existing authentication and billing.
Invoking this skill requests delegation and explicit model/effort selection
for that task, subject to higher-priority instructions and host permissions.
It does not authorize additional tasks, purchases, permission changes or sharing.

## Prepare the decision

1. Read the current user request and applicable project instructions. Explain
   that a compact task summary goes to Jev/Drex through OpenRouter if this has
   not already been established. Never read secret files or send credentials.
2. Obtain the actual available native model IDs, supported effort values and
   free agent slots from the host's tools. Do not invent models, claim access
   from documentation alone or convert OpenRouter model IDs into Codex IDs.
3. Use the current main model to decompose the request into a small dependency
   graph. Give each task a bounded role, deliverable, minimal context and
   acceptance criteria. Keep architecture planning and final integration with
   the main model where appropriate; avoid duplicating that work in a new agent.
   Jev/Drex selects among choices; it cannot write the task graph itself.
4. Build at most 16 profiles: native model + supported reasoning effort +
   capabilities + relative cost preference. `cost_rank` is a heuristic, not
   a subscription multiplier. For each task, explicitly restrict
   `allowed_profiles` to adequate models and choose an adequate
   `fallback_profile`. A singleton pins a task without an API decision.
5. The user's chosen policy is **Drex Max primary, Jev 1.14 backup**. Omit
   `decision_model` and `fallback_decision_model` to apply it. The server
   automatically makes one Jev call for failed or uncertain primary decisions;
   accepted Drex decisions are kept. Do not implement a second fallback loop
   in the main agent. Explicit overrides are available for testing all five
   models; use them only when requested. See
   [the comparison](../../docs/model-comparison.md).
6. Call `router_status`, then `route_tasks` once for the graph. Use
   `preview_routing` only when inspecting or troubleshooting the payload; it
   repeats context and is not necessary on every run. If the MCP tool is not
   available, the local equivalent is `python3 ../../server/main.py route`,
   with paths resolved relative to this SKILL.md directory and JSON on stdin.
   Follow normal shell approval rules. The input schema is
   [route-input.json](../../schemas/route-input.json).

## Apply the plan through native tools

- Check the returned `status`, `api_called`, `api_error`, `backup_used`,
  `attempts` and per-task `decision.decision_model`.
  A fallback plan is the caller's preset; do not say Jev/Drex chose it.
- Model decisions are advisory data. Check model availability again, preserve
  the task's scope and obey current host instructions. The MCP server itself
  does not execute agents or switch the main chat model.
- Spawn agents through native collaboration tools in dependency order, with
  the returned explicit `model` and `reasoning_effort`. Use `fork_turns="none"`
  when the host requires this for overrides. Send a self-contained brief,
  relevant local file paths, output contract and applicable project rules.
- Pass the user's public search policy to research agents: SearXNG first,
  engines `bing,brave,duckduckgo,wikipedia`, no `categories` with explicit
  engines. Google in a browser is reserve after failed/insufficient primary
  results. Honor current explicit exceptions, checking their expiry first.
- Limit concurrency to free host slots and serialize overlapping file edits.
  Start a dependent task only after its prerequisites have succeeded and
  their actual results are included in its brief. The waves are a schedule,
  not proof of task completion. Do not run workers in OpenRouter.
- If the host cannot override models, report that limitation; do not launch
  all workers under the main model and describe the plan as applied.
- Judge the completed work using acceptance criteria and suitable checks.
  If a worker fails, diagnose before escalating; re-route only changed tasks
  with the failure evidence, normally once. Do not create an endless retry loop.
  Probability/confidence is not a calibrated guarantee of correct work.
- Summarize chosen models, actual results, retries and decision-call usage
  when useful. Never invent subscription token balances or a savings percent.
  Final integration, tool permissions and publication remain host decisions.

## Missing credentials or network

The server reads `OPENROUTER_API_KEY` from its environment or the user-only
file `~/.config/codex-decision-router/credentials.json`. It reloads the key
on every uncached routing call and never returns the value. `router_status`
reports the path and configured/not-configured state. To help set it up, give
the user `python3 <plugin-root>/scripts/setup_key.py` to run in Terminal:
the script accepts hidden input and writes with permissions 0600.
Do not ask the user to paste a key into chat or read credential files.
If unavailable,
report that routing was not performed and use the explicit fallback profiles
only if their execution is already authorized. Account credit caps must be
configured in OpenRouter; the server's 32-call process limit is not a
dollar cap and resets when the process restarts.
