---
name: sc-test-design
description: Design a reviewable test-case specification, not executable code, where every case records What it tests, Who it protects, Why it matters, Given/When/Then, and a negative companion before role-based review. Use before writing tests, when the user invokes $sc-test-design in Codex or /sc-test-design in Claude Code, asks to design or enumerate test cases, requests a test plan, or enters the sc-tdd, sc-tdd-backend, or sc-tdd-uiux pipeline.
---

# Overview

This skill designs test cases as a **specification document**, not as executable test code. It exists because a test suite is only as thorough as the intent behind it: when each case states *what* behaviour is under test, *who* (which stakeholder/role) it protects, and *why* it matters (the risk if it breaks), the cases become both more exhaustive and far easier to review. The spec is organized so that **each role can review only the slice they own**.

It produces a single artifact—the test-case spec—and hands it to the TDD pipeline, which turns it into failing tests. It never writes implementation or test code itself.

**Invoke this skill when:**

- The user explicitly invokes `$sc-test-design` in Codex or `/sc-test-design` in Claude Code
- The user asks to "design test cases", "enumerate test cases", "write a test plan", or "review test cases by role"
- Test intent (what/who/why) should be captured and reviewed before any test code exists
- The `sc-tdd`, `sc-tdd-backend`, or `sc-tdd-uiux` pipeline reaches its **Test Case Design** lead-in step
- A feature needs a role-reviewable spec before red-green-refactor begins

# Intent Schema

Every test case MUST carry all seven fields. A case missing any field is incomplete and must not enter review.

| Field | Meaning | Why it matters |
|-------|---------|----------------|
| **What** | The specific behaviour or contract under test | Defines scope; prevents vague "tests the function" cases |
| **Who** | The stakeholder/role this case protects (end user, API consumer, ops, finance, screen-reader user, …) | Anchors the case to a real party so reviewers can judge relevance |
| **Why** | The risk/failure cost if this behaviour breaks | Drives prioritization and reveals the severity behind each case |
| **Type** | `unit` \| `integration` \| `a11y` \| `performance` \| `security` \| `e2e` | Routes the case to the owning review role and the right test layer |
| **Roles** | One or more review roles responsible for this case (from `.claude/test-roles.md`) | Enables role-partitioned review |
| **GWT** | Given / When / Then scenario, objective and automatable | The executable specification the TDD pipeline consumes |
| **Negative** | At least one "must fail when …" companion scenario | Guarantees the case also pins down what is *not* allowed |

# Role File Discovery & Creation

Test-case review is role-partitioned. The roles live in a project file. **Before designing cases, locate that file; if absent, create it first.**

1. **Discover** — Look for the role definition in this order: `.claude/test-roles.md`, then `docs/TEST_ROLES.md`, then root `TEST_ROLES.md`. If any exists, load it and use its roles verbatim.
2. **Create when absent** — If none exists, create `.claude/test-roles.md` (path is explicit so the side effect is auditable) seeded with five default roles, and tell the user it was created and where. Do not silently proceed without a role file.

Default seed for `.claude/test-roles.md`:

```markdown
# Test Review Roles

Each test case in an sc-test-design spec is tagged with one or more roles below.
Reviewers read only the cases tagged for their role.

## QA / Functional
- focus: correctness of happy paths, boundaries, and error paths
- owns_test_types: unit, integration, e2e
- review_checklist:
  - Every public behaviour has at least one positive and one negative case
  - Boundary values (0, empty, max, off-by-one) are covered
  - Error paths assert the specific failure, not just "throws"

## Security
- focus: authn/authz, input validation, data exposure, injection
- owns_test_types: security, integration
- review_checklist:
  - Unauthorized and privilege-escalation attempts are tested
  - Untrusted input is validated/escaped at the boundary
  - No secret/PII leaks through responses, logs, or errors

## Domain / PO
- focus: business rules, acceptance criteria, stakeholder value
- owns_test_types: unit, integration, e2e
- review_checklist:
  - Each acceptance criterion maps to at least one case
  - "Who" field names a real stakeholder for every case
  - Business edge cases (refunds, partial states, limits) are present

## Accessibility
- focus: WCAG, keyboard/focus, roles/labels, screen-reader output
- owns_test_types: a11y, e2e
- review_checklist:
  - Interactive elements are keyboard-operable with visible focus
  - Roles, names, and labels are asserted
  - Error and status messages are programmatically announced

## Performance
- focus: latency, throughput, resource budgets, scalability limits
- owns_test_types: performance, integration
- review_checklist:
  - Hot paths assert a concrete budget (time, queries, allocations)
  - Degradation under load or large input is covered
  - N+1 / unbounded-growth scenarios are tested
```

When a project's role file already defines different roles, honor it and tag cases against those roles instead of the defaults.

# Pipeline

1. **Role File Resolution** — Discover or create `.claude/test-roles.md` per the rules above. Load the active role set.
2. **Context Discovery** — Read applicable `AGENTS.md` files first, then `README.md`, optional `CLAUDE.md` or `.claude/CONVENTIONS.md`, the feature description, and any referenced source. Read independent files in parallel when the runtime supports it.
3. **Test Case Design** — Enumerate cases covering happy paths, boundaries, error paths, and the negative companion for each. Fill all seven Intent Schema fields per case. Analyze deeply enough to surface cases the user did not mention. Tag every case with its owning role(s).
4. **Role-based Review** — For each role present in the spec, review that role's slice against its `review_checklist`. Surface gaps (missing case, weak GWT, absent negative, untagged stakeholder) and revise. A role's slice passes only when its checklist is satisfiable from the spec.
5. **Spec Output** — Write the spec to `.claude/test-design/{YYYY-MM-DD-HHmm}_{slug}.md`: a full case table, then one section per role containing that role's cases and review outcome. This file is the artifact the TDD pipeline consumes.

# Runtime Compatibility

- Use the current agent and the runtime's available file, shell, and plan tools. Do not require Claude Code's `Task` tool, fixed Claude model names, or any provider-specific subagent API.
- Perform role reviews sequentially by default. Parallelize independent role reviews only when the runtime supports it and the user or active project instructions permit delegation.
- Treat `--cost-optimize` as a request for a concise single-pass review and `--quality-first` as a request for deeper edge-case analysis and a second review pass; do not map either flag to a hard-coded model.
- Keep `.claude/test-design/` and `.claude/test-roles.md` as the project's existing shared artifact paths. Codex may create and update them.

# Side Effects

- Creates `.claude/test-roles.md` in the target project **only if no role file exists** (seeded with the five default roles above).
- Writes the spec to `.claude/test-design/{YYYY-MM-DD-HHmm}_{slug}.md` in the target project.
- Never writes source code, test code, or files outside `.claude/` in the target project.

# Boundaries

**Will:**
- Produce a reviewable test-case specification with full What/Who/Why intent per case
- Discover or create `.claude/test-roles.md` before designing cases
- Partition the spec by role and run role-based review against each role's checklist
- Hand the spec to the TDD pipeline as the input to Test Generation

**Will Not:**
- Write executable tests or implementation code (the TDD pipeline does that)
- Proceed without an active role file
- Emit a case missing any of the seven Intent Schema fields
- Tag a case with a role not defined in the project's role file

# See Also

- [sc-tdd orchestrator](../sc-tdd/SKILL.md) — consumes this spec at its Test Case Design step
- [sc-tdd-backend](../sc-tdd-backend/SKILL.md) · [sc-tdd-uiux](../sc-tdd-uiux/SKILL.md) — specialized pipelines that run this skill first
