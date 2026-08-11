---
name: sc-tdd
description: Classify a feature as backend, UI, fullstack, or ambiguous, then run the matching test-first pipeline and integration checks. Use when the user asks for TDD, test-first or test-driven implementation, requires tests before code, invokes $sc-tdd in Codex or /sc-tdd in Claude Code, or describes a feature without making the backend/UI boundary clear.
---

# Overview

This skill is the entry point for Test-First Development. It classifies the request, routes execution to `sc-tdd-backend` or `sc-tdd-uiux`, and—when the feature spans both domains—coordinates both pipelines and emits integration tests.

**Invoke this skill when:**

- The user explicitly invokes `$sc-tdd` in Codex or `/sc-tdd` in Claude Code, or says "TDD", "test-first", or "test-driven"
- Tests must be written before implementation as an explicit discipline
- The feature description does not make clear whether it is backend, UI, or both
- Automated quality validation (type check, lint, coverage) should run as part of delivery

For direct execution when the domain is already certain, use `sc-tdd-backend` or `sc-tdd-uiux` instead to skip classification.

# Classification

Classify the request using semantic understanding of the feature, not only keyword matching. Produce one of four labels and a one-sentence justification:

| Label | Meaning | Action |
|-------|---------|--------|
| `BACKEND_ONLY` | Feature is purely server-side logic (API, service, CLI, job, data processing) | Run `sc-tdd-backend` |
| `UI_ONLY` | Feature is purely client-side rendering or interaction (component, form, page) | Run `sc-tdd-uiux` |
| `FULLSTACK` | Feature requires both a backend contract and a UI that consumes it | Run both pipelines in parallel when allowed, otherwise sequentially, then generate integration tests |
| `AMBIGUOUS` | Could reasonably be either—insufficient signal to choose | Ask the user to disambiguate before proceeding |

Keyword weights (backend: `endpoint`, `API`, `service`, `middleware`, `migration`, `cron`, `cli`; UI: `component`, `form`, `modal`, `React`, `Vue`, `accessibility`, `layout`) are a sanity check for the semantic judgment, not the primary mechanism. When semantic and keyword signals disagree, prefer the semantic reading and state the tension.

Force flags override classification entirely: `--force-backend`, `--force-ui`, `--force-fullstack`.

# Pipeline

1. **Convention Discovery** — Read applicable `AGENTS.md` files first, then `README.md`, optional `CLAUDE.md` or `.claude/CONVENTIONS.md`, and framework configuration. Read independent files in parallel when the runtime supports it. If no project convention exists, use framework defaults and state them; ask only when a choice would materially change behavior.
2. **Classification** — Produce a label and justification. On `AMBIGUOUS`, ask; on others, proceed.
3. **Specialized Pipeline** — Read the matching sibling `SKILL.md` and follow it. For fullstack work, run both pipelines concurrently only when delegation is available and permitted; otherwise run them sequentially. Each specialized pipeline begins with **Test Case Design** via `sc-test-design`, which produces a role-reviewed test-case spec (What/Who/Why + GWT + negative per case) that feeds its Test Generation phase.
4. **Integration (fullstack only)** — After both pipelines reach green, generate cross-domain tests that exercise the UI against the real backend contract.
5. **Commit** — Propose a conventional commit message with coverage metrics and wait for the user's explicit approval before running `git commit`.

# Runtime Compatibility

- Use the current agent and the runtime's available file, shell, and plan tools. Do not require Claude Code's `Task` tool, fixed Claude model names, or any provider-specific subagent API.
- Read [`../sc-tdd-backend/SKILL.md`](../sc-tdd-backend/SKILL.md), [`../sc-tdd-uiux/SKILL.md`](../sc-tdd-uiux/SKILL.md), or both after classification; do not assume a slash command can invoke another skill automatically.
- Delegate or parallelize only when the runtime supports it and the user or active project instructions permit it. If not, execute the same phases sequentially without reducing scope.
- Treat `--cost-optimize` as fewer review passes and `--quality-first` as deeper edge-case analysis and an additional review pass. Do not map either flag to a hard-coded model.

# Tool Use Guidance

- Spend the deepest reasoning on Test Case Design and Test Generation, where missed edge cases are most expensive. Keep mechanical quality-gate execution concise.
- **Parallel tool calls** are the default for independent reads (convention files, framework detection, directory listing). Sequential calls are reserved for genuinely dependent work.
- **Progressive disclosure**: this file is the entry surface. Load only the sibling specialized skill selected by classification, or both for fullstack work.

# Boundaries

**Will:**
- Classify requests and route to the appropriate specialized skill
- Run `sc-test-design` as the Test Case Design lead-in before each pipeline's Test Generation
- Run both backend and UI pipelines for fullstack features, concurrently when permitted and otherwise sequentially
- Emit integration tests after both fullstack pipelines reach green
- Discover and follow applicable project conventions before writing code
- Require explicit user approval before any commit

**Will Not:**
- Run both domains when the request is clearly single-domain
- Proceed on `AMBIGUOUS` classifications without asking
- Skip convention verification, quality gates, or commit confirmation
- Push to a remote unless the user explicitly requests it

# See Also

- [sc-test-design](../sc-test-design/SKILL.md) — Test Case Design lead-in that produces the role-reviewed spec
- [sc-tdd-backend](../sc-tdd-backend/SKILL.md) — backend pipeline
- [sc-tdd-uiux](../sc-tdd-uiux/SKILL.md) — UI/UX pipeline
