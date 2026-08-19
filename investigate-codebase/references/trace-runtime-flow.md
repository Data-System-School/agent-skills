# Trace Runtime, Control, and Data Flow

## Goal

Explain one concrete behavior as a falsifiable causal path. Distinguish static
reachability from behavior actually observed at runtime.

## Procedure

1. Choose a concrete input, triggering event, configuration, and expected observable
   result. Use a real example when available.
2. Locate the true entry point, including framework routing, middleware, CLI wiring,
   message subscription, scheduler, or event dispatch.
3. Follow the path through boundary validation, authentication, orchestration,
   domain decisions, persistence or external effects, response construction, error
   handling, and telemetry.
4. At each step record:

   | Step | Symbol | Input shape | Decision or transformation | Output/side effect | Evidence |
   |---|---|---|---|---|---|

5. Track data identity and shape changes. Note defaults, normalization, serialization,
   validation, caching, batching, and lossy conversions.
6. Identify the owner and lifetime of mutable state. Include transaction, queue,
   retry, idempotency, cancellation, timeout, and concurrency behavior when relevant.
7. Resolve conditional routes created by feature flags, environment values, runtime
   type dispatch, dependency injection, decorators, plugins, callbacks, or reflection.
   Mark an edge unknown if it cannot be resolved statically.
8. Trace at least one failure path and its externally visible result. Include cleanup
   and terminal-state behavior.
9. Form predictions such as: "With input X and flag Y, execution reaches A then B,
   writes C, and emits D." Select a focused test, trace, or log observation that could
   disprove each important prediction.

## Output

Return:

1. The direct causal answer
2. Trigger, preconditions, and observable result
3. The shortest supported execution path
4. Data transformations and state ownership
5. Side effects, errors, retries, cancellation, and configuration branches
6. Static evidence versus runtime evidence
7. Exact reproduction command or action and outcome for every `RUNTIME` claim
8. Counterexamples, unresolved dynamic edges, and smallest next check

Do not call a sequence diagram a runtime trace unless execution was observed. Label a
source-derived diagram as a static model.
