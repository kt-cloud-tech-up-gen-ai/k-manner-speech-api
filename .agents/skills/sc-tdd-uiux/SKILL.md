---
name: sc-tdd-uiux
description: Run a UI/UX-specialized red-green-refactor pipeline with rendering, interaction, accessibility tests, and configured quality gates. Use for components, forms, modals, interactions, layout, and accessibility across React, Vue, Angular, and Svelte, or when the user invokes $sc-tdd-uiux in Codex or /sc-tdd-uiux in Claude Code.
---

# Overview

This skill runs the Test-First Development pipeline for UI work: rendering, interaction, and accessibility tests are generated and verified to fail first, implementation stays minimal, and quality gates (including WCAG checks) enforce correctness before the commit is proposed.

**Invoke this skill when:**

- The user explicitly invokes `$sc-tdd-uiux` in Codex or `/sc-tdd-uiux` in Claude Code
- The feature is a client-side component, form, modal, layout, or interaction
- The `sc-tdd` orchestrator classifies the request as `UI_ONLY`
- Accessibility (a11y, WCAG, screen reader, ARIA) is an explicit requirement

# Pipeline

1. **Framework Detection** — Read `package.json` to detect React, Vue, Angular, or Svelte and load the matching testing-library.
2. **Test Case Design** — Read and follow [`../sc-test-design/SKILL.md`](../sc-test-design/SKILL.md) to produce a role-reviewed spec covering rendering, interaction, and a11y: each case records What/Who/Why plus a Given/When/Then and a negative companion, and the Accessibility role reviews the a11y slice. If the project has no role file, `sc-test-design` creates `.claude/test-roles.md` before designing cases. This spec is the input to Test Generation.
3. **Test Generation** — Turn each spec case into a rendering, user-event, keyboard-interaction, accessibility (roles, labels, focus order), or error-state test. Verify the suite fails before proceeding.
4. **Implementation** — Write the minimum component code to pass the tests, one cycle at a time. On failure, diagnose from current evidence before retrying, up to 3 attempts.
5. **Quality Gates** — Discover and run every gate configured by the repository: tests, type check, lint, formatter, coverage, automated WCAG checks, and an E2E smoke test. Require coverage ≥ 80% when coverage tooling and a threshold are configured. Report an absent gate as `not configured`; do not install new tooling unless the user asks for it.
6. **Cleanup** — Remove unused imports, dead CSS, and temporary fixtures.
7. **Commit** — Propose a conventional commit message with coverage and a11y metrics. Wait for the user's explicit approval.

# Runtime Compatibility

- Use the current agent and the runtime's available file, shell, and plan tools. Do not require Claude Code's `Task` tool, fixed Claude model names, or any provider-specific subagent API.
- Run the pipeline in the current agent by default. Delegate independent review or verification only when the runtime supports it and the user or active project instructions permit delegation; lack of delegation must never skip a phase.
- Treat `--cost-optimize` as fewer review passes and `--quality-first` as deeper interaction/a11y analysis and an additional review pass. Do not map either flag to a hard-coded model.
- Discover the repository's configured test, type, lint, format, coverage, a11y, and E2E commands before running gates. Run every available gate, report unavailable gates as `not configured`, and do not install or invent a tool solely to satisfy a gate.

# Framework Support

| Framework | Testing Library | Minimum Version |
|-----------|----------------|-----------------|
| React | `@testing-library/react` | 14+ |
| Vue | `@testing-library/vue` | 8+ |
| Angular | `@testing-library/angular` | 14+ |
| Svelte | `@testing-library/svelte` | 4+ |

# Resource Limits

| Phase | Timeout | Max Retries |
|-------|---------|-------------|
| Test Generation | 90s | 2 |
| Implementation | 150s | 3 |
| Quality Gates (each) | 45s | 3 |
| E2E Smoke Test | 120s | 1 |
| Total Pipeline | 720s | — |

On a non-recoverable error, the pipeline pauses with diagnostics rather than silently skipping.

# Boundaries

**Will:**
- Generate rendering, interaction, and a11y tests before implementation
- Support React, Vue, Angular, and Svelte with auto-detected testing libraries
- Enforce configured WCAG checks and report when no automated a11y gate is configured
- Propose a conventional commit and wait for user approval

**Will Not:**
- Build backend services or API endpoints—route those to `sc-tdd-backend`
- Skip accessibility checks even when the user does not explicitly request them
- Push to a remote without explicit user request
- Accept implementation-first ordering

# See Also

- [sc-test-design](../sc-test-design/SKILL.md) — Test Case Design lead-in that produces the role-reviewed spec
- [sc-tdd orchestrator](../sc-tdd/SKILL.md) — use when the domain isn't already clear
