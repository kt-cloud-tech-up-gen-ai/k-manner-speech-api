---
name: sc-tdd-backend
description: Run a backend-specialized red-green-refactor pipeline with test-case design, isolated red verification, minimal implementation, and configured quality gates. Use for APIs, services, middleware, background jobs, schedulers, CLI tools, data migrations, and other non-UI logic, or when the user invokes $sc-tdd-backend in Codex or /sc-tdd-backend in Claude Code.
---

# Overview

This skill runs the Test-First Development pipeline for backend work: tests are generated and verified to fail first, implementation is kept minimal, and quality gates enforce type safety, lint, and coverage before the commit is proposed.

**Invoke this skill when:**

- The user explicitly invokes `$sc-tdd-backend` in Codex or `/sc-tdd-backend` in Claude Code
- The feature is unambiguously server-side (endpoint, service, middleware, job, CLI, migration)
- The `sc-tdd` orchestrator classifies the request as `BACKEND_ONLY`
- Data processing, queue workers, or scheduled tasks need tests before implementation

# Pipeline

1. **Test Case Design** — Read and follow [`../sc-test-design/SKILL.md`](../sc-test-design/SKILL.md) first to produce a role-reviewed spec: each case records What it tests, Who it protects, and Why it matters, plus a Given/When/Then and a negative companion. If the project has no role file, `sc-test-design` creates `.claude/test-roles.md` (five default roles) before designing cases. This spec is the input to Test Generation.
2. **Test Generation** — Turn each spec case into a unit test (pure logic), integration test (external boundaries), or error-path test. Run each newly written test in isolation and confirm that the intended test body is reached and fails **consistently** at the intended assertion. Collection, compilation, shared setup/teardown, unrelated, unconditional, or flaky failures do not count — unless the existence of that symbol, module, or schema is itself the contract under test. Reproduce the same red at least twice and record the test ID and the failure message.
3. **Implementation** — Write the minimum code to pass the tests, one cycle at a time. On failure, diagnose from current evidence before retrying, up to 3 attempts.
4. **Quality Gates** — Discover and run every gate configured by the repository: tests, type check, lint, formatter, and coverage. Require coverage ≥ 80% when coverage tooling and a threshold are configured. Auto-fix task-introduced issues up to 2 times per available gate before pausing. Report an absent gate as `not configured`; do not install new tooling unless the user asks for it.
5. **Cleanup** — Remove unused imports, dead code, and temporary files introduced during the cycle.
6. **Commit** — Propose a conventional commit message with coverage metrics. Wait for the user's explicit approval.

# Runtime Compatibility

- Use the current agent and the runtime's available file, shell, and plan tools. Do not require Claude Code's `Task` tool, fixed Claude model names, or any provider-specific subagent API.
- Run the pipeline in the current agent by default. Delegate independent review or verification only when the runtime supports it and the user or active project instructions permit delegation; lack of delegation must never skip a phase.
- Treat `--cost-optimize` as fewer review passes and `--quality-first` as deeper edge-case analysis and an additional review pass. Do not map either flag to a hard-coded model.
- Discover the repository's configured test, type, lint, format, and coverage commands before running gates. Run every available gate, report unavailable gates as `not configured`, and do not install or invent a tool solely to satisfy a gate.

# Resource Limits

| Phase | Timeout | Max Retries |
|-------|---------|-------------|
| Test Generation | 60s | 2 |
| Implementation | 120s | 3 |
| Quality Gates (each) | 30s | 3 |
| Total Pipeline | 600s | — |

On a non-recoverable error, the pipeline pauses with a diagnostic, the attempts made, and the recommended next step. It does not silently skip the failure.

# Boundaries

**Will:**
- Generate failing tests before any implementation
- Cover APIs, services, scripts, schedulers, CLI tools, and middleware
- Enforce every configured type, lint, format, and coverage gate and report which gates are not configured
- Propose a conventional commit and wait for user approval

**Will Not:**
- Build UI components—route those to `sc-tdd-uiux`
- Execute end-to-end browser tests—out of scope for backend
- Push to a remote without explicit user request
- Skip the red phase or accept implementation-first ordering

# See Also

- [sc-test-design](../sc-test-design/SKILL.md) — Test Case Design lead-in that produces the role-reviewed spec
- [sc-tdd orchestrator](../sc-tdd/SKILL.md) — use when the domain isn't already clear
