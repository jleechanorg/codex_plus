## Successful Patterns
- `claude -p /copilot` before edits enforced search-first validation, surfaced blockers early, and kept loops single-task.
- `claude -p /execute` as the lone command per loop delivered deterministic updates without scheduler retries.
- Pairing `/think --checkpoint` snapshots with shell snapshots kept state under 2k tokens for fast recoveries.
- Running `./run_tests.sh` prior to `claude -p /pr` maintained >97% pass confidence and clean handoffs.

## Avoid These Patterns
- Stacking multiple slash commands in one `claude -p` (e.g., `/copilot /execute /push`) deadlocked the scheduler and restarted loops.
- Delegating to agents missing frontmatter fields (`description`, tools) triggered parser failures and blocked orchestration.
- Skipping search validation or plan refresh led to redundant sweeps and inflated context windows.
- Spawning auxiliary MCP servers on occupied ports (worldarchitect:8000) aborted delegation; verify availability first.

## Genesis Optimizations
- [context conservation techniques] Keep `fix_plan.md` prioritized, reuse shell snapshots, and checkpoint with `/think --checkpoint` to preserve concise state.
- [subagent delegation improvements] Cap heavy `claude -p` delegations at five per loop, ensure `.claude/agents/*.md` metadata is complete, and assign tasks to single-purpose YAML agents.
- [genesis principle outcomes] Succeeded: ONE ITEM PER LOOP, SEARCH FIRST, NO PLACEHOLDERS. Needs attention: CONTEXT ENHANCEMENT when hooks auto-inject large prompts—trim extras before delegating.
