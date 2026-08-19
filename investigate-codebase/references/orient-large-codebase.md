# Orient in a Large Codebase

## Goal

Create a compact navigation model of runtime and domain boundaries. Do not summarize
every directory or attempt to understand every implementation detail.

## Procedure

1. Confirm the repository or monorepo scope and the revision being examined.
2. Inspect repository instructions, workspace and package manifests, build files,
   CI configuration, deploy configuration, ownership metadata, and top-level docs.
3. Identify:
   - executable and request entry points;
   - applications, services, packages, and shared libraries;
   - domain ownership and state ownership;
   - public API, event, schema, storage, and external-service boundaries;
   - test topology and representative fixtures;
   - generated, vendored, build, migration, and deployment surfaces.
4. Group code by runtime or domain responsibility, not merely by directory name.
5. Select one to three representative vertical slices that cross meaningful
   boundaries. Prefer real user-visible or operational flows.
6. Reconcile documented architecture with imports, wiring, configuration, tests,
   and executable entry points. Record contradictions.
7. Classify candidate files as:
   - `must-read`: required to understand a primary boundary or flow;
   - `supporting`: useful for contracts, variants, or failure behavior;
   - `parking-lot`: interesting but outside the current question.
8. Stop the first pass after roughly five to seven core components and a
   five-to-twelve-file reading route. Split the repository into subsystems if the
   active model exceeds roughly ten to twelve major symbols or concepts.

## Questions the map must answer

- Where can execution enter the system?
- Which component owns each decision and mutable state?
- Which contracts connect components?
- Where do durable and external side effects occur?
- Which configuration or deployment choices change the path?
- Which tests best demonstrate each representative flow?
- Which important edges remain dynamic, inferred, or unknown?

## Output

Return:

1. A one-paragraph system purpose and boundary statement
2. A compact component map with responsibilities and contracts
3. One to three representative vertical slices
4. A project-specific glossary only for terms needed by the explanation
5. The ordered reading route with one reason per file
6. Contradictions, unknowns, and the next subsystem worth mapping

Avoid a directory-by-directory tour. Mention file counts or language statistics only
when they influence how the repository should be navigated.
