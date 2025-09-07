# Codex-Plus — User Story Product Specification (v1.1)

- Product: Codex-Plus
- Version: 1.1
- Status: Proposed
- Date: September 7, 2025

## Executive Summary

Codex-Plus provides an “IDE in the terminal” experience that is indistinguishable from Codex CLI, adding power-user workflows without changing how users interact.

- Identical look and feel to Codex CLI; zero learning curve.
- Slash commands compatible with Claude Code CLI conventions.
- Optional pre-input and post-output hooks to enrich prompts and act on responses.
- Remote MCP tool support to use external tools within the session.
- Persistent sessions to resume work exactly where you left off.
- Optional predictable-cost mode for budgeting, when available.

## Vision

Codex-Plus delivers an “IDE in the terminal” experience that looks and feels exactly like Codex CLI, while adding power‑user features such as slash commands, workflow hooks, remote MCP tools, and persistent sessions. It introduces these capabilities with zero learning curve and optional support for predictable costs, without changing how users naturally work in the terminal.

## Product Principles

- UI Parity: Looks and behaves exactly like Codex CLI.
- Non‑Invasive: Feels the same as Codex CLI; no new concepts to learn.
- Extensible by Design: Simple, discoverable ways to add commands, integrate tools, and automate workflows.
- Predictable Costs Option: An optional mode that aligns with fixed‑cost usage plans where available.
- Fast and Reliable: Interactions feel instantaneous and resilient during long sessions.

## User Stories (with Acceptance Criteria)

1) Identical Terminal Experience [MUST]

- As a terminal‑first developer, I want the product to look and behave exactly like Codex CLI so I can switch with zero learning curve.
- Acceptance:
  - Starting and using the product is indistinguishable from Codex CLI in prompts, streaming, colors, keyboard behavior, and interaction flow.
  - All non‑slash input behaves exactly as in Codex CLI.
  - Interactive question/answer flows remain smooth (e.g., confirmations).

2) Slash Commands [MUST]

- As a power user, I want slash commands prefixed with “/” that follow Claude Code CLI conventions so I can trigger actions quickly.
- Acceptance:
  - Slash commands are recognized and execute immediately without altering non‑slash behavior.
  - I can list available commands and see brief descriptions via `/help`.
  - Command names and argument patterns align with Claude Code CLI conventions.

3) Hooks: Pre‑Input and Post‑Output [MUST]

- As a user, I want to optionally modify prompts before sending and act on responses after receiving so I can automate parts of my workflow.
- Acceptance:
  - I can choose to have prompts enriched or adjusted before sending.
  - I can choose to observe or act on responses after they appear.
  - I can easily turn these behaviors on or off.

4) Remote MCP Tools [MUST]

- As a user of MCP tools, I want to connect to remote MCP tools consistent with Claude Code CLI so I can use external tools inside the conversation.
- Acceptance:
  - Remote MCP tools can be listed and invoked from within the session.
  - Tool results appear inline and are part of the conversation history.
  - Behavior matches user expectations from Claude Code CLI.

5) Persistent Sessions [MUST]

- As a user, I want my session to persist across terminal restarts so I never lose context.
- Acceptance:
  - Closing and reopening resumes the same conversation with complete history intact.
  - I can optionally save or export a transcript of the session (e.g., via `/save`).

6) Seamless Passthrough [MUST]

- As a user, I want anything that is not a slash command to be treated as normal Codex CLI input so I can work as usual.
- Acceptance:
  - All non‑slash messages pass through unchanged.
  - There is no noticeable latency added to typical interactions.

7) Interactive Prompts [MUST]

- As a user, I want interactive prompts and confirmations to work naturally so I can respond without friction.
- Acceptance:
  - When asked to confirm actions (e.g., run code, apply changes), simple inputs like “y/n” work as expected.
  - Complex interactive flows remain responsive and intuitive.

8) Discoverability and Defaults [SHOULD]

- As a new user, I want built‑in help, status, and quit commands, and clear guidance on capabilities so I can onboard quickly.
- Acceptance:
  - `/help` lists built‑in and user‑defined slash commands with short descriptions.
  - `/status` shows connection status and current session information.
  - `/quit` exits gracefully without losing information.

9) Predictable Costs Option [MUST]

- As a heavy user or team, I want an option to use predictable, fixed‑cost usage so budgeting is easier.
- Acceptance:
  - I can choose to operate in a mode that supports predictable, fixed‑cost usage, when available.
  - Choosing this option does not change how I interact.

10) Raw Attach Mode [SHOULD]

- As a power user, I want an optional mode that shows the raw underlying session for complex interactions so I can troubleshoot or handle advanced cases.
- Acceptance:
  - A command is available to switch into and out of a direct, raw session view.
  - In this view, only direct interactions are shown until I exit.

11) Performance and Reliability [SHOULD]

- As a user, I want interactions to feel instantaneous and robust so I can stay in flow.
- Acceptance:
  - Typical interactions feel as fast as Codex CLI.
  - The product remains responsive during long outputs or extended sessions.

## Default Commands

- `/help`: Show all available slash commands (built‑in and user‑defined) with short descriptions.
- `/status`: Show current connection status and session information.
- `/quit`: Gracefully end the session.
- `/attach`: Enter a raw, direct session view (optional raw mode).
- `/save`: Export the current transcript to a file.

## Non‑Goals (v1.0)

- No graphical user interface; terminal‑only experience.
- No multi‑user or multi‑session management.
- No built‑in advanced AI features beyond what users can create with slash commands, hooks, or MCP tools.

## Compatibility Note

Slash commands, remote MCP tools, and hooks follow Claude Code CLI conventions.
