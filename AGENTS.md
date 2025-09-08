Codex CLI Usage

- This repository assumes development and conversations happen inside the Codex CLI. When you see “start Codex” or run sessions in this repo, it refers to launching the `codex` command in your terminal.
- Prefer demonstrating workflows with Codex CLI flags rather than raw API calls. Useful flags:
  - `-m, --model <MODEL>`: choose the model for the agent
  - `-i, --image <FILE>`: attach image(s) to the first prompt
  - `-p, --profile <NAME>`: use a profile from `~/.codex/config.toml`
  - `-a, --ask-for-approval <POLICY>` and `-s, --sandbox <MODE>`: control execution approvals and sandboxing
  - `--full-auto`: shortcut for low‑friction automatic execution (`-a on-failure`, `--sandbox workspace-write`)
  - `--yolo`: development convenience to run fast without friction (intended for trusted environments)

Model Selection

- Set the model with `codex -m <model_id>` or via config (`-c model="<model_id>"`).
- Use `gpt5-high` as a convenience alias in this repo; the proxy maps it to the current flagship GPT‑5 model (default `gpt-5-chat-latest`). Override with `GPT5_HIGH_TARGET` if needed.
- If a provided model ID isn’t available to your account, Codex will return an error—switch to an available ID per your provider access.

Working With This Repo

- The project includes a Codex‑Plus proxy that can transparently intercept Codex CLI traffic. To route Codex through it while the proxy is running locally: `OPENAI_BASE_URL=http://localhost:3000 codex`.
- Default Codex settings live in `~/.codex/config.toml`. You can override any config at launch with `-c key=value` (the value is parsed as JSON when possible).
- When contributing instructions for agents, assume a Codex session context unless explicitly noted otherwise.

Quick Notes for Agents

- Keep changes focused and minimal; follow existing code style.
- Prefer CLI examples like `codex -m <model> "prompt"` when illustrating usage.
- If you need to pick a “best GPT‑5” default in examples, prefer the current flagship GPT‑5 release ID available to the user; fall back to a widely available variant if needed.

Billing Note

- ChatGPT (Plus/Team/Enterprise) subscriptions apply to the ChatGPT apps and do not cover OpenAI API usage. API access is billed usage‑based in the OpenAI Platform. Ensure the API project has an active payment method and spending limit to avoid `insufficient_quota` errors.
