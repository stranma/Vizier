# Vizier Tech Stack

## Research Summary (February 2026)

Based on evaluation of 8 agent frameworks, 5 LLM routing libraries, 2 messaging platforms, and dozens of infrastructure tools.

## Key Finding: Build Our Own Thin Runtime

No existing agent framework fits Vizier's model. Every framework assumes either:
- **LLM-driven orchestration** (Claude SDK, CrewAI, OpenAI SDK) — an LLM decides what to do next
- **Graph-driven orchestration** (LangGraph, Microsoft Agent Framework) — a pre-defined graph determines flow

Vizier uses **event-driven, code-driven orchestration**: filesystem watch triggers Python code that spawns isolated agent calls. This is the product differentiator — adopting someone else's orchestration means giving it away.

The runtime is ~1500 lines of Python. Use libraries as building blocks, not frameworks as foundations.

## Recommended Stack

### Core Runtime (build ourselves)

| Component | Lines (est.) | Purpose |
|-----------|-------------|---------|
| Agent runtime | ~200 | Spawn LLM call with prompt + tools, get output, discard context |
| Spec state machine | ~300 | DRAFT -> READY -> IN_PROGRESS -> REVIEW -> DONE/REJECTED/STUCK |
| Event loop | ~300 | watchdog filesystem monitoring -> Python handlers -> agent spawning |
| Tool registry | ~200 | Define tools per agent role, enforce plugin restrictions |
| Plugin loader | ~100 | Entry point discovery, class instantiation |
| Model router | ~50 | Map abstract tiers to provider/model pairs via LiteLLM |

### LLM Provider Layer

| Tool | Purpose | Why this one |
|------|---------|-------------|
| **LiteLLM** (library mode) | Multi-provider LLM abstraction | Unified interface to 100+ providers. Auto cost tracking. Provider swap = config change. 35.7k stars. |

**Architecture**: Use LiteLLM as a Python library (`litellm.completion()`), not as a Docker proxy. Vizier is 100% Python — no need for a separate proxy process, Docker dependency, or network hop.

Model tiers defined in Vizier's config:

```yaml
# /opt/vizier/config.yaml
model_tiers:
  opus:    anthropic/claude-opus-4-6
  sonnet:  anthropic/claude-sonnet-4-5-20250929
  haiku:   anthropic/claude-haiku-4-5-20251001
  worker-oss: huggingface/Qwen/Qwen3-14B  # future, Phase 5+
```

Agent code calls `litellm.completion(model=resolved_model, ...)` — the model router maps abstract tiers to concrete model strings.

**Reconsider proxy mode when:** Vizier adds non-Python components, or multiple Vizier instances need shared cost budgets.

**Future**: Qwen3-14B on HF Inference Endpoints as cheap Worker-tier alternative (5-6x less than API calls at scale).

### Communication Layer

| Tool | Purpose | Why this one |
|------|---------|-------------|
| **OpenClaw** | Messaging bridge (Telegram, WhatsApp, Slack, Discord) | 145k stars. Battle-tested channel adapters for 12+ platforms. MIT license. |
| **aiogram 3.x** | Direct Telegram bot (fallback / simpler option) | Async-first, Pydantic types, modern. Better than python-telegram-bot for new projects. |

**Architecture**: Two options (decide during implementation):

**Option A: OpenClaw as gateway** (recommended for multi-channel)
```
User (WhatsApp/Telegram/Slack)
  -> OpenClaw (TypeScript, Docker)
     -> Custom MCP tool or webhook
        -> Vizier EA (Python)
```
OpenClaw handles channel normalization, auth, message formatting. Vizier handles business logic.

**Option B: Direct aiogram** (simpler, Telegram-only)
```
User (Telegram)
  -> aiogram bot
     -> Vizier EA (Python)
```
Simpler, no TypeScript dependency. Sufficient if Telegram is the only channel.

**Recommendation**: Start with Option B (aiogram). Migrate to Option A when multi-channel becomes needed.

### Calendar & Productivity MCP

| Tool | Purpose | Why this one |
|------|---------|-------------|
| **workspace-mcp** | Google Calendar + Gmail + Docs + Drive (personal) | All-in-one, Python, OAuth 2.1. For Sultan's personal Google account. |
| **Microsoft 365 MCP Server** | Outlook Calendar + Mail + Files (company) | Graph API-based. For Sultan's company account (algoenergy.cz). EA unifies both calendars. |
| **FastMCP 3.0** | Build custom MCP servers | Clean API, Jinja2-like simplicity for defining tools. |
| **telegram-mcp** | AI agent controlling Telegram (send messages, read chats) | Full-featured, Telethon-based. |

### Infrastructure

| Tool | Purpose | Why this one |
|------|---------|-------------|
| **watchdog 6.0** | Filesystem event watching | De facto standard. 14 years of maintenance. Linux/macOS/Windows. |
| **Jinja2** | Prompt templates | Industry standard. Inheritance, includes, macros. |
| **Pydantic** | Typed agent I/O, spec models, tool contracts | Type safety for specs, config, tool parameters. |
| **pluggy 1.6 + apluggy** | Plugin framework (optional) | pytest-proven. apluggy adds async support. |
| **importlib.metadata entry_points** | Plugin discovery | PyPA standard. Works with any build backend. |
| **structlog** | Structured logging | JSON-formatted agent invocation logs (tokens, cost, duration). Append to `reports/<project>/agent-log.jsonl`. |
| **systemd** | Daemon management | Simple unit file, no library needed. `Type=simple`, `Restart=always`. |
| **uv** | Package management, workspaces | Already using. Monorepo with libs/core, apps/daemon, apps/cli, plugins/*. |
| **ruff** | Lint + format | Already using. Line length 120, fast. |
| **pyright** | Type checking | Already using. Standard mode. |
| **pytest** | Testing | Already using. |

### What We Explicitly Do NOT Use

| Tool | Why not |
|------|---------|
| **LangGraph / LangChain** | Graph-driven orchestration doesn't match our event-driven model. Heavy abstractions. |
| **CrewAI** | LLM-driven orchestration. Agents share context (opposite of fresh-context). Moving to paid. |
| **AutoGen / Microsoft Agent Framework** | In flux (merger). .NET-first. Azure ecosystem gravity. |
| **Claude Agent SDK** | Anthropic-only. LLM-driven orchestration. Pre-1.0. But good inspiration for subagent isolation. |
| **OpenAI Agents SDK** | Handoff/conversation model, not spawn-and-forget. OpenAI ecosystem bias. |
| **Google ADK** | Google Cloud ecosystem. Wrong deployment model. |
| **Redis / NATS** | Filesystem watch is sufficient at our scale. Zero infrastructure benefit. |
| **OpenRouter** | No self-hosting, no custom routing rules. Fine for experiments. |
| **aisuite** | Development stalled. No streaming, no cost tracking. |

## Open-Source Model Strategy

For cost optimization, deploy open-source models as Worker-tier alternatives:

| Model | Size | Use case | Host on |
|-------|------|----------|---------|
| **Qwen3-14B** | 14B | Worker tasks (coding, structured output) | HF Inference Endpoints / self-host |
| **DeepSeek-R1-Distill-8B** | 8B | Reasoning-heavy Worker tasks | HF Inference Endpoints |
| **Mistral 3B** | 3B | Ultra-cheap simple edits | Self-host on CPU |

LiteLLM proxy handles routing. Agent code doesn't know or care which model serves the request.

**Timeline**: Start with Anthropic API only (Phases 0-4). Add HF-hosted open-source models in Phase 5+ as cost optimization.

## Package Dependencies

### libs/core (vizier-core)

```toml
dependencies = [
    "litellm>=1.0",           # LLM provider abstraction
    "pydantic>=2.0",          # Typed models (specs, config, tool contracts)
    "jinja2>=3.0",            # Prompt templates
    "watchdog>=6.0",          # Filesystem event watching
    "pyyaml>=6.0",            # Config files, spec frontmatter
    "python-frontmatter>=1.0", # Markdown frontmatter parsing
    "filelock>=3.0",          # Cross-process file locking for state.json
]
```

### apps/daemon (vizier-daemon)

```toml
dependencies = [
    "vizier-core",
    "aiogram>=3.25",          # Telegram bot (EA communication)
    "uvicorn>=0.30",          # ASGI server (if we need HTTP endpoints)
]
```

### apps/cli (vizier-cli)

```toml
dependencies = [
    "vizier-core",
    "click>=8.0",             # CLI framework
    "rich>=13.0",             # Terminal formatting
]
```

### plugins/software (vizier-plugin-software)

```toml
dependencies = [
    "vizier-core",
]
# No additional deps — uses bash tools for pytest/ruff/git
```

### plugins/documents (vizier-plugin-documents)

```toml
dependencies = [
    "vizier-core",
    "python-docx>=1.0",      # Word document generation
    "openpyxl>=3.0",         # Excel file generation
]
```
