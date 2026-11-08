## Distributing work across subagents
- This is a standing instruction: when a task has two or more separate parts, or one large part worth handing off, split it and start the subagents yourself without asking again.
- Before launching, always use the `route-subagents` skill: the router (Drex Max, Jev 1.14 as backup) picks the model and effort for each Claude subagent and each Codex run.
- Do small work yourself (a question, a few reads, one edit), without subagents or the router.
- Keep the conversation with me, architecture, task breakdown and final verification with the main session model.
- Project limits (commits, deletes, secrets, package installs) apply to every worker too.
