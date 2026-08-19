# Analyze PR and Change Impact

## Goal

Explain the semantic behavior delta and its transitive risk. Do not merely paraphrase
changed lines or list changed files.

## Anchor the comparison

1. Capture the PR or change intent, acceptance criteria, base revision, head revision,
   and relevant configuration.
2. Prefer PR metadata for the intended base; otherwise resolve the merge base and
   disclose the choice.
3. Separate the target diff from unrelated dirty worktree changes.
4. Classify formatting, generated output, lockfiles, snapshots, renames, mechanical
   refactors, and code motion before analyzing semantic changes.

## Map the impact surface

Trace outward in this order:

1. Changed behavior and symbols
2. Direct callers, callees, dispatch, and dependency injection
3. Public API, event, schema, serialization, configuration, and migration contracts
4. Downstream consumers, storage, external services, and operational tooling
5. Tests, observability, deployment, compatibility, rollback, performance, and concurrency

Inspect unchanged code whenever it consumes a changed contract. Treat the textual diff
as the starting point, not the boundary of impact.

## Build the behavior matrix

Use concrete scenarios:

| Scenario/precondition | Base behavior | Head behavior | Intended? | Evidence/check | Residual risk |
|---|---|---|---|---|---|

Also list preserved invariants: behaviors that must remain unchanged despite the diff.

## Verify

- Map each acceptance criterion and behavioral claim to a test or executable check.
- Prefer a focused test that fails on the base and passes on the head for newly added
  behavior when feasible.
- Establish whether failures are pre-existing before attributing them to the change.
- Check negative, boundary, permission, retry, partial-failure, state-transition,
  migration, compatibility, and rollback scenarios according to risk.
- Confirm that tests assert the changed behavior rather than only execute changed lines.
- Record skipped, flaky, timed-out, or environment-blocked checks explicitly.

## Output

Return:

1. Intended observable change
2. Before/after behavior matrix
3. Transitive impact and blast radius
4. Preserved invariants
5. Validation evidence with exact commands or reproducible actions for `RUNTIME` claims
6. Compatibility, operational, and rollback concerns
7. Residual risk and a conditional merge, hold, or block recommendation when requested

Avoid reviewing every file equally. Spend attention in proportion to behavioral and
operational consequence.
